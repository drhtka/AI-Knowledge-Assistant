from __future__ import annotations

from time import perf_counter

from api.generation import generate_grounded_answer
from api.ingestion import load_chunks
from api.schemas import AskResponse, RetrievalModeValue, SearchHit, SearchResponse
from api.vector_search import rank_chunks_by_similarity


def search(question: str, top_k: int, retrieval_mode: RetrievalModeValue = "auto") -> SearchResponse:
    hits = [
        SearchHit(
            document_id=chunk.document_id,
            title=chunk.title,
            snippet=chunk.content,
            score=round(score, 3),
            file_type=chunk.file_type,
        )
        for chunk, score in rank_chunks_by_similarity(
            question=question,
            chunks=load_chunks(),
            mode=retrieval_mode,
        )[:top_k]
    ]

    return SearchResponse(
        question=question,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
        hits=hits,
    )


def ask(question: str, top_k: int, retrieval_mode: RetrievalModeValue = "auto") -> AskResponse:
    started_at = perf_counter()
    result = search(question=question, top_k=top_k, retrieval_mode=retrieval_mode)
    generated = generate_grounded_answer(question=question, hits=result.hits)
    latency_ms = int((perf_counter() - started_at) * 1000)

    return AskResponse(
        question=question,
        answer=generated.answer,
        sources=[hit.title for hit in result.hits],
        chunks=result.hits,
        retrieval_mode=result.retrieval_mode,
        confidence=generated.confidence,
        latency_ms=latency_ms,
        answer_mode=generated.answer_mode,
    )
