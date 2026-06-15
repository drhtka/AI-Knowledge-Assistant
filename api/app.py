from __future__ import annotations

from contextlib import asynccontextmanager
from urllib.parse import urlencode

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.chunking_config import CHUNKING_PRESETS, get_chunking_config, set_chunking_preset
from api.indexing_service import (
    consume_rerun_request,
    ensure_index_loaded,
    get_reindex_history,
    get_reindex_status,
    prepare_uploaded_document,
    rebuild_index,
    start_reindex_job,
)
from api.ingestion import build_document_preview
from api.logging_utils import configure_logging
from api.retrieval import ask, get_retrieval_history, get_retrieval_runtime_snapshot, search
from api.schemas import (
    AskRequest,
    AskResponse,
    ChunkingConfigResponse,
    ChunkingConfigUpdateRequest,
    HealthResponse,
    IngestResponse,
    PgvectorMetadataSnapshotResponse,
    ReindexHistoryEntryResponse,
    ReindexHistoryResponse,
    ReindexStartResponse,
    ReindexStatusResponse,
    RetrievalHistoryEntryResponse,
    RetrievalHistoryResponse,
    RetrievalRuntimeSnapshotResponse,
    RuntimeObservabilityResponse,
    SearchRequest,
    SearchResponse,
    StorageConfigResponse,
    StorageConfigUpdateRequest,
    WebSearchHistoryEntryResponse,
    WebSearchHistoryResponse,
    WebSearchRequest,
    WebSearchResponse,
)
from api.storage import get_active_storage_backend, get_storage_backend_config, set_active_storage_backend
from api.settings import (
    RAW_DATA_DIR,
    STATIC_DIR,
    TEMPLATES_DIR,
)
from api.web_search import get_web_search_history, web_search


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    ensure_index_loaded()
    yield


