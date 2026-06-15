from __future__ import annotations

import json
import logging
import re
from threading import Lock
from typing import Any, Mapping

from api.settings import PGVECTOR_DATABASE_URL, PGVECTOR_SCHEMA, RUNTIME_STATE_TABLE

logger = logging.getLogger("ai_knowledge_assistant.runtime_state")

ACTIVE_STORAGE_BACKEND_STATE_KEY = "active_storage_backend"
REINDEX_STATUS_STATE_KEY = "reindex_status"
RETRIEVAL_RUNTIME_SNAPSHOT_STATE_KEY = "retrieval_runtime_snapshot"
SOURCE_UPDATE_JOB_STATE_KEY = "source_update_job"

_schema_lock = Lock()
_schema_ready = False


def _validate_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError(f"Invalid SQL identifier for runtime state store: {value!r}")
    return value


def _table_name() -> str:
    schema_name = _validate_identifier(PGVECTOR_SCHEMA)
    table_name = _validate_identifier(RUNTIME_STATE_TABLE)
    return f"{schema_name}.{table_name}"


def _connect() -> object:
    try:
        import psycopg
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required to persist runtime state in PostgreSQL. "
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
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    state_key TEXT PRIMARY KEY,
                    state_payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        connection.commit()
        _schema_ready = True


def load_runtime_state(state_key: str) -> dict[str, Any] | None:
    try:
        with _connect() as connection:
            _ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT state_payload FROM {_table_name()} WHERE state_key = %s",
                    (state_key,),
                )
                row = cursor.fetchone()
    except Exception as exc:
        logger.warning(
            "Failed to load runtime state from PostgreSQL.",
            extra={
                "event": "runtime_state_load_failed",
                "context": {
                    "state_key": state_key,
                    "error_type": type(exc).__name__,
                },
            },
            exc_info=True,
        )
        return None

    if row is None:
        return None

    try:
        payload = row[0]
        if isinstance(payload, dict):
            return dict(payload)
        if isinstance(payload, str):
            loaded_payload = json.loads(payload)
            if isinstance(loaded_payload, dict):
                return dict(loaded_payload)
        raise ValueError(f"Runtime state payload for key {state_key!r} is not a JSON object.")
    except Exception as exc:
        logger.warning(
            "Runtime state payload is invalid and will be ignored.",
            extra={
                "event": "runtime_state_payload_invalid",
                "context": {
                    "state_key": state_key,
                    "error_type": type(exc).__name__,
                },
            },
            exc_info=True,
        )
        return None


def save_runtime_state(state_key: str, payload: Mapping[str, object]) -> bool:
    try:
        with _connect() as connection:
            _ensure_schema(connection)
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    INSERT INTO {_table_name()} (state_key, state_payload, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (state_key) DO UPDATE SET
                        state_payload = EXCLUDED.state_payload,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (state_key, json.dumps(dict(payload), sort_keys=True)),
                )
            connection.commit()
    except Exception as exc:
        logger.warning(
            "Failed to persist runtime state to PostgreSQL.",
            extra={
                "event": "runtime_state_save_failed",
                "context": {
                    "state_key": state_key,
                    "error_type": type(exc).__name__,
                },
            },
            exc_info=True,
        )
        return False

    return True
