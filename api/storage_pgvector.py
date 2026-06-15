from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import re
from time import perf_counter

from api.chunking_config import get_chunking_config
from api.embeddings import (
    compose_embedding_text,
    embedding_stack_available,
    encode_query,
    encode_texts,
    get_embedding_model,
    vector_to_pgvector_literal,
)
from api.ingestion import (
    IGNORED_FILENAMES,
    SUPPORTED_EXTENSIONS,
    LoadedChunk,
    build_experiment_chunks,
)
from api.schemas import RetrievalModeValue
from api.settings import (
    CHUNKING_VERSION,
    RAW_DATA_DIR,
    PGVECTOR_DATABASE_URL,
    PGVECTOR_EMBEDDING_DIM,
    PGVECTOR_SCHEMA,
    PGVECTOR_TABLE,
)
from api.storage_runtime import RankedChunkResult, StorageWarmupResult

logger = logging.getLogger("ai_knowledge_assistant.pgvector_storage")


class PgvectorRetrievalUnavailableError(RuntimeError):
    """Raised when pgvector retrieval cannot be used and a lexical DB fallback is needed."""



@dataclass(frozen=True)
class PgvectorChunkStorageConfig:
    database_url: str
    schema_name: str
    table_name: str
    embedding_dim: int


@dataclass(frozen=True)
class PgvectorMetadataSnapshot:
    chunk_size_words: int
    chunk_overlap_words: int
    chunking_version: str
    indexed_at: datetime
    chunk_count: int
    source_file_count: int
    embedding_document_count: int
    lexical_document_count: int

    def to_response_payload(self) -> dict[str, object]:
        return {
            "chunk_size_words": self.chunk_size_words,
            "chunk_overlap_words": self.chunk_overlap_words,
            "chunking_version": self.chunking_version,
            "indexed_at": self.indexed_at.isoformat(),
            "chunk_count": self.chunk_count,
            "source_file_count": self.source_file_count,
            "embedding_document_count": self.embedding_document_count,
            "lexical_document_count": self.lexical_document_count,
        }


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

    def _log_rescue_fallback(
        self,
        *,
        mode: RetrievalModeValue,
        question: str,
        top_k: int,
        latency_ms: float,
        reason: str,
        error: Exception | None = None,
    ) -> None:
        logger.warning(
            "pgvector retrieval fell back to PostgreSQL lexical ranking.",
            extra={
                "event": "pgvector_retrieval_fallback",
                "context": {
                    "mode": mode,
                    "question_length": len(question.strip()),
                    "top_k": top_k,
                    "latency_ms": round(latency_ms, 2),
                    "reason": reason,
                    "error_type": type(error).__name__ if error is not None else "",
                },
            },
            exc_info=error is not None,
        )

    def _log_zero_results(
        self,
        *,
        mode: RetrievalModeValue,
        question: str,
        top_k: int,
        latency_ms: float,
    ) -> None:
        logger.info(
            "pgvector retrieval returned zero results without using local fallback.",
            extra={
                "event": "pgvector_retrieval_zero_results",
                "context": {
                    "mode": mode,
                    "question_length": len(question.strip()),
                    "top_k": top_k,
                    "latency_ms": round(latency_ms, 2),
                },
            },
        )

    def _log_successful_retrieval(
        self,
        *,
        mode: RetrievalModeValue,
        question: str,
        top_k: int,
        hit_count: int,
        latency_ms: float,
    ) -> None:
        logger.info(
            "pgvector retrieval completed successfully.",
            extra={
                "event": "pgvector_retrieval_succeeded",
                "context": {
                    "mode": mode,
                    "question_length": len(question.strip()),
                    "top_k": top_k,
                    "hit_count": hit_count,
                    "latency_ms": round(latency_ms, 2),
                },
            },
        )

    def _rank_chunks_with_lexical_fallback(
        self,
        *,
        question: str,
        top_k: int,
        mode: RetrievalModeValue,
        started_at: float,
        reason: str,
        error: Exception | None = None,
    ) -> RankedChunkResult:
        self._log_rescue_fallback(
            mode=mode,
            question=question,
            top_k=top_k,
            latency_ms=(perf_counter() - started_at) * 1000,
            reason=reason,
            error=error,
        )
        return self._rank_chunks_by_postgres_lexical(
            question=question,
            top_k=top_k,
            mode=mode,
            started_at=started_at,
            execution_path="pgvector_lexical_fallback",
            used_fallback=True,
            execution_issue=reason,
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

    def _load_metadata_snapshot(self, connection: object) -> PgvectorMetadataSnapshot | None:
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT
                    chunk_size_words,
                    chunk_overlap_words,
                    chunking_version,
                    indexed_at,
                    chunk_count,
                    source_file_count,
                    embedding_document_count,
                    lexical_document_count
                FROM {self._meta_table_name()}
                WHERE storage_key = %s
                """,
                ("active",),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return PgvectorMetadataSnapshot(
            chunk_size_words=int(row[0]),
            chunk_overlap_words=int(row[1]),
            chunking_version=str(row[2]),
            indexed_at=row[3].astimezone(timezone.utc),
            chunk_count=int(row[4]),
            source_file_count=int(row[5]),
            embedding_document_count=int(row[6]),
            lexical_document_count=int(row[7]),
        )

    def _connect(self) -> object:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError(
                "psycopg is required to use the pgvector storage backend. "
                "Install project dependencies from requirements.txt first."
            ) from exc

        return psycopg.connect(self.config.database_url)

    def get_readiness_status(self) -> dict[str, object]:
        embedding_stack_ready = embedding_stack_available()
        embedding_model_ready = bool(get_embedding_model()) if embedding_stack_ready else False

        try:
            with self._connect() as connection:
                self._ensure_schema(connection)
                metadata_snapshot = self._load_metadata_snapshot(connection)
                metadata_snapshot_stale = self._is_storage_stale(connection)
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
        except Exception as exc:
            return {
                "active_backend_state": "degraded",
                "active_backend_issue": "connection_failed",
                "active_backend_ready": False,
                "active_backend_can_connect": False,
                "active_backend_retrieval_ready": False,
                "active_backend_indexing_ready": False,
                "active_backend_indexing_preflight": "blocked",
                "active_backend_message": (
                    "pgvector backend is not ready: "
                    f"{type(exc).__name__}: {exc}"
                ),
                "pgvector_metadata_snapshot": None,
                "active_backend_indexing_message": (
                    "pgvector backend cannot reindex because the database connection is unavailable."
                ),
            }

        metadata_payload = (
            None if metadata_snapshot is None else metadata_snapshot.to_response_payload()
        )
        indexing_preflight = "native"
        indexing_message = "pgvector backend is ready for reindex requests."
        if not embedding_stack_ready:
            indexing_preflight = "degraded"
            indexing_message = (
                "pgvector backend can reindex in degraded mode, but embeddings will be unavailable because the embedding stack is unavailable."
            )
        elif not embedding_model_ready:
            indexing_preflight = "degraded"
            indexing_message = (
                "pgvector backend can reindex in degraded mode, but embeddings will be unavailable because the embedding model is unavailable."
            )

        if metadata_snapshot is None:
            return {
                "active_backend_state": "degraded",
                "active_backend_issue": "metadata_snapshot_missing",
                "active_backend_ready": True,
                "active_backend_can_connect": True,
                "active_backend_retrieval_ready": False,
                "active_backend_indexing_ready": True,
                "active_backend_indexing_preflight": indexing_preflight,
                "pgvector_metadata_snapshot": metadata_payload,
                "active_backend_message": (
                    "pgvector backend can connect, but no persisted indexing metadata snapshot exists yet."
                ),
                "active_backend_indexing_message": indexing_message,
            }

        if metadata_snapshot.chunk_count < 1:
            return {
                "active_backend_state": "degraded",
                "active_backend_issue": "metadata_snapshot_empty",
                "active_backend_ready": True,
                "active_backend_can_connect": True,
                "active_backend_retrieval_ready": False,
                "active_backend_indexing_ready": True,
                "active_backend_indexing_preflight": indexing_preflight,
                "pgvector_metadata_snapshot": metadata_payload,
                "active_backend_message": (
                    "pgvector backend can connect, but the persisted indexing metadata snapshot contains no indexed chunks yet."
                ),
                "active_backend_indexing_message": indexing_message,
            }

        if metadata_snapshot.lexical_document_count < metadata_snapshot.chunk_count:
            return {
                "active_backend_state": "degraded",
                "active_backend_issue": "metadata_snapshot_incomplete",
                "active_backend_ready": True,
                "active_backend_can_connect": True,
                "active_backend_retrieval_ready": False,
                "active_backend_indexing_ready": True,
                "active_backend_indexing_preflight": indexing_preflight,
                "pgvector_metadata_snapshot": metadata_payload,
                "active_backend_message": (
                    "pgvector backend can connect, but the persisted indexing metadata snapshot is incomplete for lexical retrieval."
                ),
                "active_backend_indexing_message": indexing_message,
            }

        if metadata_snapshot_stale:
            return {
                "active_backend_state": "degraded",
                "active_backend_issue": "metadata_snapshot_stale",
                "active_backend_ready": True,
                "active_backend_can_connect": True,
                "active_backend_retrieval_ready": False,
                "active_backend_indexing_ready": True,
                "active_backend_indexing_preflight": indexing_preflight,
                "pgvector_metadata_snapshot": metadata_payload,
                "active_backend_message": (
                    "pgvector backend can connect, but the persisted indexing metadata snapshot is stale and should be rebuilt."
                ),
                "active_backend_indexing_message": indexing_message,
            }

        if not embedding_stack_ready:
            return {
                "active_backend_state": "degraded",
                "active_backend_issue": "embedding_stack_unavailable",
                "active_backend_ready": True,
                "active_backend_can_connect": True,
                "active_backend_retrieval_ready": False,
                "active_backend_indexing_ready": True,
                "active_backend_indexing_preflight": indexing_preflight,
                "pgvector_metadata_snapshot": metadata_payload,
                "active_backend_message": (
                    "pgvector backend can connect, but the embedding stack is unavailable."
                ),
                "active_backend_indexing_message": indexing_message,
            }

        if not embedding_model_ready:
            return {
                "active_backend_state": "degraded",
                "active_backend_issue": "embedding_model_unavailable",
                "active_backend_ready": True,
                "active_backend_can_connect": True,
                "active_backend_retrieval_ready": False,
                "active_backend_indexing_ready": True,
                "active_backend_indexing_preflight": indexing_preflight,
                "pgvector_metadata_snapshot": metadata_payload,
                "active_backend_message": (
                    "pgvector backend can connect, but the embedding model is not ready."
                ),
                "active_backend_indexing_message": indexing_message,
            }

        return {
            "active_backend_state": "ready",
            "active_backend_issue": "none",
            "active_backend_ready": True,
            "active_backend_can_connect": True,
            "active_backend_retrieval_ready": True,
            "active_backend_indexing_ready": True,
            "active_backend_indexing_preflight": indexing_preflight,
            "pgvector_metadata_snapshot": metadata_payload,
            "active_backend_message": "pgvector backend is ready for retrieval requests.",
            "active_backend_indexing_message": indexing_message,
        }

    def _chunk_from_row(self, row: tuple[object, ...]) -> LoadedChunk:
        return LoadedChunk(
            document_id=str(row[0]),
            title=str(row[1]),
            content=str(row[2]),
            source_path=str(row[3]),
            file_type=str(row[4]),
            chunk_index=int(row[5]),
            chunk_size_words=int(row[6]),
            chunk_overlap_words=int(row[7]),
        )

    def _ensure_schema(self, connection: object) -> None:
        chunks_table = self._chunks_table_name()
        schema_name = self._validate_identifier(self.config.schema_name)
        table_name = self._validate_identifier(self.config.table_name)
        meta_table_name = self._validate_identifier(f"{self.config.table_name}_meta")
        index_name = self._validate_identifier(f"{table_name}_source_chunk_idx")
        lexical_index_name = self._validate_identifier(f"{table_name}_lexical_gin_idx")

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
                    lexical_document tsvector,
                    embedding vector({self.config.embedding_dim}),
                    indexed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                f"""
                ALTER TABLE {chunks_table}
                ADD COLUMN IF NOT EXISTS lexical_document tsvector
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
                CREATE INDEX IF NOT EXISTS {lexical_index_name}
                ON {chunks_table} USING GIN (lexical_document)
                """
            )
            # Backfill lexical vectors for pre-existing rows before the GIN-backed path is used.
            cursor.execute(
                f"""
                UPDATE {chunks_table}
                SET lexical_document = to_tsvector(
                    'simple',
                    COALESCE(title, '') || ' ' || COALESCE(content, '')
                )
                WHERE lexical_document IS NULL
                """
            )
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {schema_name}.{meta_table_name} (
                    storage_key TEXT PRIMARY KEY,
                    chunk_size_words INTEGER NOT NULL,
                    chunk_overlap_words INTEGER NOT NULL,
                    chunking_version TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    source_file_count INTEGER NOT NULL DEFAULT 0,
                    embedding_document_count INTEGER NOT NULL DEFAULT 0,
                    lexical_document_count INTEGER NOT NULL DEFAULT 0,
                    indexed_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            cursor.execute(
                f"""
                ALTER TABLE {self._meta_table_name()}
                ADD COLUMN IF NOT EXISTS chunk_count INTEGER NOT NULL DEFAULT 0
                """
            )
            cursor.execute(
                f"""
                ALTER TABLE {self._meta_table_name()}
                ADD COLUMN IF NOT EXISTS source_file_count INTEGER NOT NULL DEFAULT 0
                """
            )
            cursor.execute(
                f"""
                ALTER TABLE {self._meta_table_name()}
                ADD COLUMN IF NOT EXISTS embedding_document_count INTEGER NOT NULL DEFAULT 0
                """
            )
            cursor.execute(
                f"""
                ALTER TABLE {self._meta_table_name()}
                ADD COLUMN IF NOT EXISTS lexical_document_count INTEGER NOT NULL DEFAULT 0
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

    def _is_storage_stale(self, connection: object) -> bool:
        config = get_chunking_config()
        metadata = self._load_metadata_snapshot(connection)
        if metadata is None:
            return True

        if metadata.chunk_size_words != int(config["chunk_size_words"]):
            return True
        if metadata.chunk_overlap_words != int(config["chunk_overlap_words"]):
            return True
        if metadata.chunking_version != CHUNKING_VERSION:
            return True
        if metadata.chunk_count < 1:
            return bool(self._iter_supported_raw_files())
        if metadata.lexical_document_count < metadata.chunk_count:
            return True

        return any(
            datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) > metadata.indexed_at
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
            self._chunk_from_row(row)
            for row in rows
        )

    def prepare_runtime(self) -> StorageWarmupResult:
        with self._connect() as connection:
            self._ensure_schema(connection)
            if self._is_storage_stale(connection):
                chunks = self.rebuild_chunks()
                return StorageWarmupResult(
                    chunk_count=len(chunks),
                    loaded_into_memory=False,
                )

            metadata = self._load_metadata_snapshot(connection)
            return StorageWarmupResult(
                chunk_count=0 if metadata is None else metadata.chunk_count,
                loaded_into_memory=False,
            )

    def rebuild_chunks(self) -> tuple[LoadedChunk, ...]:
        config = get_chunking_config()
        chunks = build_experiment_chunks()
        embedding_rows = encode_texts(
            tuple(compose_embedding_text(chunk.title, chunk.content) for chunk in chunks)
        )
        vector_literals: list[str | None]
        if embedding_rows is None:
            vector_literals = [None] * len(chunks)
        else:
            vector_literals = [vector_to_pgvector_literal(row) for row in embedding_rows]
            if vector_literals and len(embedding_rows[0]) != self.config.embedding_dim:
                raise ValueError(
                    "Configured PGVECTOR_EMBEDDING_DIM does not match the active embedding model output size."
                )
        source_file_count = len({chunk.source_path for chunk in chunks})
        embedding_document_count = sum(1 for literal in vector_literals if literal is not None)
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
                        lexical_document,
                        embedding,
                        indexed_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        to_tsvector('simple', COALESCE(%s, '') || ' ' || COALESCE(%s, '')),
                        %s::vector,
                        NOW()
                    )
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
                            chunk.title,
                            chunk.content,
                            vector_literal,
                        )
                        for chunk, vector_literal in zip(chunks, vector_literals, strict=False)
                    ],
                )
                cursor.execute(
                    f"""
                    INSERT INTO {self._meta_table_name()} (
                        storage_key,
                        chunk_size_words,
                        chunk_overlap_words,
                        chunking_version,
                        chunk_count,
                        source_file_count,
                        embedding_document_count,
                        lexical_document_count,
                        indexed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (storage_key) DO UPDATE SET
                        chunk_size_words = EXCLUDED.chunk_size_words,
                        chunk_overlap_words = EXCLUDED.chunk_overlap_words,
                        chunking_version = EXCLUDED.chunking_version,
                        chunk_count = EXCLUDED.chunk_count,
                        source_file_count = EXCLUDED.source_file_count,
                        embedding_document_count = EXCLUDED.embedding_document_count,
                        lexical_document_count = EXCLUDED.lexical_document_count,
                        indexed_at = EXCLUDED.indexed_at
                    """,
                    (
                        "active",
                        int(config["chunk_size_words"]),
                        int(config["chunk_overlap_words"]),
                        CHUNKING_VERSION,
                        len(chunks),
                        source_file_count,
                        embedding_document_count,
                        len(chunks),
                    ),
                )
            connection.commit()
        return chunks

    def _rank_chunks_by_pgvector_embeddings(
        self,
        *,
        question: str,
        top_k: int,
        mode: RetrievalModeValue,
        started_at: float,
    ) -> RankedChunkResult:
        if not question.strip() or top_k < 1:
            return RankedChunkResult(
                ranked_chunks=[],
                execution_path="pgvector_native",
                used_fallback=False,
                execution_issue="none",
                outcome="zero_results",
            )

        query_embedding = encode_query(question)
        if query_embedding is None:
            raise PgvectorRetrievalUnavailableError(
                "Embedding model is unavailable for pgvector query encoding."
            )
        if len(query_embedding[0]) != self.config.embedding_dim:
            raise PgvectorRetrievalUnavailableError(
                "Configured PGVECTOR_EMBEDDING_DIM does not match the active embedding model output size."
            )

        query_vector = vector_to_pgvector_literal(query_embedding)
        with self._connect() as connection:
            self._ensure_schema(connection)
            if self._is_storage_stale(connection):
                self.rebuild_chunks()
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
                        chunk_overlap_words,
                        1 - (embedding <=> %s::vector) AS score
                    FROM {self._chunks_table_name()}
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_vector, query_vector, top_k),
                )
                rows = cursor.fetchall()

        ranked_chunks = [
            (self._chunk_from_row(row[:-1]), float(row[-1]))
            for row in rows
            if row[-1] is not None and float(row[-1]) > 0
        ]
        latency_ms = (perf_counter() - started_at) * 1000
        if not ranked_chunks:
            self._log_zero_results(
                mode=mode,
                question=question,
                top_k=top_k,
                latency_ms=latency_ms,
            )
        else:
            self._log_successful_retrieval(
                mode=mode,
                question=question,
                top_k=top_k,
                hit_count=len(ranked_chunks),
                latency_ms=latency_ms,
            )
        return RankedChunkResult(
            ranked_chunks=ranked_chunks,
            execution_path="pgvector_native",
            used_fallback=False,
            execution_issue="none",
            outcome="success" if ranked_chunks else "zero_results",
        )

    def _rank_chunks_by_postgres_lexical(
        self,
        *,
        question: str,
        top_k: int,
        mode: RetrievalModeValue,
        started_at: float,
        execution_path: str,
        used_fallback: bool,
        execution_issue: str,
    ) -> RankedChunkResult:
        if not question.strip() or top_k < 1:
            return RankedChunkResult(
                ranked_chunks=[],
                execution_path=execution_path,
                used_fallback=used_fallback,
                execution_issue=execution_issue,
                outcome="fallback" if used_fallback else "zero_results",
            )

        with self._connect() as connection:
            self._ensure_schema(connection)
            if self._is_storage_stale(connection):
                self.rebuild_chunks()
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    WITH lexical_query AS (
                        SELECT plainto_tsquery('simple', %s) AS query
                    )
                    SELECT
                        document_id,
                        title,
                        content,
                        source_path,
                        file_type,
                        chunk_index,
                        chunk_size_words,
                        chunk_overlap_words,
                        ts_rank_cd(lexical_document, lexical_query.query) AS score
                    FROM {self._chunks_table_name()}, lexical_query
                    WHERE lexical_document @@ lexical_query.query
                    ORDER BY score DESC, source_path, chunk_index
                    LIMIT %s
                    """,
                    (question, top_k),
                )
                rows = cursor.fetchall()

        ranked_chunks = [
            (self._chunk_from_row(row[:-1]), float(row[-1]))
            for row in rows
            if row[-1] is not None and float(row[-1]) > 0
        ]
        latency_ms = (perf_counter() - started_at) * 1000
        if not ranked_chunks:
            self._log_zero_results(
                mode=mode,
                question=question,
                top_k=top_k,
                latency_ms=latency_ms,
            )
        else:
            self._log_successful_retrieval(
                mode=mode,
                question=question,
                top_k=top_k,
                hit_count=len(ranked_chunks),
                latency_ms=latency_ms,
            )
        return RankedChunkResult(
            ranked_chunks=ranked_chunks,
            execution_path=execution_path,
            used_fallback=used_fallback,
            execution_issue=execution_issue,
            outcome="fallback" if used_fallback else ("success" if ranked_chunks else "zero_results"),
        )

    def rank_chunks(self, question: str, top_k: int, mode: RetrievalModeValue) -> RankedChunkResult:
        started_at = perf_counter()
        if mode == "tfidf":
            return self._rank_chunks_by_postgres_lexical(
                question=question,
                top_k=top_k,
                mode="tfidf",
                started_at=started_at,
                execution_path="pgvector_lexical",
                used_fallback=False,
                execution_issue="none",
            )

        try:
            return self._rank_chunks_by_pgvector_embeddings(
                question=question,
                top_k=top_k,
                mode=mode,
                started_at=started_at,
            )
        except PgvectorRetrievalUnavailableError as exc:
            return self._rank_chunks_with_lexical_fallback(
                question=question,
                top_k=top_k,
                mode=mode,
                started_at=started_at,
                reason="pgvector_unavailable",
                error=exc,
            )
        except Exception as exc:
            return self._rank_chunks_with_lexical_fallback(
                question=question,
                top_k=top_k,
                mode=mode,
                started_at=started_at,
                reason="pgvector_query_failed",
                error=exc,
            )

    def clear_cache(self) -> None:
        # The pgvector implementation does not keep a local cache yet.
        return None


def build_pgvector_storage() -> PgvectorChunkStorage:
    return PgvectorChunkStorage.from_settings()
