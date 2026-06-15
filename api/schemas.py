from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RetrievalModeValue = Literal["auto", "tfidf", "embeddings"]
ChunkingPresetValue = Literal["baseline_120_30", "legacy_80_20", "small_50_10"]
ReindexStateValue = Literal["idle", "running", "succeeded", "failed"]
StorageBackendValue = Literal["file", "pgvector"]
ReindexOutcomeValue = Literal["idle", "running", "succeeded", "failed", "rerun_requested"]
StorageBackendReadinessValue = Literal["ready", "degraded"]
IndexingPreflightValue = Literal["native", "degraded", "blocked"]
StorageBackendIssueValue = Literal[
    "none",
    "connection_failed",
    "embedding_stack_unavailable",
    "embedding_model_unavailable",
    "metadata_snapshot_missing",
    "metadata_snapshot_empty",
    "metadata_snapshot_stale",
    "metadata_snapshot_incomplete",
]
RetrievalExecutionPathValue = Literal[
    "file_native",
    "pgvector_native",
    "pgvector_lexical",
    "pgvector_lexical_fallback",
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
    active_storage_backend_summary_message: str
    active_storage_backend_state: StorageBackendReadinessValue
    active_storage_backend_issue: StorageBackendIssueValue
    active_storage_backend_ready: bool
    active_storage_backend_can_connect: bool
    active_storage_backend_retrieval_ready: bool
    active_storage_backend_indexing_ready: bool
    active_storage_backend_indexing_preflight: IndexingPreflightValue
    active_storage_backend_message: str
    active_storage_backend_indexing_message: str
    pgvector_metadata_snapshot: "PgvectorMetadataSnapshotResponse | None" = None


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
    retrieval_summary_message: str
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
    retrieval_summary_message: str
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
    active_backend_summary_message: str
    active_backend_state: StorageBackendReadinessValue
    active_backend_issue: StorageBackendIssueValue
    active_backend_ready: bool
    active_backend_can_connect: bool
    active_backend_retrieval_ready: bool
    active_backend_indexing_ready: bool
    active_backend_indexing_preflight: IndexingPreflightValue
    active_backend_message: str
    active_backend_indexing_message: str
    pgvector_metadata_snapshot: "PgvectorMetadataSnapshotResponse | None" = None
    reindex_accepted: bool
    reindex_state: ReindexStateValue
    reindex_started_at: str | None
    reindex_message: str
    rerun_requested: bool


class RetrievalRuntimeSnapshotResponse(BaseModel):
    available: bool
    request_kind: str
    status: str
    question_length: int
    retrieval_mode: RetrievalModeValue
    active_storage_backend: StorageBackendValue
    retrieval_execution_path: str
    retrieval_execution_issue: str
    retrieval_outcome: str
    retrieval_summary_message: str
    hit_count: int
    latency_ms: int
    updated_at: str | None
    error_type: str


class RuntimeObservabilityResponse(BaseModel):
    active_storage_backend: StorageBackendValue
    active_backend_summary_message: str
    active_backend_state: StorageBackendReadinessValue
    active_backend_issue: StorageBackendIssueValue
    active_backend_ready: bool
    active_backend_can_connect: bool
    active_backend_retrieval_ready: bool
    active_backend_indexing_ready: bool
    active_backend_indexing_preflight: IndexingPreflightValue
    active_backend_message: str
    active_backend_indexing_message: str
    pgvector_metadata_snapshot: "PgvectorMetadataSnapshotResponse | None" = None
    reindex_state: ReindexStateValue
    reindex_trigger: str
    reindex_backend: StorageBackendValue
    reindex_started_at: str | None
    reindex_finished_at: str | None
    reindex_rerun_requested: bool
    reindex_rerun_trigger: str
    reindex_outcome: ReindexOutcomeValue
    reindex_summary_message: str
    reindex_document_count: int
    reindex_chunk_count: int
    reindex_elapsed_ms: int
    reindex_last_error: str
    reindex_last_successful_backend: StorageBackendValue | None
    reindex_last_successful_finished_at: str | None
    last_retrieval: RetrievalRuntimeSnapshotResponse


class ReindexResponse(BaseModel):
    status: str
    document_count: int
    chunk_count: int
    elapsed_ms: int
    current_preset: ChunkingPresetValue
    chunk_size_words: int
    chunk_overlap_words: int


class PgvectorMetadataSnapshotResponse(BaseModel):
    chunk_size_words: int
    chunk_overlap_words: int
    chunking_version: str
    indexed_at: str
    chunk_count: int
    source_file_count: int
    embedding_document_count: int
    lexical_document_count: int


class ReindexStartResponse(BaseModel):
    status: str
    accepted: bool
    state: ReindexStateValue
    trigger: str
    active_storage_backend: StorageBackendValue
    started_at: str | None
    finished_at: str | None
    rerun_trigger: str
    outcome: ReindexOutcomeValue
    summary_message: str
    last_successful_backend: StorageBackendValue | None
    last_successful_finished_at: str | None
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
    outcome: ReindexOutcomeValue
    summary_message: str
    last_successful_backend: StorageBackendValue | None
    last_successful_finished_at: str | None
    document_count: int
    chunk_count: int
    elapsed_ms: int


class ReindexHistoryEntryResponse(BaseModel):
    history_entry_id: int
    trigger: str
    active_storage_backend: StorageBackendValue
    state: ReindexStateValue
    outcome: ReindexOutcomeValue
    started_at: str
    finished_at: str | None
    summary_message: str
    last_error: str
    document_count: int
    chunk_count: int
    elapsed_ms: int


class ReindexHistoryResponse(BaseModel):
    entries: list[ReindexHistoryEntryResponse]


class RetrievalHistoryEntryResponse(BaseModel):
    history_entry_id: int
    request_kind: str
    status: str
    question_length: int
    retrieval_mode: str
    active_storage_backend: StorageBackendValue
    retrieval_execution_path: str
    retrieval_execution_issue: str
    retrieval_outcome: str
    retrieval_summary_message: str
    hit_count: int
    latency_ms: int
    updated_at: str
    error_type: str


class RetrievalHistoryResponse(BaseModel):
    entries: list[RetrievalHistoryEntryResponse]


class WebSearchHistoryEntryResponse(BaseModel):
    history_entry_id: int
    question_length: int
    top_k: int
    engine: str
    status: str
    hit_count: int
    latency_ms: int
    updated_at: str
    error_type: str


class WebSearchHistoryResponse(BaseModel):
    entries: list[WebSearchHistoryEntryResponse]


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
