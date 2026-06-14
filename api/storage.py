from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from api.ingestion import LoadedChunk, build_processed_chunks, clear_chunks_cache, load_chunks
from api.settings import CHUNK_STORAGE_BACKEND
from api.storage_pgvector import build_pgvector_storage


class ChunkStorage(Protocol):
    def load_chunks(self) -> tuple[LoadedChunk, ...]:
        ...

    def rebuild_chunks(self) -> tuple[LoadedChunk, ...]:
        ...

    def rank_chunks_by_embeddings(self, question: str, top_k: int) -> list[tuple[LoadedChunk, float]] | None:
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

    def rank_chunks_by_embeddings(self, _question: str, _top_k: int) -> list[tuple[LoadedChunk, float]] | None:
        return None

    def clear_cache(self) -> None:
        clear_chunks_cache()


@lru_cache(maxsize=1)
def get_chunk_storage() -> ChunkStorage:
    if CHUNK_STORAGE_BACKEND == "file":
        return FileChunkStorage()
    if CHUNK_STORAGE_BACKEND == "pgvector":
        return build_pgvector_storage()
    raise ValueError(
        f"Unsupported chunk storage backend: {CHUNK_STORAGE_BACKEND!r}. "
        "Expected one of: 'file', 'pgvector'."
    )
