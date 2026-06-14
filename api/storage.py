from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from api.ingestion import LoadedChunk, build_processed_chunks, clear_chunks_cache, load_chunks


class ChunkStorage(Protocol):
    def load_chunks(self) -> tuple[LoadedChunk, ...]:
        ...

    def rebuild_chunks(self) -> tuple[LoadedChunk, ...]:
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

    def clear_cache(self) -> None:
        clear_chunks_cache()


_default_chunk_storage: ChunkStorage = FileChunkStorage()


def get_chunk_storage() -> ChunkStorage:
    return _default_chunk_storage
