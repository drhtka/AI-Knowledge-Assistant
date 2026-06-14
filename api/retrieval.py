from __future__ import annotations

import logging
from pathlib import Path
from time import perf_counter

from api.generation import generate_grounded_answer
from api.schemas import AskResponse, RetrievalModeValue, SearchHit, SearchResponse
from api.storage import get_active_storage_backend, get_chunk_storage

logger = logging.getLogger("ai_knowledge_assistant.retrieval")


def search(question: str, top_k: int, retrieval_mode: RetrievalModeValue = "auto") -> SearchResponse:
    started_at = perf_counter()
    active_storage_backend = get_active_storage_backend()
    try:
        chunk_storage = get_chunk_storage()
        ranked_result = chunk_storage.rank_chunks(
            question=question,
            top_k=top_k,
            mode=retrieval_mode,
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
            hits=hits,
        )
        latency_ms = int((perf_counter() - started_at) * 1000)
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
                    "hit_count": len(hits),
                    "latency_ms": latency_ms,
                },
            },
        )
        return response
    except Exception as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
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
    started_at = perf_counter()
    try:
        result = search(question=question, top_k=top_k, retrieval_mode=retrieval_mode)
        generated = generate_grounded_answer(question=question, hits=result.hits)
        latency_ms = int((perf_counter() - started_at) * 1000)

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
                    "hit_count": len(result.hits),
                    "latency_ms": latency_ms,
                    "answer_mode": generated.answer_mode,
                },
            },
        )
        return response
    except Exception as exc:
        latency_ms = int((perf_counter() - started_at) * 1000)
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
