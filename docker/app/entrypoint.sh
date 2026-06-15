#!/bin/sh
set -eu

python - <<'PY'
import os
import sys
import time

backend = os.getenv("CHUNK_STORAGE_BACKEND", "file").strip().lower()
database_url = os.getenv("PGVECTOR_DATABASE_URL", "").strip()

if backend != "pgvector" or not database_url:
    raise SystemExit(0)

import psycopg

deadline = time.time() + float(os.getenv("DB_STARTUP_TIMEOUT_SEC", "90"))
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

exec uvicorn api.app:app --host 0.0.0.0 --port "${PORT:-8000}"
