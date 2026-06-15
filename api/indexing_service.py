from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
from pathlib import Path
from threading import RLock
from time import perf_counter

from api.ingestion import (
    build_document_preview,
    estimate_document_chunk_count,
    save_uploaded_document,
)
from api.reindex_history_store import (
    ReindexHistoryEntry,
    create_reindex_history_entry,
    finalize_reindex_history_entry,
    list_reindex_history_entries,
)
from api.runtime_state_store import (
    REINDEX_STATUS_STATE_KEY,
    load_runtime_state,
    save_runtime_state,
)
from api.storage import (
    get_active_storage_backend,
    get_chunk_storage,
    sync_active_storage_source_corpus,
)

logger = logging.getLogger("ai_knowledge_assistant.indexing")


@dataclass(frozen=True)
class ReindexResult:
    document_count: int
    chunk_count: int
    elapsed_ms: int


@dataclass(frozen=True)
class UploadedDocumentResult:
    original_filename: str
    stored_path: Path
    file_type: str
    estimated_chunks: int
    preview_text: str


@dataclass(frozen=True)
class ReindexStatusSnapshot:
    state: str
    trigger: str
    backend: str
    history_entry_id: int | None
    started_at: str | None
    finished_at: str | None
    last_error: str
    rerun_requested: bool
    rerun_trigger: str
    document_count: int
    chunk_count: int
    elapsed_ms: int
    outcome: str
    summary_message: str
    last_successful_backend: str | None
    last_successful_finished_at: str | None


@dataclass(frozen=True)
class ReindexStartResult:
    accepted: bool
    status_snapshot: ReindexStatusSnapshot


_reindex_status_lock = RLock()
_reindex_status_initialized = False


def _default_reindex_status_snapshot() -> ReindexStatusSnapshot:
    return ReindexStatusSnapshot(
        state="idle",
        trigger="startup",
        backend=get_active_storage_backend(),
        history_entry_id=None,
        started_at=None,
        finished_at=None,
        last_error="",
        rerun_requested=False,
        rerun_trigger="",
        document_count=0,
        chunk_count=0,
        elapsed_ms=0,
        outcome="idle",
        summary_message="No reindex job has been recorded yet.",
        last_successful_backend=None,
        last_successful_finished_at=None,
    )


_reindex_status = ReindexStatusSnapshot(
    state="idle",
    trigger="startup",
    backend="file",
    history_entry_id=None,
    started_at=None,
    finished_at=None,
    last_error="",
    rerun_requested=False,
    rerun_trigger="",
    document_count=0,
    chunk_count=0,
    elapsed_ms=0,
    outcome="idle",
    summary_message="No reindex job has been recorded yet.",
    last_successful_backend=None,
    last_successful_finished_at=None,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _derive_reindex_outcome(*, state: str, rerun_requested: bool) -> str:
    if state == "running" and rerun_requested:
        return "rerun_requested"
    if state in {"idle", "running", "succeeded", "failed"}:
        return state
    return "idle"


def _build_reindex_summary_message(
    *,
    state: str,
    outcome: str,
    backend: str,
    trigger: str,
    rerun_requested: bool,
    rerun_trigger: str,
    document_count: int,
    chunk_count: int,
    last_error: str,
) -> str:
    if outcome == "idle":
        return "No reindex job has been recorded yet."
    if outcome == "rerun_requested":
        requested_trigger = rerun_trigger or trigger
        return (
            f"Reindex is running on backend {backend} and another pass was requested "
            f"with trigger {requested_trigger}."
        )
    if state == "running":
        return f"Reindex is running on backend {backend} with trigger {trigger}."
    if state == "succeeded":
        if document_count == 0:
            return f"Reindex succeeded on backend {backend} but found zero documents to index."
        return (
            f"Reindex succeeded on backend {backend}: indexed {document_count} documents "
            f"into {chunk_count} chunks."
        )
    if state == "failed":
        error_summary = last_error or "unknown error"
        return f"Reindex failed on backend {backend}: {error_summary}."
    return (
        f"Reindex is in state {state} on backend {backend}"
        f"{' with a rerun requested' if rerun_requested else ''}."
    )


def _coerce_optional_str(value: object) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)


