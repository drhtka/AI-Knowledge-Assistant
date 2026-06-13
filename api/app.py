from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from api.ingestion import load_chunks, save_uploaded_document
from api.retrieval import ask, search
from api.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    IngestResponse,
    SearchRequest,
    SearchResponse,
    WebSearchRequest,
    WebSearchResponse,
)
from api.settings import (
    CHUNK_OVERLAP_WORDS,
    CHUNK_SIZE_WORDS,
    STATIC_DIR,
    TEMPLATES_DIR,
)
from api.web_search import web_search


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_chunks()
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


def _build_mode_comparison(question: str, top_k: int) -> list[dict[str, object]]:
    comparisons: list[dict[str, object]] = []
    for mode in RETRIEVAL_MODE_OPTIONS:
        result = search(question, top_k, retrieval_mode=mode)
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


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    question = request.query_params.get("question", "")
    top_k_raw = request.query_params.get("top_k", "3") or "3"
    top_k = max(1, min(10, int(top_k_raw)))
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

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "page_title": "AI Knowledge Assistant",
            "question": question,
            "top_k": top_k,
            "retrieval_mode": retrieval_mode,
            "retrieval_mode_options": RETRIEVAL_MODE_OPTIONS,
            "system_config": {
                "default_retrieval_mode": "auto",
                "chunk_size_words": CHUNK_SIZE_WORDS,
                "chunk_overlap_words": CHUNK_OVERLAP_WORDS,
                "available_retrieval_modes": RETRIEVAL_MODE_OPTIONS,
            },
            "web_question": web_question,
            "web_top_k": web_top_k,
            "demo_prompts": DEMO_PROMPTS,
            "search_result": search_result,
            "ask_result": ask_result,
            "mode_comparison": mode_comparison,
            "web_search_result": web_search_result,
            "web_search_error": web_search_error,
            "search_result_json": search_result.model_dump(mode="json") if search_result else {},
            "ask_result_json": ask_result.model_dump(mode="json") if ask_result else {},
            "web_search_result_json": web_search_result.model_dump(mode="json") if web_search_result else {},
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", ready=True, project="ai_knowledge_assistant")


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
async def ingest_endpoint(file: UploadFile = File(...)) -> IngestResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required.")

    file_content = await file.read()
    if not file_content.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        stored_path = save_uploaded_document(file.filename, file_content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    chunks_loaded = sum(1 for chunk in load_chunks() if chunk.document_id.startswith(stored_path.stem))
    return IngestResponse(
        status="ok",
        filename=file.filename,
        stored_path=str(stored_path),
        chunks_loaded=chunks_loaded,
    )


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(request: AskRequest) -> AskResponse:
    return ask(
        question=request.question,
        top_k=request.top_k,
        retrieval_mode=request.retrieval_mode,
    )
