from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
from threading import Lock
from typing import Protocol

from api.ingestion import LoadedChunk, build_processed_chunks, clear_chunks_cache, load_chunks
from api.schemas import RetrievalModeValue, StorageBackendValue
from api.settings import CHUNK_STORAGE_BACKEND
from api.storage_pgvector import PgvectorChunkStorage, build_pgvector_storage
from api.vector_search import rank_chunks_by_similarity

logger = logging.getLogger("ai_knowledge_assistant.storage")
AVAILABLE_STORAGE_BACKENDS: tuple[StorageBackendValue, ...] = ("file", "pgvector")
_storage_backend_lock = Lock()


class ChunkStorage(Protocol):
    def load_chunks(self) -> tuple[LoadedChunk, ...]:
        ...

    def rebuild_chunks(self) -> tuple[LoadedChunk, ...]:
        ...

    def rank_chunks(self, question: str, top_k: int, mode: RetrievalModeValue) -> list[tuple[LoadedChunk, float]]:
        ...

    def clear_cache(self) -> None:
        ...


@dataclass(frozen=True)
class FileChunkStorage:
    def load_chunks(self) -> tuple[LoadedChunk, ...]:
        return load_chunks()

    def rebuild_chunks(self) -> tuple[LoadedChunk, ...]:
        clear_chunks_cache()
        chunks = build_processed_chunks()
        clear_chunks_cache()
        return chunks

    def rank_chunks(self, question: str, top_k: int, mode: RetrievalModeValue) -> list[tuple[LoadedChunk, float]]:
        return rank_chunks_by_similarity(
            question=question,
            chunks=self.load_chunks(),
            mode=mode,
        )[:top_k]

    def clear_cache(self) -> None:
        clear_chunks_cache()


def _normalize_storage_backend(value: str) -> StorageBackendValue:
    backend = value.strip().lower()
    if backend in AVAILABLE_STORAGE_BACKENDS:
        return backend
    raise ValueError(
        f"Unsupported chunk storage backend: {value!r}. "
        "Expected one of: 'file', 'pgvector'."
    )


_default_storage_backend: StorageBackendValue = _normalize_storage_backend(CHUNK_STORAGE_BACKEND)
_current_storage_backend: StorageBackendValue = _default_storage_backend


def get_active_storage_backend() -> StorageBackendValue:
    with _storage_backend_lock:
        return _current_storage_backend


def get_storage_backend_config() -> dict[str, object]:
    current_backend = get_active_storage_backend()
    config: dict[str, object] = {
        "current_backend": current_backend,
        "default_backend": _default_storage_backend,
        "available_backends": list(AVAILABLE_STORAGE_BACKENDS),
        "runtime_override_active": current_backend != _default_storage_backend,
    }
    config.update(get_active_storage_backend_status())
    return config


def get_active_storage_backend_status() -> dict[str, object]:
    current_backend = get_active_storage_backend()
    if current_backend == "file":
        return {
            "active_backend_ready": True,
            "active_backend_can_connect": True,
            "active_backend_retrieval_ready": True,
            "active_backend_message": "file backend is ready for retrieval requests.",
        }

    pgvector_storage = _build_chunk_storage("pgvector")
    if not isinstance(pgvector_storage, PgvectorChunkStorage):
        raise TypeError("Expected PgvectorChunkStorage for the 'pgvector' backend.")
    return pgvector_storage.get_readiness_status()


def set_active_storage_backend(backend: StorageBackendValue) -> dict[str, object]:
    global _current_storage_backend
    normalized_backend = _normalize_storage_backend(backend)
    with _storage_backend_lock:
        previous_backend = _current_storage_backend
        _current_storage_backend = normalized_backend

    logger.info(
        "Storage backend runtime selector updated.",
        extra={
            "event": "storage_backend_selected",
            "context": {
                "previous_backend": previous_backend,
                "current_backend": normalized_backend,
                "default_backend": _default_storage_backend,
                "runtime_override_active": normalized_backend != _default_storage_backend,
            },
        },
    )
    return get_storage_backend_config()


@lru_cache(maxsize=2)
def _build_chunk_storage(backend: str) -> ChunkStorage:
    if backend == "file":
        return FileChunkStorage()
    if backend == "pgvector":
        return build_pgvector_storage()
    raise ValueError(f"Unsupported chunk storage backend: {backend!r}.")


def get_chunk_storage() -> ChunkStorage:
    return _build_chunk_storage(get_active_storage_backend())
