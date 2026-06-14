from __future__ import annotations

from dataclasses import dataclass

from api.ingestion import LoadedChunk
from api.settings import (
    PGVECTOR_DATABASE_URL,
    PGVECTOR_EMBEDDING_DIM,
    PGVECTOR_SCHEMA,
    PGVECTOR_TABLE,
)


@dataclass(frozen=True)
class PgvectorChunkStorageConfig:
    database_url: str
    schema_name: str
    table_name: str
    embedding_dim: int


@dataclass(frozen=True)
class PgvectorChunkStorage:
    config: PgvectorChunkStorageConfig

    @classmethod
    def from_settings(cls) -> "PgvectorChunkStorage":
        return cls(
            config=PgvectorChunkStorageConfig(
                database_url=PGVECTOR_DATABASE_URL,
                schema_name=PGVECTOR_SCHEMA,
                table_name=PGVECTOR_TABLE,
                embedding_dim=PGVECTOR_EMBEDDING_DIM,
            )
        )

    def load_chunks(self) -> tuple[LoadedChunk, ...]:
        raise NotImplementedError(
            "pgvector storage scaffold is configured, but chunk loading is not implemented yet."
        )

    def rebuild_chunks(self) -> tuple[LoadedChunk, ...]:
        raise NotImplementedError(
            "pgvector storage scaffold is configured, but reindex persistence is not implemented yet."
        )

    def clear_cache(self) -> None:
        # The pgvector implementation does not keep a local cache yet.
        return None


def build_pgvector_storage() -> PgvectorChunkStorage:
    return PgvectorChunkStorage.from_settings()