app = FastAPI(
    title="AI Knowledge Assistant API",
    version="0.1.0",
    description="Compact scaffold for a production-like RAG portfolio project.",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

DEMO_PROMPTS = [
    {
        "label": "Architecture",
        "question": "What layers should a production-like RAG system have?",
    },
    {
        "label": "Evaluation",
        "question": "How should I evaluate retrieval quality in a RAG system?",
    },
    {
        "label": "Hybrid Search",
        "question": "Why does hybrid retrieval help compared to embeddings only?",
    },
]

RETRIEVAL_MODE_OPTIONS = ("auto", "tfidf", "embeddings")
TOP_K_OPTIONS = tuple(range(1, 11))


def _preset_label(preset: str) -> str:
    return preset.split("_", 1)[0]


def _build_mode_comparison(question: str, top_k: int) -> list[dict[str, object]]:
    comparisons: list[dict[str, object]] = []
    for mode in RETRIEVAL_MODE_OPTIONS:
        result = search(
            question,
            top_k,
            retrieval_mode=mode,
            record_runtime_snapshot=False,
            record_history=False,
        )
        top_hit = result.hits[0] if result.hits else None
        comparisons.append(
            {
                "mode": mode,
                "top_source": top_hit.title if top_hit else "No match",
                "top_score": top_hit.score if top_hit else 0.0,
                "hit_count": len(result.hits),
            }
        )
    return comparisons


def _build_reindex_status_response() -> ReindexStatusResponse:
    status_snapshot = get_reindex_status()
    return ReindexStatusResponse(
        state=status_snapshot.state,
        trigger=status_snapshot.trigger,
        active_storage_backend=status_snapshot.backend,
        started_at=status_snapshot.started_at,
        finished_at=status_snapshot.finished_at,
        last_error=status_snapshot.last_error,
        rerun_requested=status_snapshot.rerun_requested,
        rerun_trigger=status_snapshot.rerun_trigger,
        outcome=status_snapshot.outcome,
        summary_message=status_snapshot.summary_message,
        last_successful_backend=status_snapshot.last_successful_backend,
        last_successful_finished_at=status_snapshot.last_successful_finished_at,
        document_count=status_snapshot.document_count,
        chunk_count=status_snapshot.chunk_count,
        elapsed_ms=status_snapshot.elapsed_ms,
    )


def _build_reindex_history_response(limit: int) -> ReindexHistoryResponse:
    return ReindexHistoryResponse(
        entries=[
            ReindexHistoryEntryResponse(
                history_entry_id=entry.history_entry_id,
                trigger=entry.trigger,
                active_storage_backend=entry.backend,
                state=entry.state,
                outcome=entry.outcome,
                started_at=entry.started_at,
                finished_at=entry.finished_at,
                summary_message=entry.summary_message,
                last_error=entry.last_error,
                document_count=entry.document_count,
                chunk_count=entry.chunk_count,
                elapsed_ms=entry.elapsed_ms,
            )
            for entry in get_reindex_history(limit=limit)
        ]
    )


def _build_retrieval_history_response(limit: int) -> RetrievalHistoryResponse:
    return RetrievalHistoryResponse(
        entries=[
            RetrievalHistoryEntryResponse(
                history_entry_id=entry.history_entry_id,
                request_kind=entry.request_kind,
                status=entry.status,
                question_length=entry.question_length,
                retrieval_mode=entry.retrieval_mode,
                active_storage_backend=entry.active_storage_backend,
                retrieval_execution_path=entry.retrieval_execution_path,
                retrieval_execution_issue=entry.retrieval_execution_issue,
                retrieval_outcome=entry.retrieval_outcome,
                retrieval_summary_message=entry.retrieval_summary_message,
                hit_count=entry.hit_count,
                latency_ms=entry.latency_ms,
                updated_at=entry.updated_at,
                error_type=entry.error_type,
            )
            for entry in get_retrieval_history(limit=limit)
        ]
    )


def _build_web_search_history_response(limit: int) -> WebSearchHistoryResponse:
    return WebSearchHistoryResponse(
        entries=[
            WebSearchHistoryEntryResponse(
                history_entry_id=entry.history_entry_id,
                question_length=entry.question_length,
                top_k=entry.top_k,
                engine=entry.engine,
                status=entry.status,
                hit_count=entry.hit_count,
                latency_ms=entry.latency_ms,
                updated_at=entry.updated_at,
                error_type=entry.error_type,
            )
            for entry in get_web_search_history(limit=limit)
        ]
    )


def _run_reindex_background_job(trigger: str, started_at: str | None) -> None:
    current_trigger = trigger
    current_started_at = started_at
    assume_running = True
    while True:
        rebuild_index(
            trigger=current_trigger,
            started_at_iso=current_started_at,
            assume_running=assume_running,
        )
        rerun_trigger = consume_rerun_request()
        if not rerun_trigger:
            return
        current_trigger = rerun_trigger
        current_started_at = None
        assume_running = False


def _build_reindex_start_response(trigger: str = "manual") -> ReindexStartResponse:
    start_result = start_reindex_job(trigger=trigger)
    message = (
        "Reindex job started in the background."
        if start_result.accepted
        else "Reindex is already running; rerun requested."
    )
    return ReindexStartResponse(
        status="accepted" if start_result.accepted else "already_running",
        accepted=start_result.accepted,
        state=start_result.status_snapshot.state,
        trigger=start_result.status_snapshot.trigger,
        active_storage_backend=start_result.status_snapshot.backend,
        started_at=start_result.status_snapshot.started_at,
        finished_at=start_result.status_snapshot.finished_at,
        rerun_trigger=start_result.status_snapshot.rerun_trigger,
        outcome=start_result.status_snapshot.outcome,
        summary_message=start_result.status_snapshot.summary_message,
        last_successful_backend=start_result.status_snapshot.last_successful_backend,
        last_successful_finished_at=start_result.status_snapshot.last_successful_finished_at,
        message=message,
        rerun_requested=start_result.status_snapshot.rerun_requested,
    )


def _build_chunking_config_response(
    updated_config: dict[str, object],
    reindex_start: ReindexStartResponse,
) -> ChunkingConfigResponse:
    return ChunkingConfigResponse(
        current_preset=updated_config["current_preset"],
        chunk_size_words=updated_config["chunk_size_words"],
        chunk_overlap_words=updated_config["chunk_overlap_words"],
        available_presets=updated_config["available_presets"],
        active_storage_backend=get_active_storage_backend(),
        reindex_accepted=reindex_start.accepted,
        reindex_state=reindex_start.state,
        reindex_started_at=reindex_start.started_at,
        reindex_message=reindex_start.message,
        rerun_requested=reindex_start.rerun_requested,
    )


def _build_pgvector_metadata_snapshot_response(
    payload: object,
) -> PgvectorMetadataSnapshotResponse | None:
    if not isinstance(payload, dict):
        return None

    return PgvectorMetadataSnapshotResponse(
        chunk_size_words=int(payload["chunk_size_words"]),
        chunk_overlap_words=int(payload["chunk_overlap_words"]),
        chunking_version=str(payload["chunking_version"]),
        indexed_at=str(payload["indexed_at"]),
        chunk_count=int(payload["chunk_count"]),
        source_file_count=int(payload["source_file_count"]),
        embedding_document_count=int(payload["embedding_document_count"]),
        lexical_document_count=int(payload["lexical_document_count"]),
    )


def _build_storage_config_response(
    storage_config: dict[str, object],
    reindex_start: ReindexStartResponse,
) -> StorageConfigResponse:
    return StorageConfigResponse(
        current_backend=storage_config["current_backend"],
        default_backend=storage_config["default_backend"],
        available_backends=storage_config["available_backends"],
        runtime_override_active=storage_config["runtime_override_active"],
        active_backend_summary_message=storage_config["active_backend_summary_message"],
        active_backend_state=storage_config["active_backend_state"],
        active_backend_issue=storage_config["active_backend_issue"],
        active_backend_ready=storage_config["active_backend_ready"],
        active_backend_can_connect=storage_config["active_backend_can_connect"],
        active_backend_retrieval_ready=storage_config["active_backend_retrieval_ready"],
        active_backend_indexing_ready=storage_config["active_backend_indexing_ready"],
        active_backend_indexing_preflight=storage_config["active_backend_indexing_preflight"],
        active_backend_message=storage_config["active_backend_message"],
        active_backend_indexing_message=storage_config["active_backend_indexing_message"],
        pgvector_metadata_snapshot=_build_pgvector_metadata_snapshot_response(
            storage_config.get("pgvector_metadata_snapshot")
        ),
        reindex_accepted=reindex_start.accepted,
        reindex_state=reindex_start.state,
        reindex_started_at=reindex_start.started_at,
        reindex_message=reindex_start.message,
        rerun_requested=reindex_start.rerun_requested,
    )


def _start_reindex_background_job(
    background_tasks: BackgroundTasks,
    trigger: str,
) -> ReindexStartResponse:
    response = _build_reindex_start_response(trigger=trigger)
    if response.accepted:
        background_tasks.add_task(
            _run_reindex_background_job,
            response.trigger,
            response.started_at,
        )
    return response


async def _ingest_uploaded_file(file: UploadFile, background_tasks: BackgroundTasks) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    file_content = await file.read()
    if not file_content.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        ingested_document = prepare_uploaded_document(file.filename, file_content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    reindex_start = _start_reindex_background_job(background_tasks, trigger="upload")

    return IngestResponse(
        status="ok",
        filename=ingested_document.original_filename,
        source_name=ingested_document.stored_path.name,
        file_type=ingested_document.file_type,
        stored_path=str(ingested_document.stored_path),
        estimated_chunks=ingested_document.estimated_chunks,
        preview_text=ingested_document.preview_text,
        reindex_accepted=reindex_start.accepted,
        reindex_state=reindex_start.state,
        reindex_started_at=reindex_start.started_at,
        reindex_message=reindex_start.message,
        rerun_requested=reindex_start.rerun_requested,
    )


def _build_upload_feedback(request: Request) -> dict[str, object] | None:
    upload_status = request.query_params.get("upload_status", "")
    if not upload_status:
        return None

    source_name = request.query_params.get("uploaded_source_name", "")
    preview_text = ""
    if upload_status == "ok" and source_name:
        preview_path = RAW_DATA_DIR / source_name
        if preview_path.exists():
            preview_text = build_document_preview(preview_path)

    return {
        "status": upload_status,
        "filename": request.query_params.get("uploaded_filename", ""),
        "source_name": source_name,
        "file_type": request.query_params.get("uploaded_file_type", ""),
        "estimated_chunks": request.query_params.get("uploaded_estimated_chunks", "0"),
        "preview_text": preview_text,
        "reindex_message": request.query_params.get("uploaded_reindex_message", ""),
        "reindex_state": request.query_params.get("uploaded_reindex_state", ""),
        "error": request.query_params.get("upload_error", ""),
    }


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    chunk_size_options = sorted(
        {config["chunk_size_words"] for config in CHUNKING_PRESETS.values()},
        reverse=True,
    )
    chunk_overlap_options = sorted(
        {config["chunk_overlap_words"] for config in CHUNKING_PRESETS.values()},
        reverse=True,
    )
    preset_display_options = [
        {"value": preset, "label": _preset_label(preset)}
        for preset in CHUNKING_PRESETS.keys()
    ]
    question = request.query_params.get("question", "")
    has_top_k_query = "top_k" in request.query_params
    top_k_raw = request.query_params.get("top_k", "3") or "3"
    top_k = max(1, min(10, int(top_k_raw)))
    has_retrieval_mode_query = "retrieval_mode" in request.query_params
    retrieval_mode = request.query_params.get("retrieval_mode", "auto") or "auto"
    if retrieval_mode not in RETRIEVAL_MODE_OPTIONS:
        retrieval_mode = "auto"
    web_question = request.query_params.get("web_question", "")
    web_top_k_raw = request.query_params.get("web_top_k", "5") or "5"
    web_top_k = max(1, min(10, int(web_top_k_raw)))

    search_result = search(question, top_k, retrieval_mode=retrieval_mode) if question else None
    ask_result = ask(question, top_k, retrieval_mode=retrieval_mode) if question else None
    web_search_result = None
    web_search_error = ""
    if web_question:
        try:
            web_search_result = web_search(question=web_question, top_k=web_top_k)
        except ValueError as exc:
            web_search_error = str(exc)
    mode_comparison = _build_mode_comparison(question, top_k) if question else []
    upload_feedback = _build_upload_feedback(request)
    storage_config = get_storage_backend_config()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page_title": "AI Knowledge Assistant",
            "question": question,
            "top_k": top_k,
            "has_top_k_query": has_top_k_query,
            "retrieval_mode": retrieval_mode,
            "has_retrieval_mode_query": has_retrieval_mode_query,
            "retrieval_mode_options": RETRIEVAL_MODE_OPTIONS,
            "system_config": {
                "default_retrieval_mode": "auto",
                "available_retrieval_modes": RETRIEVAL_MODE_OPTIONS,
                "available_chunk_sizes": chunk_size_options,
                "available_chunk_overlaps": chunk_overlap_options,
                "preset_display_options": preset_display_options,
                "available_top_k": TOP_K_OPTIONS,
                "current_storage_backend": storage_config["current_backend"],
                "default_storage_backend": storage_config["default_backend"],
                "available_storage_backends": storage_config["available_backends"],
                "storage_runtime_override_active": storage_config["runtime_override_active"],
                **get_chunking_config(),
            },
            "web_question": web_question,
            "web_top_k": web_top_k,
            "demo_prompts": DEMO_PROMPTS,
            "search_result": search_result,
            "ask_result": ask_result,
            "mode_comparison": mode_comparison,
            "upload_feedback": upload_feedback,
            "reindex_status": _build_reindex_status_response(),
            "web_search_result": web_search_result,
            "web_search_error": web_search_error,
            "search_result_json": search_result.model_dump(mode="json") if search_result else {},
            "ask_result_json": ask_result.model_dump(mode="json") if ask_result else {},
            "web_search_result_json": web_search_result.model_dump(mode="json") if web_search_result else {},
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    storage_config = get_storage_backend_config()
    ready = bool(
        storage_config["active_backend_ready"]
        and storage_config["active_backend_retrieval_ready"]
        and storage_config["active_backend_indexing_ready"]
    )
    return HealthResponse(
        status="ok" if ready else "degraded",
        ready=ready,
        project="ai_knowledge_assistant",
        active_storage_backend=storage_config["current_backend"],
        active_storage_backend_summary_message=storage_config["active_backend_summary_message"],
        active_storage_backend_state=storage_config["active_backend_state"],
        active_storage_backend_issue=storage_config["active_backend_issue"],
        active_storage_backend_ready=storage_config["active_backend_ready"],
        active_storage_backend_can_connect=storage_config["active_backend_can_connect"],
        active_storage_backend_retrieval_ready=storage_config["active_backend_retrieval_ready"],
        active_storage_backend_indexing_ready=storage_config["active_backend_indexing_ready"],
        active_storage_backend_indexing_preflight=storage_config["active_backend_indexing_preflight"],
        active_storage_backend_message=storage_config["active_backend_message"],
        active_storage_backend_indexing_message=storage_config["active_backend_indexing_message"],
        pgvector_metadata_snapshot=_build_pgvector_metadata_snapshot_response(
            storage_config.get("pgvector_metadata_snapshot")
        ),
    )


@app.get("/chunking-config", response_model=ChunkingConfigResponse)
def chunking_config_endpoint() -> ChunkingConfigResponse:
    chunking_config = get_chunking_config()
    return ChunkingConfigResponse(
        current_preset=chunking_config["current_preset"],
        chunk_size_words=chunking_config["chunk_size_words"],
        chunk_overlap_words=chunking_config["chunk_overlap_words"],
        available_presets=chunking_config["available_presets"],
        active_storage_backend=get_active_storage_backend(),
        reindex_accepted=False,
        reindex_state=get_reindex_status().state,
        reindex_started_at=get_reindex_status().started_at,
        reindex_message="No chunking reindex requested in this response.",
        rerun_requested=get_reindex_status().rerun_requested,
    )


@app.post("/chunking-config", response_model=ChunkingConfigResponse)
def update_chunking_config_endpoint(
    request: ChunkingConfigUpdateRequest,
    background_tasks: BackgroundTasks,
) -> ChunkingConfigResponse:
    updated_config = set_chunking_preset(request.preset)
    reindex_start = _start_reindex_background_job(background_tasks, trigger="chunking_config")
    return _build_chunking_config_response(updated_config, reindex_start)


@app.get("/storage-config", response_model=StorageConfigResponse)
def storage_config_endpoint() -> StorageConfigResponse:
    storage_config = get_storage_backend_config()
    reindex_status = get_reindex_status()
    return _build_storage_config_response(
        storage_config,
        ReindexStartResponse(
            status="noop",
            accepted=False,
            state=reindex_status.state,
            trigger=reindex_status.trigger,
            active_storage_backend=reindex_status.backend,
            started_at=reindex_status.started_at,
            finished_at=reindex_status.finished_at,
            rerun_trigger=reindex_status.rerun_trigger,
            outcome=reindex_status.outcome,
            summary_message=reindex_status.summary_message,
            last_successful_backend=reindex_status.last_successful_backend,
            last_successful_finished_at=reindex_status.last_successful_finished_at,
            message="No storage backend reindex requested in this response.",
            rerun_requested=reindex_status.rerun_requested,
        ),
    )


def _build_runtime_observability_response() -> RuntimeObservabilityResponse:
    storage_config = get_storage_backend_config()
    reindex_status = get_reindex_status()
    last_retrieval = get_retrieval_runtime_snapshot()
    return RuntimeObservabilityResponse(
        active_storage_backend=storage_config["current_backend"],
        active_backend_summary_message=storage_config["active_backend_summary_message"],
        active_backend_state=storage_config["active_backend_state"],
        active_backend_issue=storage_config["active_backend_issue"],
        active_backend_ready=storage_config["active_backend_ready"],
        active_backend_can_connect=storage_config["active_backend_can_connect"],
        active_backend_retrieval_ready=storage_config["active_backend_retrieval_ready"],
        active_backend_indexing_ready=storage_config["active_backend_indexing_ready"],
        active_backend_indexing_preflight=storage_config["active_backend_indexing_preflight"],
        active_backend_message=storage_config["active_backend_message"],
        active_backend_indexing_message=storage_config["active_backend_indexing_message"],
        pgvector_metadata_snapshot=_build_pgvector_metadata_snapshot_response(
            storage_config.get("pgvector_metadata_snapshot")
        ),
        reindex_state=reindex_status.state,
        reindex_trigger=reindex_status.trigger,
        reindex_backend=reindex_status.backend,
        reindex_started_at=reindex_status.started_at,
        reindex_finished_at=reindex_status.finished_at,
        reindex_rerun_requested=reindex_status.rerun_requested,
        reindex_rerun_trigger=reindex_status.rerun_trigger,
        reindex_outcome=reindex_status.outcome,
        reindex_summary_message=reindex_status.summary_message,
        reindex_document_count=reindex_status.document_count,
        reindex_chunk_count=reindex_status.chunk_count,
        reindex_elapsed_ms=reindex_status.elapsed_ms,
        reindex_last_error=reindex_status.last_error,
        reindex_last_successful_backend=reindex_status.last_successful_backend,
        reindex_last_successful_finished_at=reindex_status.last_successful_finished_at,
        last_retrieval=RetrievalRuntimeSnapshotResponse(
            available=last_retrieval.available,
            request_kind=last_retrieval.request_kind,
            status=last_retrieval.status,
            question_length=last_retrieval.question_length,
            retrieval_mode=last_retrieval.retrieval_mode,
            active_storage_backend=last_retrieval.active_storage_backend,
            retrieval_execution_path=last_retrieval.retrieval_execution_path,
            retrieval_execution_issue=last_retrieval.retrieval_execution_issue,
            retrieval_outcome=last_retrieval.retrieval_outcome,
            retrieval_summary_message=last_retrieval.retrieval_summary_message,
            hit_count=last_retrieval.hit_count,
            latency_ms=last_retrieval.latency_ms,
            updated_at=last_retrieval.updated_at,
            error_type=last_retrieval.error_type,
        ),
    )


@app.get("/runtime-observability", response_model=RuntimeObservabilityResponse)
def runtime_observability_endpoint() -> RuntimeObservabilityResponse:
    return _build_runtime_observability_response()


@app.get("/runtime-status", response_model=RuntimeObservabilityResponse)
def runtime_status_endpoint() -> RuntimeObservabilityResponse:
    return _build_runtime_observability_response()


@app.post("/storage-config", response_model=StorageConfigResponse)
def update_storage_config_endpoint(
    request: StorageConfigUpdateRequest,
    background_tasks: BackgroundTasks,
) -> StorageConfigResponse:
    updated_config = set_active_storage_backend(request.backend)
    reindex_start = _start_reindex_background_job(background_tasks, trigger="storage_backend")
    return _build_storage_config_response(updated_config, reindex_start)


@app.post("/reindex", response_model=ReindexStartResponse)
def reindex_endpoint(background_tasks: BackgroundTasks) -> ReindexStartResponse:
    return _start_reindex_background_job(background_tasks, trigger="manual")


@app.get("/reindex-status", response_model=ReindexStatusResponse)
def reindex_status_endpoint() -> ReindexStatusResponse:
    return _build_reindex_status_response()


@app.get("/reindex-history", response_model=ReindexHistoryResponse)
def reindex_history_endpoint(limit: int = Query(default=20, ge=1, le=100)) -> ReindexHistoryResponse:
    return _build_reindex_history_response(limit=limit)


@app.get("/retrieval-history", response_model=RetrievalHistoryResponse)
def retrieval_history_endpoint(limit: int = Query(default=20, ge=1, le=100)) -> RetrievalHistoryResponse:
    return _build_retrieval_history_response(limit=limit)


@app.get("/web-search-history", response_model=WebSearchHistoryResponse)
def web_search_history_endpoint(limit: int = Query(default=20, ge=1, le=100)) -> WebSearchHistoryResponse:
    return _build_web_search_history_response(limit=limit)


@app.post("/search", response_model=SearchResponse)
def search_endpoint(request: SearchRequest) -> SearchResponse:
    return search(
        question=request.question,
        top_k=request.top_k,
        retrieval_mode=request.retrieval_mode,
    )


@app.post("/web-search", response_model=WebSearchResponse)
def web_search_endpoint(request: WebSearchRequest) -> WebSearchResponse:
    try:
        return web_search(question=request.question, top_k=request.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/ingest", response_model=IngestResponse)
async def ingest_endpoint(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> IngestResponse:
    return await _ingest_uploaded_file(file, background_tasks)


@app.post("/upload")
async def upload_page_endpoint(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> RedirectResponse:
    try:
        result = await _ingest_uploaded_file(file, background_tasks)
    except HTTPException as exc:
        query = urlencode(
            {
                "upload_status": "error",
                "upload_error": str(exc.detail),
            },
        )
        return RedirectResponse(url=f"/?{query}", status_code=303)

    query = urlencode(
        {
            "upload_status": "ok",
            "uploaded_filename": result.filename,
            "uploaded_source_name": result.source_name,
            "uploaded_file_type": result.file_type,
            "uploaded_estimated_chunks": result.estimated_chunks,
            "uploaded_reindex_message": result.reindex_message,
            "uploaded_reindex_state": result.reindex_state,
        },
    )
    return RedirectResponse(url=f"/?{query}", status_code=303)


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(request: AskRequest) -> AskResponse:
    return ask(
        question=request.question,
        top_k=request.top_k,
        retrieval_mode=request.retrieval_mode,
    )