def _coerce_optional_backend(value: object) -> str | None:
    if value in {None, ""}:
        return None
    backend = str(value)
    if backend in {"file", "pgvector"}:
        return backend
    return None


def _coerce_optional_int(value: object) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)


def _coerce_reindex_status_snapshot(payload: dict[str, object]) -> ReindexStatusSnapshot:
    default_snapshot = _default_reindex_status_snapshot()
    state = str(payload.get("state", default_snapshot.state))
    if state not in {"idle", "running", "succeeded", "failed"}:
        state = default_snapshot.state

    trigger = str(payload.get("trigger", default_snapshot.trigger))
    backend = str(payload.get("backend", default_snapshot.backend))
    if backend not in {"file", "pgvector"}:
        backend = default_snapshot.backend

    last_error = str(payload.get("last_error", default_snapshot.last_error))
    rerun_requested = bool(payload.get("rerun_requested", default_snapshot.rerun_requested))
    rerun_trigger = str(payload.get("rerun_trigger", default_snapshot.rerun_trigger))
    document_count = int(payload.get("document_count", default_snapshot.document_count))
    chunk_count = int(payload.get("chunk_count", default_snapshot.chunk_count))
    elapsed_ms = int(payload.get("elapsed_ms", default_snapshot.elapsed_ms))
    outcome = str(
        payload.get(
            "outcome",
            _derive_reindex_outcome(state=state, rerun_requested=rerun_requested),
        )
    )
    if outcome not in {"idle", "running", "succeeded", "failed", "rerun_requested"}:
        outcome = _derive_reindex_outcome(state=state, rerun_requested=rerun_requested)

    summary_message = str(
        payload.get(
            "summary_message",
            _build_reindex_summary_message(
                state=state,
                outcome=outcome,
                backend=backend,
                trigger=trigger,
                rerun_requested=rerun_requested,
                rerun_trigger=rerun_trigger,
                document_count=document_count,
                chunk_count=chunk_count,
                last_error=last_error,
            ),
        )
    )

    return ReindexStatusSnapshot(
        state=state,
        trigger=trigger,
        backend=backend,
        history_entry_id=_coerce_optional_int(payload.get("history_entry_id")),
        started_at=_coerce_optional_str(payload.get("started_at")),
        finished_at=_coerce_optional_str(payload.get("finished_at")),
        last_error=last_error,
        rerun_requested=rerun_requested,
        rerun_trigger=rerun_trigger,
        document_count=document_count,
        chunk_count=chunk_count,
        elapsed_ms=elapsed_ms,
        outcome=outcome,
        summary_message=summary_message,
        last_successful_backend=_coerce_optional_backend(
            payload.get("last_successful_backend")
        ),
        last_successful_finished_at=_coerce_optional_str(
            payload.get("last_successful_finished_at")
        ),
    )


def _ensure_reindex_status_initialized() -> None:
    global _reindex_status, _reindex_status_initialized

    snapshot_to_persist: ReindexStatusSnapshot | None = None
    with _reindex_status_lock:
        if _reindex_status_initialized:
            return

        persisted_state = load_runtime_state(REINDEX_STATUS_STATE_KEY)
        if isinstance(persisted_state, dict):
            _reindex_status = _coerce_reindex_status_snapshot(persisted_state)
            if _reindex_status.state == "running":
                _reindex_status = _coerce_reindex_status_snapshot(
                    {
                        **asdict(_reindex_status),
                        "state": "failed",
                        "finished_at": _utc_now_iso(),
                        "last_error": "Process restarted before the background reindex finished.",
                        "rerun_requested": False,
                        "rerun_trigger": "",
                    }
                )
                if _reindex_status.history_entry_id is not None:
                    finalize_reindex_history_entry(
                        _reindex_status.history_entry_id,
                        state=_reindex_status.state,
                        outcome=_reindex_status.outcome,
                        finished_at=str(_reindex_status.finished_at),
                        document_count=_reindex_status.document_count,
                        chunk_count=_reindex_status.chunk_count,
                        elapsed_ms=_reindex_status.elapsed_ms,
                        last_error=_reindex_status.last_error,
                        summary_message=_reindex_status.summary_message,
                    )
                snapshot_to_persist = _reindex_status
        else:
            _reindex_status = _default_reindex_status_snapshot()
            snapshot_to_persist = _reindex_status
        _reindex_status_initialized = True

    if snapshot_to_persist is not None:
        save_runtime_state(REINDEX_STATUS_STATE_KEY, asdict(snapshot_to_persist))


