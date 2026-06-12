from __future__ import annotations

from api.ingestion import load_chunks
from api.schemas import AskResponse, SearchHit, SearchResponse


def _tokenize(text: str) -> set[str]:
    return {
        token.strip(".,:;!?()[]").lower()
        for token in text.split()
        if token.strip()
    }


def search(question: str, top_k: int) -> SearchResponse:
    query_tokens = _tokenize(question)
    hits: list[SearchHit] = []

    for chunk in load_chunks():
        chunk_tokens = _tokenize(f"{chunk.title} {chunk.content}")
        overlap = len(query_tokens & chunk_tokens)
        if overlap == 0:
            continue

        hits.append(
            SearchHit(
                document_id=chunk.document_id,
                title=chunk.title,
                snippet=chunk.content,
                score=round(overlap / max(len(query_tokens), 1), 3),
            )
        )

    hits.sort(key=lambda item: item.score, reverse=True)
    return SearchResponse(question=question, top_k=top_k, hits=hits[:top_k])


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
