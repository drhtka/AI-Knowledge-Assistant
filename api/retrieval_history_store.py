from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from threading import Lock

from api.settings import PGVECTOR_DATABASE_URL, PGVECTOR_SCHEMA, RETRIEVAL_HISTORY_TABLE

logger = logging.getLogger("ai_knowledge_assistant.retrieval_history")

_schema_lock = Lock()
_schema_ready = False


@dataclass(frozen=True)
class RetrievalHistoryEntry:
    history_entry_id: int
    request_kind: str
    status: str
    question_length: int
    retrieval_mode: str
    active_storage_backend: str
    retrieval_execution_path: str
    retrieval_execution_issue: str
    retrieval_outcome: str
    retrieval_summary_message: str
    hit_count: int
    latency_ms: int
    updated_at: str
    error_type: str


def _validate_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid SQL identifier for retrieval history store: {value!r}")
    return value


def _table_name() -> str:
    schema_name = _validate_identifier(PGVECTOR_SCHEMA)
    table_name = _validate_identifier(RETRIEVAL_HISTORY_TABLE)
    return f"{schema_name}.{table_name}"


def _connect() -> object:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required to persist retrieval history in PostgreSQL. "
            "Install project dependencies from requirements.txt first."
        ) from exc

    return psycopg.connect(PGVECTOR_DATABASE_URL)


def _ensure_schema(connection: object) -> None:
    global _schema_ready
    if _schema_ready:
        return

    with _schema_lock:
        if _schema_ready:
            return

        schema_name = _validate_identifier(PGVECTOR_SCHEMA)
        table_name = _table_name()
        updated_at_index = _validate_identifier(f"{RETRIEVAL_HISTORY_TABLE}_updated_at_idx")
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    history_entry_id BIGSERIAL PRIMARY KEY,
                    request_kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    question_length INTEGER NOT NULL DEFAULT 0,
                    retrieval_mode TEXT NOT NULL,
                    active_storage_backend TEXT NOT NULL,
                    retrieval_execution_path TEXT NOT NULL,
                    retrieval_execution_issue TEXT NOT NULL,
                    retrieval_outcome TEXT NOT NULL,
                    retrieval_summary_message TEXT NOT NULL,
                    hit_count INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    updated_at TIMESTAMPTZ NOT NULL,
                    error_type TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {updated_at_index}
                ON {table_name} (updated_at DESC, history_entry_id DESC)
                """
            )
        connection.commit()
        _schema_ready = True


def create_retrieval_history_entry(
    *,
    request_kind: str,
    status: str,
    question_length: int,
    retrieval_mode: str,
    active_storage_backend: str,
    retrieval_execution_path: str,
    retrieval_execution_issue: str,
    retrieval_outcome: str,
    retrieval_summary_message: str,
    hit_count: int,
    latency_ms: int,
    updated_at: str,
    error_type: str,
) -> int | None:
    try:
        with _connect() as connection:
            _ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {_table_name()} (
                        request_kind,
                        status,
                        question_length,
                        retrieval_mode,
                        active_storage_backend,
                        retrieval_execution_path,
                        retrieval_execution_issue,
                        retrieval_outcome,
                        retrieval_summary_message,
                        hit_count,
                        latency_ms,
                        updated_at,
                        error_type
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING history_entry_id
                    """,
                    (
                        request_kind,
                        status,
                        question_length,
                        retrieval_mode,
                        active_storage_backend,
                        retrieval_execution_path,
                        retrieval_execution_issue,
                        retrieval_outcome,
                        retrieval_summary_message,
                        hit_count,
                        latency_ms,
                        updated_at,
                        error_type,
                    ),
                )
                row = cursor.fetchone()
            connection.commit()
    except Exception as exc:
        logger.warning(
            "Failed to create retrieval history entry in PostgreSQL.",
            extra={
                "event": "retrieval_history_create_failed",
                "context": {
                    "request_kind": request_kind,
                    "status": status,
                    "error_type": type(exc).__name__,
                },
            },
            exc_info=True,
        )
        return None

    if row is None:
        return None
    return int(row[0])


def list_retrieval_history_entries(limit: int = 20) -> tuple[RetrievalHistoryEntry, ...]:
    safe_limit = max(1, min(100, int(limit)))
    try:
        with _connect() as connection:
            _ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        history_entry_id,
                        request_kind,
                        status,
                        question_length,
                        retrieval_mode,
                        active_storage_backend,
                        retrieval_execution_path,
                        retrieval_execution_issue,
                        retrieval_outcome,
                        retrieval_summary_message,
                        hit_count,
                        latency_ms,
                        updated_at,
                        error_type
                    FROM {_table_name()}
                    ORDER BY updated_at DESC, history_entry_id DESC
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                rows = cursor.fetchall()
    except Exception as exc:
        logger.warning(
            "Failed to load retrieval history from PostgreSQL.",
            extra={
                "event": "retrieval_history_load_failed",
                "context": {
                    "limit": safe_limit,
                    "error_type": type(exc).__name__,
                },
            },
            exc_info=True,
        )
        return ()

    return tuple(
        RetrievalHistoryEntry(
            history_entry_id=int(row[0]),
            request_kind=str(row[1]),
            status=str(row[2]),
            question_length=int(row[3]),
            retrieval_mode=str(row[4]),
            active_storage_backend=str(row[5]),
            retrieval_execution_path=str(row[6]),
            retrieval_execution_issue=str(row[7]),
            retrieval_outcome=str(row[8]),
            retrieval_summary_message=str(row[9]),
            hit_count=int(row[10]),
            latency_ms=int(row[11]),
            updated_at=row[12].isoformat(),
            error_type=str(row[13]),
        )
        for row in rows
    )
