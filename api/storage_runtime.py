from __future__ import annotations

from dataclasses import dataclass

from api.ingestion import LoadedChunk
from api.schemas import RetrievalExecutionIssueValue, RetrievalExecutionPathValue, RetrievalOutcomeValue


@dataclass(frozen=True)
class RankedChunkResult:
    ranked_chunks: list[tuple[LoadedChunk, float]]
    execution_path: RetrievalExecutionPathValue
    used_fallback: bool
    execution_issue: RetrievalExecutionIssueValue
    outcome: RetrievalOutcomeValue
