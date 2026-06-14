from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re

from api.chunking_config import get_chunking_config
from api.ingestion import (
    IGNORED_FILENAMES,
    SUPPORTED_EXTENSIONS,
    LoadedChunk,
    build_experiment_chunks,
)
from api.settings import (
    CHUNKING_VERSION,
    RAW_DATA_DIR,
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

    def _validate_identifier(self, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(f"Invalid SQL identifier for pgvector storage: {value!r}")
        return value

    def _chunks_table_name(self) -> str:
        schema_name = self._validate_identifier(self.config.schema_name)
        table_name = self._validate_identifier(self.config.table_name)
        return f"{schema_name}.{table_name}"

    def _meta_table_name(self) -> str:
        schema_name = self._validate_identifier(self.config.schema_name)
        table_name = self._validate_identifier(f"{self.config.table_name}_meta")
        return f"{schema_name}.{table_name}"

    def _connect(self) -> object:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required to use the pgvector storage backend. "
                "Install project dependencies from requirements.txt first."
            ) from exc

        return psycopg.connect(self.config.database_url)

    def _ensure_schema(self, connection: object) -> None:
        chunks_table = self._chunks_table_name()
        schema_name = self._validate_identifier(self.config.schema_name)
        table_name = self._validate_identifier(self.config.table_name)
        meta_table_name = self._validate_identifier(f"{self.config.table_name}_meta")
        index_name = self._validate_identifier(f"{table_name}_source_chunk_idx")

        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {chunks_table} (
                    document_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_path TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    chunk_size_words INTEGER NOT NULL,
                    chunk_overlap_words INTEGER NOT NULL,
                    embedding vector({self.config.embedding_dim}),
                    indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS {index_name}
                ON {chunks_table} (source_path, chunk_index)
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.{meta_table_name} (
                    storage_key TEXT PRIMARY KEY,
                    chunk_size_words INTEGER NOT NULL,
                    chunk_overlap_words INTEGER NOT NULL,
                    chunking_version TEXT NOT NULL,
                    indexed_at TIMESTAMPTZ NOT NULL
                )
                """
            )

    def _iter_supported_raw_files(self) -> list[object]:
        if not RAW_DATA_DIR.exists():
            return []
        return [
            path
            for path in sorted(RAW_DATA_DIR.rglob("*"))
            if path.is_file()
            and path.name not in IGNORED_FILENAMES
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ]

    def _has_stored_chunks(self, connection: object) -> bool:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT EXISTS (SELECT 1 FROM {self._chunks_table_name()} LIMIT 1)")
            row = cursor.fetchone()
        return bool(row and row[0])

    def _is_storage_stale(self, connection: object) -> bool:
        config = get_chunking_config()
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT chunk_size_words, chunk_overlap_words, chunking_version, indexed_at
                FROM {self._meta_table_name()}
                WHERE storage_key = %s
                """,
                ("active",),
            )
            row = cursor.fetchone()

        if row is None:
            return True

        chunk_size_words, chunk_overlap_words, chunking_version, indexed_at = row
        if chunk_size_words != int(config["chunk_size_words"]):
            return True
        if chunk_overlap_words != int(config["chunk_overlap_words"]):
            return True
        if chunking_version != CHUNKING_VERSION:
            return True
        if not self._has_stored_chunks(connection):
            return bool(self._iter_supported_raw_files())

        indexed_at_utc = indexed_at.astimezone(timezone.utc)
        return any(
            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) > indexed_at_utc
            for path in self._iter_supported_raw_files()
        )

    def load_chunks(self) -> tuple[LoadedChunk, ...]:
        with self._connect() as connection:
            self._ensure_schema(connection)
            if self._is_storage_stale(connection):
                return self.rebuild_chunks()

            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        document_id,
                        title,
                        content,
                        source_path,
                        file_type,
                        chunk_index,
                        chunk_size_words,
                        chunk_overlap_words
                    FROM {self._chunks_table_name()}
                    ORDER BY source_path, chunk_index
                    """
                )
                rows = cursor.fetchall()

        return tuple(
            LoadedChunk(
                document_id=row[0],
                title=row[1],
                content=row[2],
                source_path=row[3],
                file_type=row[4],
                chunk_index=row[5],
                chunk_size_words=row[6],
                chunk_overlap_words=row[7],
            )
            for row in rows
        )

    def rebuild_chunks(self) -> tuple[LoadedChunk, ...]:
        config = get_chunking_config()
        chunks = build_experiment_chunks()
        with self._connect() as connection:
            self._ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(f"TRUNCATE TABLE {self._chunks_table_name()}")
                cursor.executemany(
                    f"""
                    INSERT INTO {self._chunks_table_name()} (
                        document_id,
                        title,
                        content,
                        source_path,
                        file_type,
                        chunk_index,
                        chunk_size_words,
                        chunk_overlap_words,
                        embedding,
                        indexed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NULL, NOW())
                    """,
                    [
                        (
                            chunk.document_id,
                            chunk.title,
                            chunk.content,
                            chunk.source_path,
                            chunk.file_type,
                            chunk.chunk_index,
                            chunk.chunk_size_words,
                            chunk.chunk_overlap_words,
                        )
                        for chunk in chunks
                    ],
                )
                cursor.execute(
                    f"""
                    INSERT INTO {self._meta_table_name()} (
                        storage_key,
                        chunk_size_words,
                        chunk_overlap_words,
                        chunking_version,
                        indexed_at
                    ) VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (storage_key) DO UPDATE SET
                        chunk_size_words = EXCLUDED.chunk_size_words,
                        chunk_overlap_words = EXCLUDED.chunk_overlap_words,
                        chunking_version = EXCLUDED.chunking_version,
                        indexed_at = EXCLUDED.indexed_at
                    """,
                    (
                        "active",
                        int(config["chunk_size_words"]),
                        int(config["chunk_overlap_words"]),
                        CHUNKING_VERSION,
                    ),
                )
            connection.commit()
        return chunks

    def clear_cache(self) -> None:
        # The pgvector implementation does not keep a local cache yet.
        return None


def build_pgvector_storage() -> PgvectorChunkStorage:
    return PgvectorChunkStorage.from_settings()
