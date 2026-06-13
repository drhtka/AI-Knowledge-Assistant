from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RetrievalModeValue = Literal["auto", "tfidf", "embeddings"]
ChunkingPresetValue = Literal["baseline_120_30", "legacy_80_20", "small_50_10"]


class HealthResponse(BaseModel):
    status: str
    ready: bool
    project: str


class SearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)
    retrieval_mode: RetrievalModeValue = "auto"


class SearchHit(BaseModel):
    document_id: str
    title: str
    snippet: str
    score: float
    file_type: str
    source_name: str
    chunk_index: int


class SearchResponse(BaseModel):
    question: str
    top_k: int
    retrieval_mode: RetrievalModeValue
    hits: list[SearchHit]


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)
    retrieval_mode: RetrievalModeValue = "auto"


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[str]
    chunks: list[SearchHit]
    retrieval_mode: RetrievalModeValue
    confidence: float
    latency_ms: int
    answer_mode: str


class IngestResponse(BaseModel):
    status: str
    filename: str
    stored_path: str
    chunks_loaded: int


class ChunkingConfigUpdateRequest(BaseModel):
    preset: ChunkingPresetValue


class ChunkingConfigResponse(BaseModel):
    current_preset: ChunkingPresetValue
    chunk_size_words: int
    chunk_overlap_words: int
    available_presets: list[ChunkingPresetValue]


class WebSearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)


class WebSearchHit(BaseModel):
    title: str
    link: str
    snippet: str
    source: str
    position: int


class WebSearchResponse(BaseModel):
    question: str
    top_k: int
    engine: str
    hits: list[WebSearchHit]
