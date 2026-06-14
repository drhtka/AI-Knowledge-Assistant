from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RetrievalModeValue = Literal["auto", "tfidf", "embeddings"]
ChunkingPresetValue = Literal["baseline_120_30", "legacy_80_20", "small_50_10"]
ReindexStateValue = Literal["idle", "running", "succeeded", "failed"]
StorageBackendValue = Literal["file", "pgvector"]
StorageBackendReadinessValue = Literal["ready", "degraded"]
StorageBackendIssueValue = Literal[
    "none",
    "connection_failed",
    "embedding_stack_unavailable",
    "embedding_model_unavailable",
]
RetrievalExecutionPathValue = Literal[
    "file_native",
    "pgvector_native",
    "pgvector_local_tfidf",
    "pgvector_rescue_fallback",
]
RetrievalExecutionIssueValue = Literal[
    "none",
    "pgvector_unavailable",
    "pgvector_query_failed",
]
RetrievalOutcomeValue = Literal["success", "zero_results", "fallback"]


class HealthResponse(BaseModel):
    status: str
    ready: bool
    project: str
    active_storage_backend: StorageBackendValue
    active_storage_backend_state: StorageBackendReadinessValue
    active_storage_backend_issue: StorageBackendIssueValue
    active_storage_backend_ready: bool
    active_storage_backend_can_connect: bool
    active_storage_backend_retrieval_ready: bool
    active_storage_backend_message: str


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
    active_storage_backend: StorageBackendValue
    retrieval_execution_path: RetrievalExecutionPathValue
    retrieval_used_fallback: bool
    retrieval_execution_issue: RetrievalExecutionIssueValue
    retrieval_outcome: RetrievalOutcomeValue
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
    active_storage_backend: StorageBackendValue
    retrieval_execution_path: RetrievalExecutionPathValue
    retrieval_used_fallback: bool
    retrieval_execution_issue: RetrievalExecutionIssueValue
    retrieval_outcome: RetrievalOutcomeValue
    confidence: float
    latency_ms: int
    answer_mode: str


class IngestResponse(BaseModel):
    status: str
    filename: str
    source_name: str
    file_type: str
    stored_path: str
    estimated_chunks: int
    preview_text: str
    reindex_accepted: bool
    reindex_state: ReindexStateValue
    reindex_started_at: str | None
    reindex_message: str
    rerun_requested: bool


class ChunkingConfigUpdateRequest(BaseModel):
    preset: ChunkingPresetValue


class ChunkingConfigResponse(BaseModel):
    current_preset: ChunkingPresetValue
    chunk_size_words: int
    chunk_overlap_words: int
    available_presets: list[ChunkingPresetValue]
    active_storage_backend: StorageBackendValue
    reindex_accepted: bool
    reindex_state: ReindexStateValue
    reindex_started_at: str | None
    reindex_message: str
    rerun_requested: bool


class StorageConfigUpdateRequest(BaseModel):
    backend: StorageBackendValue


class StorageConfigResponse(BaseModel):
    current_backend: StorageBackendValue
    default_backend: StorageBackendValue
    available_backends: list[StorageBackendValue]
    runtime_override_active: bool
    active_backend_state: StorageBackendReadinessValue
    active_backend_issue: StorageBackendIssueValue
    active_backend_ready: bool
    active_backend_can_connect: bool
    active_backend_retrieval_ready: bool
    active_backend_message: str
    reindex_accepted: bool
    reindex_state: ReindexStateValue
    reindex_started_at: str | None
    reindex_message: str
    rerun_requested: bool


class ReindexResponse(BaseModel):
    status: str
    document_count: int
    chunk_count: int
    elapsed_ms: int
    current_preset: ChunkingPresetValue
    chunk_size_words: int
    chunk_overlap_words: int


class ReindexStartResponse(BaseModel):
    status: str
    accepted: bool
    state: ReindexStateValue
    trigger: str
    active_storage_backend: StorageBackendValue
    started_at: str | None
    message: str
    rerun_requested: bool


class ReindexStatusResponse(BaseModel):
    state: ReindexStateValue
    trigger: str
    active_storage_backend: StorageBackendValue
    started_at: str | None
    finished_at: str | None
    last_error: str
    rerun_requested: bool
    rerun_trigger: str
    document_count: int
    chunk_count: int
    elapsed_ms: int


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
