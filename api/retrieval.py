from __future__ import annotations

from api.ingestion import load_chunks
from api.schemas import AskResponse, SearchHit, SearchResponse
from api.vector_search import rank_chunks_by_similarity


def search(question: str, top_k: int) -> SearchResponse:
    hits = [
        SearchHit(
            document_id=chunk.document_id,
            title=chunk.title,
            snippet=chunk.content,
            score=round(score, 3),
        )
        for chunk, score in rank_chunks_by_similarity(question=question, chunks=load_chunks())[:top_k]
    ]

    return SearchResponse(question=question, top_k=top_k, hits=hits)


def ask(question: str, top_k: int) -> AskResponse:
    result = search(question=question, top_k=top_k)
    if not result.hits:
        return AskResponse(
            question=question,
            answer="No grounded answer yet. Add relevant documents or improve retrieval first.",
            sources=[],
            chunks=[],
        )

    answer = " ".join(hit.snippet for hit in result.hits[:2])
    return AskResponse(
        question=question,
        answer=answer,
        sources=[hit.title for hit in result.hits],
        chunks=result.hits,
    )
