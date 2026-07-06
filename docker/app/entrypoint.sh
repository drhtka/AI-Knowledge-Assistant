#!/bin/sh
set -eu

python - <<'PY'
import os
import sys
import time
from pathlib import Path


def env_value(name: str, default: str = "") -> str:
    file_path = os.getenv(f"{name}_FILE", "").strip()
    if file_path:
        try:
            return Path(file_path).read_text(encoding="utf-8").strip()
        except OSError:
            return default
    return os.getenv(name, default).strip()


def build_database_url() -> str:
    explicit_url = env_value("PGVECTOR_DATABASE_URL", "")
    if explicit_url:
        return explicit_url

    host = env_value("POSTGRES_HOST", "localhost")
    port = env_value("POSTGRES_PORT", "5432")
    database = env_value("POSTGRES_DB", "ai_knowledge_assistant")
    user = env_value("POSTGRES_USER", "postgres")
    password = env_value("POSTGRES_PASSWORD", "postgres")
    sslmode = env_value("POSTGRES_SSL_MODE", "disable")
    return (
        f"postgresql://{user}:{password}@{host}:{port}/{database}"
        f"?sslmode={sslmode}"
    )

backend = env_value("CHUNK_STORAGE_BACKEND", "file").lower()
database_url = build_database_url()

if backend != "pgvector":
    raise SystemExit(0)

import psycopg

deadline = time.time() + float(env_value("DB_STARTUP_TIMEOUT_SEC", "90"))
last_error = ""

while time.time() < deadline:
    try:
        with psycopg.connect(database_url, connect_timeout=5) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        raise SystemExit(0)
    except Exception as exc:
        last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(2)

print(
    f"Database did not become ready before app startup: {last_error}",
    file=sys.stderr,
)
raise SystemExit(1)
PY

exec uvicorn api.app:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${UVICORN_WORKERS:-1}"
