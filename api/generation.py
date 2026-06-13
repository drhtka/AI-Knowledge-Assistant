from __future__ import annotations

from dataclasses import dataclass

from api.schemas import SearchHit

MIN_TOP_SCORE_FOR_GROUNDED_ANSWER = 0.12
MAX_SNIPPET_CHARS = 280


@dataclass(frozen=True)
class GroundedAnswerResult:
    answer: str
    confidence: float
    answer_mode: str


def _truncate(text: str, limit: int = MAX_SNIPPET_CHARS) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}..."


def generate_grounded_answer(question: str, hits: list[SearchHit]) -> GroundedAnswerResult:
    normalized_question = " ".join(question.split())

    if not hits:
        return GroundedAnswerResult(
            answer="No grounded answer yet. Add relevant documents or improve retrieval first.",
            confidence=0.0,
            answer_mode="no_context",
        )

    top_score = hits[0].score
    if top_score < MIN_TOP_SCORE_FOR_GROUNDED_ANSWER:
        return GroundedAnswerResult(
            answer=(
                "I found weak context for this question. "
                f"Please add more relevant documents or rephrase: '{_truncate(normalized_question, 120)}'."
            ),
            confidence=round(top_score, 3),
            answer_mode="weak_context_fallback",
        )

    # Keep the answer grounded by summarizing only top retrieved snippets.
    top_hits = hits[:2]
    evidence = " ".join(_truncate(hit.snippet) for hit in top_hits)
    return GroundedAnswerResult(
        answer=evidence,
        confidence=round(top_score, 3),
        answer_mode="grounded_extract",
    )
