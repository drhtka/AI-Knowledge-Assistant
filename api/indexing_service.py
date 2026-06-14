from __future__ import annotations

from dataclasses import dataclass
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
from api.storage import get_chunk_storage

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
    started_at: str | None
    finished_at: str | None
    last_error: str
    rerun_requested: bool
    rerun_trigger: str
    document_count: int
    chunk_count: int
    elapsed_ms: int


@dataclass(frozen=True)
class ReindexStartResult:
    accepted: bool
    status_snapshot: ReindexStatusSnapshot


_reindex_status_lock = RLock()
_reindex_status = ReindexStatusSnapshot(
    state="idle",
    trigger="startup",
    started_at=None,
    finished_at=None,
    last_error="",
    rerun_requested=False,
    rerun_trigger="",
    document_count=0,
    chunk_count=0,
    elapsed_ms=0,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_reindex_status(**changes: object) -> ReindexStatusSnapshot:
    global _reindex_status
    with _reindex_status_lock:
        _reindex_status = ReindexStatusSnapshot(
            state=str(changes.get("state", _reindex_status.state)),
            trigger=str(changes.get("trigger", _reindex_status.trigger)),
            started_at=changes.get("started_at", _reindex_status.started_at),
            finished_at=changes.get("finished_at", _reindex_status.finished_at),
            last_error=str(changes.get("last_error", _reindex_status.last_error)),
            rerun_requested=bool(changes.get("rerun_requested", _reindex_status.rerun_requested)),
            rerun_trigger=str(changes.get("rerun_trigger", _reindex_status.rerun_trigger)),
            document_count=int(changes.get("document_count", _reindex_status.document_count)),
            chunk_count=int(changes.get("chunk_count", _reindex_status.chunk_count)),
            elapsed_ms=int(changes.get("elapsed_ms", _reindex_status.elapsed_ms)),
        )
        return _reindex_status


def get_reindex_status() -> ReindexStatusSnapshot:
    with _reindex_status_lock:
        return ReindexStatusSnapshot(**_reindex_status.__dict__)


def consume_rerun_request() -> str:
    with _reindex_status_lock:
        if not _reindex_status.rerun_requested:
            return ""
        rerun_trigger = _reindex_status.rerun_trigger or _reindex_status.trigger
        _set_reindex_status(rerun_requested=False, rerun_trigger="")
        return rerun_trigger


def start_reindex_job(trigger: str = "manual") -> ReindexStartResult:
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
                        "rerun_requested": status_snapshot.rerun_requested,
                    },
                },
            )
            return ReindexStartResult(
                accepted=False,
                status_snapshot=ReindexStatusSnapshot(**status_snapshot.__dict__),
            )

        started_at = _utc_now_iso()
        status_snapshot = _set_reindex_status(
            state="running",
            trigger=trigger,
            started_at=started_at,
            finished_at=None,
            last_error="",
            rerun_requested=False,
            rerun_trigger="",
        )

    logger.info(
        "Accepted reindex job start.",
        extra={
            "event": "index_rebuild_start_accepted",
            "context": {
                "trigger": trigger,
                "state": status_snapshot.state,
                "started_at": status_snapshot.started_at,
            },
        },
    )
    return ReindexStartResult(accepted=True, status_snapshot=status_snapshot)


def ensure_index_loaded() -> tuple:
    chunks = get_chunk_storage().load_chunks()
    logger.info(
        "Index loaded into memory.",
        extra={
            "event": "index_loaded",
            "context": {
                "chunk_count": len(chunks),
            },
        },
    )
    return chunks


def rebuild_index(
    trigger: str = "manual",
    *,
    started_at_iso: str | None = None,
    assume_running: bool = False,
) -> ReindexResult:
    started_at = perf_counter()
    chunk_storage = get_chunk_storage()
    if started_at_iso is None:
        started_at_iso = _utc_now_iso()
    if not assume_running:
        _set_reindex_status(
            state="running",
            trigger=trigger,
            started_at=started_at_iso,
            finished_at=None,
            last_error="",
        )
    try:
        chunks = chunk_storage.rebuild_chunks()
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        result = ReindexResult(
            document_count=len({chunk.source_path for chunk in chunks}),
            chunk_count=len(chunks),
            elapsed_ms=elapsed_ms,
        )
        _set_reindex_status(
            state="succeeded",
            trigger=trigger,
            started_at=started_at_iso,
            finished_at=_utc_now_iso(),
            last_error="",
            document_count=result.document_count,
            chunk_count=result.chunk_count,
            elapsed_ms=result.elapsed_ms,
        )
        logger.info(
            "Rebuilt processed chunks index.",
            extra={
                "event": "index_rebuilt",
                "context": {
                    "trigger": trigger,
                    "document_count": result.document_count,
                    "chunk_count": result.chunk_count,
                    "elapsed_ms": result.elapsed_ms,
                },
            },
        )
        return result
    except Exception as exc:
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        _set_reindex_status(
            state="failed",
            trigger=trigger,
            started_at=started_at_iso,
            finished_at=_utc_now_iso(),
            last_error=str(exc),
            elapsed_ms=elapsed_ms,
        )
        logger.exception(
            "Reindex failed.",
            extra={
                "event": "index_rebuild_failed",
                "context": {
                    "trigger": trigger,
                    "elapsed_ms": elapsed_ms,
                    "error_type": type(exc).__name__,
                },
            },
        )
        raise


def ingest_uploaded_document(filename: str, content: bytes) -> UploadedDocumentResult:
    stored_path = save_uploaded_document(filename, content)
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