def _set_reindex_status(**changes: object) -> ReindexStatusSnapshot:
    global _reindex_status
    persisted_snapshot: ReindexStatusSnapshot
    with _reindex_status_lock:
        state = str(changes.get("state", _reindex_status.state))
        trigger = str(changes.get("trigger", _reindex_status.trigger))
        backend = str(changes.get("backend", _reindex_status.backend))
        history_entry_id = changes.get("history_entry_id", _reindex_status.history_entry_id)
        started_at = changes.get("started_at", _reindex_status.started_at)
        finished_at = changes.get("finished_at", _reindex_status.finished_at)
        last_error = str(changes.get("last_error", _reindex_status.last_error))
        rerun_requested = bool(changes.get("rerun_requested", _reindex_status.rerun_requested))
        rerun_trigger = str(changes.get("rerun_trigger", _reindex_status.rerun_trigger))
        document_count = int(changes.get("document_count", _reindex_status.document_count))
        chunk_count = int(changes.get("chunk_count", _reindex_status.chunk_count))
        elapsed_ms = int(changes.get("elapsed_ms", _reindex_status.elapsed_ms))
        outcome = str(
            changes.get(
                "outcome",
                _derive_reindex_outcome(state=state, rerun_requested=rerun_requested),
            )
        )
        last_successful_backend = changes.get(
            "last_successful_backend",
            _reindex_status.last_successful_backend,
        )
        last_successful_finished_at = changes.get(
            "last_successful_finished_at",
            _reindex_status.last_successful_finished_at,
        )
        summary_message = str(
            changes.get(
                "summary_message",
                _build_reindex_summary_message(
                    state=state,
                    outcome=outcome,
                    backend=backend,
                    trigger=trigger,
                    rerun_requested=rerun_requested,
                    rerun_trigger=rerun_trigger,
                    document_count=document_count,
                    chunk_count=chunk_count,
                    last_error=last_error,
                ),
            )
        )
        _reindex_status = ReindexStatusSnapshot(
            state=state,
            trigger=trigger,
            backend=backend,
            history_entry_id=(
                None if history_entry_id is None else int(history_entry_id)
            ),
            started_at=started_at,
            finished_at=finished_at,
            last_error=last_error,
            rerun_requested=rerun_requested,
            rerun_trigger=rerun_trigger,
            document_count=document_count,
            chunk_count=chunk_count,
            elapsed_ms=elapsed_ms,
            outcome=outcome,
            summary_message=summary_message,
            last_successful_backend=(
                None if last_successful_backend is None else str(last_successful_backend)
            ),
            last_successful_finished_at=(
                None
                if last_successful_finished_at is None
                else str(last_successful_finished_at)
            ),
        )
        persisted_snapshot = _reindex_status

    save_runtime_state(REINDEX_STATUS_STATE_KEY, asdict(persisted_snapshot))
    return persisted_snapshot


def get_reindex_status() -> ReindexStatusSnapshot:
    _ensure_reindex_status_initialized()
    with _reindex_status_lock:
        return ReindexStatusSnapshot(**_reindex_status.__dict__)


def get_reindex_history(limit: int = 20) -> tuple[ReindexHistoryEntry, ...]:
    return list_reindex_history_entries(limit=limit)


def consume_rerun_request() -> str:
    _ensure_reindex_status_initialized()
    with _reindex_status_lock:
        if not _reindex_status.rerun_requested:
            return ""
        rerun_trigger = _reindex_status.rerun_trigger or _reindex_status.trigger
        _set_reindex_status(rerun_requested=False, rerun_trigger="")
        return rerun_trigger


