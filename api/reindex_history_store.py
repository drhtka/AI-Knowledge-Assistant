from __future__ import annotations

from dataclasses import dataclass
import logging
import re
from threading import Lock

from api.settings import PGVECTOR_DATABASE_URL, PGVECTOR_SCHEMA, REINDEX_HISTORY_TABLE

logger = logging.getLogger("ai_knowledge_assistant.reindex_history")

_schema_lock = Lock()
_schema_ready = False


@dataclass(frozen=True)
class ReindexHistoryEntry:
    history_entry_id: int
    trigger: str
    backend: str
    state: str
    outcome: str
    started_at: str
    finished_at: str | None
    document_count: int
    chunk_count: int
    elapsed_ms: int
    last_error: str
    summary_message: str


def _validate_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid SQL identifier for reindex history store: {value!r}")
    return value


def _table_name() -> str:
    schema_name = _validate_identifier(PGVECTOR_SCHEMA)
    table_name = _validate_identifier(REINDEX_HISTORY_TABLE)
    return f"{schema_name}.{table_name}"


def _connect() -> object:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required to persist reindex history in PostgreSQL. "
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
        started_at_index = _validate_identifier(f"{REINDEX_HISTORY_TABLE}_started_at_idx")
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    history_entry_id BIGSERIAL PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    backend TEXT NOT NULL,
                    state TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    started_at TIMESTAMPTZ NOT NULL,
                    finished_at TIMESTAMPTZ,
                    document_count INTEGER NOT NULL DEFAULT 0,
                    chunk_count INTEGER NOT NULL DEFAULT 0,
                    elapsed_ms INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT NOT NULL DEFAULT '',
                    summary_message TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {started_at_index}
                ON {table_name} (started_at DESC, history_entry_id DESC)
                """
            )
        connection.commit()
        _schema_ready = True


def create_reindex_history_entry(
    *,
    trigger: str,
    backend: str,
    state: str,
    outcome: str,
    started_at: str,
    summary_message: str,
) -> int | None:
    try:
        with _connect() as connection:
            _ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {_table_name()} (
                        trigger,
                        backend,
                        state,
                        outcome,
                        started_at,
                        summary_message
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING history_entry_id
                    """,
                    (trigger, backend, state, outcome, started_at, summary_message),
                )
                row = cursor.fetchone()
            connection.commit()
    except Exception as exc:
        logger.warning(
            "Failed to create reindex history entry in PostgreSQL.",
            extra={
                "event": "reindex_history_create_failed",
                "context": {
                    "trigger": trigger,
                    "backend": backend,
                    "error_type": type(exc).__name__,
                },
            },
            exc_info=True,
        )
        return None

    if row is None:
        return None
    return int(row[0])


def finalize_reindex_history_entry(
    history_entry_id: int,
    *,
    state: str,
    outcome: str,
    finished_at: str,
    document_count: int,
    chunk_count: int,
    elapsed_ms: int,
    last_error: str,
    summary_message: str,
) -> bool:
    try:
        with _connect() as connection:
            _ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    UPDATE {_table_name()}
                    SET
                        state = %s,
                        outcome = %s,
                        finished_at = %s,
                        document_count = %s,
                        chunk_count = %s,
                        elapsed_ms = %s,
                        last_error = %s,
                        summary_message = %s,
                        updated_at = NOW()
                    WHERE history_entry_id = %s
                    """,
                    (
                        state,
                        outcome,
                        finished_at,
                        document_count,
                        chunk_count,
                        elapsed_ms,
                        last_error,
                        summary_message,
                        history_entry_id,
                    ),
                )
            connection.commit()
    except Exception as exc:
        logger.warning(
            "Failed to finalize reindex history entry in PostgreSQL.",
            extra={
                "event": "reindex_history_finalize_failed",
                "context": {
                    "history_entry_id": history_entry_id,
                    "error_type": type(exc).__name__,
                },
            },
            exc_info=True,
        )
        return False

    return True


def list_reindex_history_entries(limit: int = 20) -> tuple[ReindexHistoryEntry, ...]:
    safe_limit = max(1, min(100, int(limit)))
    try:
        with _connect() as connection:
            _ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT
                        history_entry_id,
                        trigger,
                        backend,
                        state,
                        outcome,
                        started_at,
                        finished_at,
                        document_count,
                        chunk_count,
                        elapsed_ms,
                        last_error,
                        summary_message
                    FROM {_table_name()}
                    ORDER BY started_at DESC, history_entry_id DESC
                    LIMIT %s
                    """,
                    (safe_limit,),
                )
                rows = cursor.fetchall()
    except Exception as exc:
        logger.warning(
            "Failed to load reindex history from PostgreSQL.",
            extra={
                "event": "reindex_history_load_failed",
                "context": {
                    "limit": safe_limit,
                    "error_type": type(exc).__name__,
                },
            },
            exc_info=True,
        )
        return ()

    return tuple(
        ReindexHistoryEntry(
            history_entry_id=int(row[0]),
            trigger=str(row[1]),
            backend=str(row[2]),
            state=str(row[3]),
            outcome=str(row[4]),
            started_at=row[5].isoformat(),
            finished_at=None if row[6] is None else row[6].isoformat(),
            document_count=int(row[7]),
            chunk_count=int(row[8]),
            elapsed_ms=int(row[9]),
            last_error=str(row[10]),
            summary_message=str(row[11]),
        )
        for row in rows
    )
