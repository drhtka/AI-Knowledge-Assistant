from __future__ import annotations

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str
    ready: bool
    project: str


class SearchRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)


class SearchHit(BaseModel):
    document_id: str
    title: str
    snippet: str
    score: float


class SearchResponse(BaseModel):
    question: str
    top_k: int
    hits: list[SearchHit]


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=3, ge=1, le=10)


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[str]
    chunks: list[SearchHit]
    confidence: float
    latency_ms: int
    answer_mode: str


class IngestResponse(BaseModel):
    status: str
    filename: str
    stored_path: str
    chunks_loaded: int


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