def start_reindex_job(trigger: str = "manual") -> ReindexStartResult:
    _ensure_reindex_status_initialized()
    active_storage_backend = get_active_storage_backend()
    with _reindex_status_lock:
        if _reindex_status.state == "running":
            status_snapshot = _set_reindex_status(
                rerun_requested=True,
                rerun_trigger=trigger,
            )
            logger.info(
                "Marked reindex rerun as requested while another reindex is running.",
                extra={
                    "event": "index_rebuild_rerun_requested",
                    "context": {
                        "trigger": trigger,
                        "current_trigger": status_snapshot.trigger,
                        "state": status_snapshot.state,
                        "backend": status_snapshot.backend,
                        "outcome": status_snapshot.outcome,
                        "summary_message": status_snapshot.summary_message,
                        "active_storage_backend": active_storage_backend,
                        "rerun_requested": status_snapshot.rerun_requested,
                    },
                },
            )
            return ReindexStartResult(
                accepted=False,
                status_snapshot=ReindexStatusSnapshot(**status_snapshot.__dict__),
            )

        started_at = _utc_now_iso()
        history_entry_id = create_reindex_history_entry(
            trigger=trigger,
            backend=active_storage_backend,
            state="running",
            outcome="running",
            started_at=started_at,
            summary_message=f"Reindex is running on backend {active_storage_backend} with trigger {trigger}.",
        )
        status_snapshot = _set_reindex_status(
            state="running",
            trigger=trigger,
            backend=active_storage_backend,
            history_entry_id=history_entry_id,
            started_at=started_at,
            finished_at=None,
            last_error="",
            rerun_requested=False,
            rerun_trigger="",
            document_count=0,
            chunk_count=0,
            elapsed_ms=0,
        )

    logger.info(
        "Accepted reindex job start.",
        extra={
            "event": "index_rebuild_start_accepted",
            "context": {
                "trigger": trigger,
                "state": status_snapshot.state,
                "backend": status_snapshot.backend,
                "outcome": status_snapshot.outcome,
                "summary_message": status_snapshot.summary_message,
                "started_at": status_snapshot.started_at,
                "active_storage_backend": active_storage_backend,
            },
        },
    )
    return ReindexStartResult(accepted=True, status_snapshot=status_snapshot)


def ensure_index_loaded() -> tuple:
    active_storage_backend = get_active_storage_backend()
    warmup_result = get_chunk_storage().prepare_runtime()
    if warmup_result.loaded_into_memory:
        logger.info(
            "Index loaded into memory.",
            extra={
                "event": "index_loaded",
                "context": {
                    "chunk_count": warmup_result.chunk_count,
                    "active_storage_backend": active_storage_backend,
                    "loaded_into_memory": True,
                },
            },
        )
    else:
        # pgvector runtime should prepare the DB path without pretending chunks were hydrated locally.
        logger.info(
            "Storage runtime prepared without loading chunks into memory.",
            extra={
                "event": "storage_runtime_prepared",
                "context": {
                    "chunk_count": warmup_result.chunk_count,
                    "active_storage_backend": active_storage_backend,
                    "loaded_into_memory": False,
                },
            },
        )
    return ()


