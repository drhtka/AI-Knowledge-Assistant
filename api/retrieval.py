from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
from threading import RLock
from datetime import datetime, timezone
from time import perf_counter

from api.generation import generate_grounded_answer
from api.runtime_state_store import (
    RETRIEVAL_RUNTIME_SNAPSHOT_STATE_KEY,
    load_runtime_state,
    save_runtime_state,
)
from api.schemas import AskResponse, RetrievalModeValue, SearchHit, SearchResponse
from api.storage import get_active_storage_backend, get_chunk_storage

logger = logging.getLogger("ai_knowledge_assistant.retrieval")


@dataclass(frozen=True)
class RetrievalRuntimeSnapshot:
    available: bool
    request_kind: str
    status: str
    question_length: int
    retrieval_mode: str
    active_storage_backend: str
    retrieval_execution_path: str
    retrieval_execution_issue: str
    retrieval_outcome: str
    retrieval_summary_message: str
    hit_count: int
    latency_ms: int
    updated_at: str | None
    error_type: str


_retrieval_runtime_lock = RLock()
_retrieval_runtime_initialized = False
_retrieval_runtime_snapshot = RetrievalRuntimeSnapshot(
    available=False,
    request_kind="none",
    status="idle",
    question_length=0,
    retrieval_mode="auto",
    active_storage_backend="file",
    retrieval_execution_path="none",
    retrieval_execution_issue="none",
    retrieval_outcome="none",
    retrieval_summary_message="No retrieval requests have been recorded yet.",
    hit_count=0,
    latency_ms=0,
    updated_at=None,
    error_type="",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_retrieval_runtime_snapshot() -> RetrievalRuntimeSnapshot:
    return RetrievalRuntimeSnapshot(
        available=False,
        request_kind="none",
        status="idle",
        question_length=0,
        retrieval_mode="auto",
        active_storage_backend=get_active_storage_backend(),
        retrieval_execution_path="none",
        retrieval_execution_issue="none",
        retrieval_outcome="none",
        retrieval_summary_message="No retrieval requests have been recorded yet.",
        hit_count=0,
        latency_ms=0,
        updated_at=None,
        error_type="",
    )


def _coerce_optional_str(value: object) -> str | None:
    if value in {None, ""}:
        return None
    return str(value)


def _coerce_retrieval_runtime_snapshot(payload: dict[str, object]) -> RetrievalRuntimeSnapshot:
    default_snapshot = _default_retrieval_runtime_snapshot()
    active_storage_backend = str(
        payload.get("active_storage_backend", default_snapshot.active_storage_backend)
    )
    if active_storage_backend not in {"file", "pgvector"}:
        active_storage_backend = default_snapshot.active_storage_backend

    return RetrievalRuntimeSnapshot(
        available=bool(payload.get("available", default_snapshot.available)),
        request_kind=str(payload.get("request_kind", default_snapshot.request_kind)),
        status=str(payload.get("status", default_snapshot.status)),
        question_length=int(payload.get("question_length", default_snapshot.question_length)),
        retrieval_mode=str(payload.get("retrieval_mode", default_snapshot.retrieval_mode)),
        active_storage_backend=active_storage_backend,
        retrieval_execution_path=str(
            payload.get(
                "retrieval_execution_path",
                default_snapshot.retrieval_execution_path,
            )
        ),
        retrieval_execution_issue=str(
            payload.get(
                "retrieval_execution_issue",
                default_snapshot.retrieval_execution_issue,
            )
        ),
        retrieval_outcome=str(
            payload.get("retrieval_outcome", default_snapshot.retrieval_outcome)
        ),
        retrieval_summary_message=str(
            payload.get(
                "retrieval_summary_message",
                default_snapshot.retrieval_summary_message,
            )
        ),
        hit_count=int(payload.get("hit_count", default_snapshot.hit_count)),
        latency_ms=int(payload.get("latency_ms", default_snapshot.latency_ms)),
        updated_at=_coerce_optional_str(payload.get("updated_at")),
        error_type=str(payload.get("error_type", default_snapshot.error_type)),
    )


def _ensure_retrieval_runtime_initialized() -> None:
    global _retrieval_runtime_initialized, _retrieval_runtime_snapshot

    snapshot_to_persist: RetrievalRuntimeSnapshot | None = None
    with _retrieval_runtime_lock:
        if _retrieval_runtime_initialized:
            return

        persisted_state = load_runtime_state(RETRIEVAL_RUNTIME_SNAPSHOT_STATE_KEY)
        if isinstance(persisted_state, dict):
            _retrieval_runtime_snapshot = _coerce_retrieval_runtime_snapshot(persisted_state)
        else:
            _retrieval_runtime_snapshot = _default_retrieval_runtime_snapshot()
            snapshot_to_persist = _retrieval_runtime_snapshot
        _retrieval_runtime_initialized = True

    if snapshot_to_persist is not None:
        save_runtime_state(
            RETRIEVAL_RUNTIME_SNAPSHOT_STATE_KEY,
            asdict(snapshot_to_persist),
        )


def _set_retrieval_runtime_snapshot(**changes: object) -> RetrievalRuntimeSnapshot:
    global _retrieval_runtime_snapshot
    persisted_snapshot: RetrievalRuntimeSnapshot
    with _retrieval_runtime_lock:
        _retrieval_runtime_snapshot = RetrievalRuntimeSnapshot(
            available=bool(changes.get("available", _retrieval_runtime_snapshot.available)),
            request_kind=str(changes.get("request_kind", _retrieval_runtime_snapshot.request_kind)),
            status=str(changes.get("status", _retrieval_runtime_snapshot.status)),
            question_length=int(changes.get("question_length", _retrieval_runtime_snapshot.question_length)),
            retrieval_mode=str(changes.get("retrieval_mode", _retrieval_runtime_snapshot.retrieval_mode)),
            active_storage_backend=str(
                changes.get(
                    "active_storage_backend",
                    _retrieval_runtime_snapshot.active_storage_backend,
                )
            ),
            retrieval_execution_path=str(
                changes.get(
                    "retrieval_execution_path",
                    _retrieval_runtime_snapshot.retrieval_execution_path,
                )
            ),
            retrieval_execution_issue=str(
                changes.get(
                    "retrieval_execution_issue",
                    _retrieval_runtime_snapshot.retrieval_execution_issue,
                )
            ),
            retrieval_outcome=str(
                changes.get("retrieval_outcome", _retrieval_runtime_snapshot.retrieval_outcome)
            ),
            retrieval_summary_message=str(
                changes.get(
                    "retrieval_summary_message",
                    _retrieval_runtime_snapshot.retrieval_summary_message,
                )
            ),
            hit_count=int(changes.get("hit_count", _retrieval_runtime_snapshot.hit_count)),
            latency_ms=int(changes.get("latency_ms", _retrieval_runtime_snapshot.latency_ms)),
            updated_at=changes.get("updated_at", _retrieval_runtime_snapshot.updated_at),
            error_type=str(changes.get("error_type", _retrieval_runtime_snapshot.error_type)),
        )
        persisted_snapshot = _retrieval_runtime_snapshot

    # Persist the latest retrieval snapshot so runtime observability survives process restarts.
    save_runtime_state(
        RETRIEVAL_RUNTIME_SNAPSHOT_STATE_KEY,
        asdict(persisted_snapshot),
    )
    return persisted_snapshot


def get_retrieval_runtime_snapshot() -> RetrievalRuntimeSnapshot:
    _ensure_retrieval_runtime_initialized()
    with _retrieval_runtime_lock:
        return RetrievalRuntimeSnapshot(**_retrieval_runtime_snapshot.__dict__)


def _build_retrieval_summary_message(
    *,
    active_storage_backend: str,
    execution_path: str,
    outcome: str,
    execution_issue: str,
) -> str:
    if execution_path == "file_native":
        if outcome == "zero_results":
            return "File backend completed normally but returned zero results."
        return "File backend served the retrieval request successfully."

    if execution_path == "pgvector_native":
        if outcome == "zero_results":
            return "pgvector DB-first retrieval completed normally but returned zero results."
        return "pgvector DB-first retrieval served the request successfully."

    if execution_path == "pgvector_local_tfidf":
        if outcome == "zero_results":
            return "pgvector backend used the local tfidf path and returned zero results."
        return "pgvector backend used the expected local tfidf path successfully."

    if execution_path == "pgvector_rescue_fallback":
        return (
            "pgvector retrieval used the rescue fallback to local ranking"
            f" because of {execution_issue}."
        )

    return (
        f"Retrieval finished on backend {active_storage_backend} with "
        f"path={execution_path} and outcome={outcome}."
    )


def search(question: str, top_k: int, retrieval_mode: RetrievalModeValue = "auto") -> SearchResponse:
    _ensure_retrieval_runtime_initialized()
    started_at = perf_counter()
    active_storage_backend = get_active_storage_backend()
    try:
        chunk_storage = get_chunk_storage()
        ranked_result = chunk_storage.rank_chunks(
            question=question,
            top_k=top_k,
            mode=retrieval_mode,
        )
        retrieval_summary_message = _build_retrieval_summary_message(
            active_storage_backend=active_storage_backend,
            execution_path=ranked_result.execution_path,
            outcome=ranked_result.outcome,
            execution_issue=ranked_result.execution_issue,
        )

        hits = [
            SearchHit(
                document_id=chunk.document_id,
                title=chunk.title,
                snippet=chunk.content,
                score=round(score, 3),
                file_type=chunk.file_type,
                source_name=Path(chunk.source_path).name,
                chunk_index=chunk.chunk_index,
            )
            for chunk, score in ranked_result.ranked_chunks
        ]

        response = SearchResponse(
            question=question,
            top_k=top_k,
            retrieval_mode=retrieval_mode,
            active_storage_backend=active_storage_backend,
            retrieval_execution_path=ranked_result.execution_path,
            retrieval_used_fallback=ranked_result.used_fallback,
            retrieval_execution_issue=ranked_result.execution_issue,
            retrieval_outcome=ranked_result.outcome,
            retrieval_summary_message=retrieval_summary_message,
            hits=hits,
        )
        latency_ms = int((perf_counter() - started_at) * 1000)
        _set_retrieval_runtime_snapshot(
            available=True,
            request_kind="search",
            status="completed",
            question_length=len(question.strip()),
            retrieval_mode=retrieval_mode,
            active_storage_backend=active_storage_backend,
            retrieval_execution_path=ranked_result.execution_path,
            retrieval_execution_issue=ranked_result.execution_issue,
            retrieval_outcome=ranked_result.outcome,
            retrieval_summary_message=retrieval_summary_message,
            hit_count=len(hits),
            latency_ms=latency_ms,
            updated_at=_utc_now_iso(),
            error_type="",
        )
        logger.info(
            "Search request completed.",
            extra={
                "event": "search_request_completed",
                "context": {
                    "question_length": len(question.strip()),
                    "top_k": top_k,
                    "retrieval_mode": retrieval_mode,
                    "active_storage_backend": active_storage_backend,
                    "retrieval_execution_path": ranked_result.execution_path,
                    "retrieval_used_fallback": ranked_result.used_fallback,
                    "retrieval_execution_issue": ranked_result.execution_issue,
                    "retrieval_outcome": ranked_result.outcome,
                    "retrieval_summary_message": retrieval_summary_message,
                    "hit_count": len(hits),
                    "latency_ms": latency_ms,
                },
            },
        )
        return response
    except Exception as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
        _set_retrieval_runtime_snapshot(
            available=True,
            request_kind="search",
            status="failed",
            question_length=len(question.strip()),
            retrieval_mode=retrieval_mode,
            active_storage_backend=active_storage_backend,
            retrieval_execution_path="unknown",
            retrieval_execution_issue="none",
            retrieval_outcome="none",
            retrieval_summary_message="Search request failed before producing a retrieval result.",
            hit_count=0,
            latency_ms=latency_ms,
            updated_at=_utc_now_iso(),
            error_type=type(exc).__name__,
        )
        logger.exception(
            "Search request failed.",
            extra={
                "event": "search_request_failed",
                "context": {
                    "question_length": len(question.strip()),
                    "top_k": top_k,
                    "retrieval_mode": retrieval_mode,
                    "active_storage_backend": active_storage_backend,
                    "latency_ms": latency_ms,
                    "error_type": type(exc).__name__,
                },
            },
        )
        raise


def ask(question: str, top_k: int, retrieval_mode: RetrievalModeValue = "auto") -> AskResponse:
    _ensure_retrieval_runtime_initialized()
    started_at = perf_counter()
    active_storage_backend = get_active_storage_backend()
    try:
        result = search(question=question, top_k=top_k, retrieval_mode=retrieval_mode)
        generated = generate_grounded_answer(question=question, hits=result.hits)
        latency_ms = int((perf_counter() - started_at) * 1000)
        _set_retrieval_runtime_snapshot(
            available=True,
            request_kind="ask",
            status="completed",
            question_length=len(question.strip()),
            retrieval_mode=result.retrieval_mode,
            active_storage_backend=result.active_storage_backend,
            retrieval_execution_path=result.retrieval_execution_path,
            retrieval_execution_issue=result.retrieval_execution_issue,
            retrieval_outcome=result.retrieval_outcome,
            retrieval_summary_message=result.retrieval_summary_message,
            hit_count=len(result.hits),
            latency_ms=latency_ms,
            updated_at=_utc_now_iso(),
            error_type="",
        )

        response = AskResponse(
            question=question,
            answer=generated.answer,
            sources=[hit.title for hit in result.hits],
            chunks=result.hits,
            retrieval_mode=result.retrieval_mode,
            active_storage_backend=result.active_storage_backend,
            retrieval_execution_path=result.retrieval_execution_path,
            retrieval_used_fallback=result.retrieval_used_fallback,
            retrieval_execution_issue=result.retrieval_execution_issue,
            retrieval_outcome=result.retrieval_outcome,
            retrieval_summary_message=result.retrieval_summary_message,
            confidence=generated.confidence,
            latency_ms=latency_ms,
            answer_mode=generated.answer_mode,
        )
        logger.info(
            "Ask request completed.",
            extra={
                "event": "ask_request_completed",
                "context": {
                    "question_length": len(question.strip()),
                    "top_k": top_k,
                    "retrieval_mode": result.retrieval_mode,
                    "active_storage_backend": result.active_storage_backend,
                    "retrieval_execution_path": result.retrieval_execution_path,
                    "retrieval_used_fallback": result.retrieval_used_fallback,
                    "retrieval_execution_issue": result.retrieval_execution_issue,
                    "retrieval_outcome": result.retrieval_outcome,
                    "retrieval_summary_message": result.retrieval_summary_message,
                    "hit_count": len(result.hits),
                    "latency_ms": latency_ms,
                    "answer_mode": generated.answer_mode,
                },
            },
        )
        return response
    except Exception as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
        _set_retrieval_runtime_snapshot(
            available=True,
            request_kind="ask",
            status="failed",
            question_length=len(question.strip()),
            retrieval_mode=retrieval_mode,
            active_storage_backend=active_storage_backend,
            retrieval_execution_path="unknown",
            retrieval_execution_issue="none",
            retrieval_outcome="none",
            retrieval_summary_message="Ask request failed before producing a grounded answer.",
            hit_count=0,
            latency_ms=latency_ms,
            updated_at=_utc_now_iso(),
            error_type=type(exc).__name__,
        )
        logger.exception(
            "Ask request failed.",
            extra={
                "event": "ask_request_failed",
                "context": {
                    "question_length": len(question.strip()),
                    "top_k": top_k,
                    "retrieval_mode": retrieval_mode,
                    "active_storage_backend": get_active_storage_backend(),
                    "retrieval_execution_path": "unknown",
                    "retrieval_used_fallback": False,
                    "retrieval_execution_issue": "none",
                    "latency_ms": latency_ms,
                    "error_type": type(exc).__name__,
                },
            },
        )
        raise