def rebuild_index(
    trigger: str = "manual",
    *,
    started_at_iso: str | None = None,
    assume_running: bool = False,
) -> ReindexResult:
    _ensure_reindex_status_initialized()
    started_at = perf_counter()
    active_storage_backend = get_active_storage_backend()
    chunk_storage = get_chunk_storage()
    if started_at_iso is None:
        started_at_iso = _utc_now_iso()
    if not assume_running:
        history_entry_id = create_reindex_history_entry(
            trigger=trigger,
            backend=active_storage_backend,
            state="running",
            outcome="running",
            started_at=started_at_iso,
            summary_message=f"Reindex is running on backend {active_storage_backend} with trigger {trigger}.",
        )
        _set_reindex_status(
            state="running",
            trigger=trigger,
            backend=active_storage_backend,
            history_entry_id=history_entry_id,
            started_at=started_at_iso,
            finished_at=None,
            last_error="",
            rerun_requested=False,
            rerun_trigger="",
            document_count=0,
            chunk_count=0,
            elapsed_ms=0,
        )
    try:
        chunks = chunk_storage.rebuild_chunks()
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        finished_at = _utc_now_iso()
        result = ReindexResult(
            document_count=len({chunk.source_path for chunk in chunks}),
            chunk_count=len(chunks),
            elapsed_ms=elapsed_ms,
        )
        status_snapshot = _set_reindex_status(
            state="succeeded",
            trigger=trigger,
            backend=active_storage_backend,
            started_at=started_at_iso,
            finished_at=finished_at,
            last_error="",
            document_count=result.document_count,
            chunk_count=result.chunk_count,
            elapsed_ms=result.elapsed_ms,
            last_successful_backend=active_storage_backend,
            last_successful_finished_at=finished_at,
        )
        if status_snapshot.history_entry_id is not None:
            finalize_reindex_history_entry(
                status_snapshot.history_entry_id,
                state=status_snapshot.state,
                outcome=status_snapshot.outcome,
                finished_at=finished_at,
                document_count=result.document_count,
                chunk_count=result.chunk_count,
                elapsed_ms=result.elapsed_ms,
                last_error=status_snapshot.last_error,
                summary_message=status_snapshot.summary_message,
            )
        logger.info(
            "Rebuilt processed chunks index.",
            extra={
                "event": "index_rebuilt",
                "context": {
                    "trigger": trigger,
                    "backend": status_snapshot.backend,
                    "outcome": status_snapshot.outcome,
                    "summary_message": status_snapshot.summary_message,
                    "document_count": result.document_count,
                    "chunk_count": result.chunk_count,
                    "elapsed_ms": result.elapsed_ms,
                    "active_storage_backend": active_storage_backend,
                },
            },
        )
        return result
    except Exception as exc:
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        status_snapshot = _set_reindex_status(
            state="failed",
            trigger=trigger,
            backend=active_storage_backend,
            started_at=started_at_iso,
            finished_at=_utc_now_iso(),
            last_error=str(exc),
            document_count=0,
            chunk_count=0,
            elapsed_ms=elapsed_ms,
        )
        if status_snapshot.history_entry_id is not None and status_snapshot.finished_at is not None:
            finalize_reindex_history_entry(
                status_snapshot.history_entry_id,
                state=status_snapshot.state,
                outcome=status_snapshot.outcome,
                finished_at=status_snapshot.finished_at,
                document_count=status_snapshot.document_count,
                chunk_count=status_snapshot.chunk_count,
                elapsed_ms=status_snapshot.elapsed_ms,
                last_error=status_snapshot.last_error,
                summary_message=status_snapshot.summary_message,
            )
        logger.exception(
            "Reindex failed.",
            extra={
                "event": "index_rebuild_failed",
                "context": {
                    "trigger": trigger,
                    "backend": status_snapshot.backend,
                    "outcome": status_snapshot.outcome,
                    "summary_message": status_snapshot.summary_message,
                    "elapsed_ms": elapsed_ms,
                    "active_storage_backend": active_storage_backend,
                    "error_type": type(exc).__name__,
                },
            },
        )
        raise


def ingest_uploaded_document(filename: str, content: bytes) -> UploadedDocumentResult:
    stored_path = save_uploaded_document(filename, content)
    sync_active_storage_source_corpus()
    reindex_result = rebuild_index(trigger="upload")
    result = UploadedDocumentResult(
        original_filename=filename,
        stored_path=stored_path,
        file_type=stored_path.suffix.lower().lstrip(".") or "unknown",
        estimated_chunks=estimate_document_chunk_count(stored_path),
        preview_text=build_document_preview(stored_path),
    )
    logger.info(
        "Uploaded document ingested and indexed.",
        extra={
            "event": "document_ingested",
            "context": {
                "filename": result.original_filename,
                "stored_name": result.stored_path.name,
                "file_type": result.file_type,
                "estimated_chunks": result.estimated_chunks,
                "index_chunk_count": reindex_result.chunk_count,
                "elapsed_ms": reindex_result.elapsed_ms,
            },
        },
    )
    return result


def prepare_uploaded_document(filename: str, content: bytes) -> UploadedDocumentResult:
    stored_path = save_uploaded_document(filename, content)
    sync_active_storage_source_corpus()
    result = UploadedDocumentResult(
        original_filename=filename,
        stored_path=stored_path,
        file_type=stored_path.suffix.lower().lstrip(".") or "unknown",
        estimated_chunks=estimate_document_chunk_count(stored_path),
        preview_text=build_document_preview(stored_path),
    )
    logger.info(
        "Uploaded document saved and prepared for async indexing.",
        extra={
            "event": "document_saved_for_indexing",
            "context": {
                "filename": result.original_filename,
                "stored_name": result.stored_path.name,
                "file_type": result.file_type,
                "estimated_chunks": result.estimated_chunks,
            },
        },
    )
    return result
