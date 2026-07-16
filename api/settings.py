from __future__ import annotations

import os
from pathlib import Path


API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CHUNKS_FILE = PROCESSED_DATA_DIR / "chunks.jsonl"
CHUNKING_VERSION = "word-overlap-v1"
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def _load_local_dotenv() -> None:
    dotenv_path = PROJECT_ROOT / ".env"
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


_load_local_dotenv()


def _env_value(name: str) -> str | None:
    file_path = os.getenv(f"{name}_FILE")
    if file_path:
        try:
            return Path(file_path).read_text(encoding="utf-8").strip()
        except OSError:
            return None
    return os.getenv(name)


def _env_flag(name: str, default: bool = False) -> bool:
    value = _env_value(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = _env_value(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_str(name: str, default: str = "") -> str:
    value = _env_value(name)
    if value is None:
        return default
    return value.strip()


CHUNK_SIZE_WORDS = _env_int("CHUNK_SIZE_WORDS", 120)
CHUNK_OVERLAP_WORDS = _env_int("CHUNK_OVERLAP_WORDS", 30)

CHUNK_STORAGE_BACKEND = _env_str("CHUNK_STORAGE_BACKEND", "file").lower() or "file"
POSTGRES_HOST = _env_str("POSTGRES_HOST", "localhost")
POSTGRES_PORT = _env_int("POSTGRES_PORT", 5432)
POSTGRES_DB = _env_str("POSTGRES_DB", "ai_knowledge_assistant")
POSTGRES_USER = _env_str("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = _env_str("POSTGRES_PASSWORD", "postgres")
POSTGRES_SSL_MODE = _env_str("POSTGRES_SSL_MODE", "disable")
PGVECTOR_SCHEMA = _env_str("PGVECTOR_SCHEMA", "public")
PGVECTOR_TABLE = _env_str("PGVECTOR_TABLE", "document_chunks")
RUNTIME_STATE_TABLE = _env_str("POSTGRES_RUNTIME_STATE_TABLE", "runtime_state")
REINDEX_HISTORY_TABLE = _env_str("POSTGRES_REINDEX_HISTORY_TABLE", "reindex_history")
RETRIEVAL_HISTORY_TABLE = _env_str("POSTGRES_RETRIEVAL_HISTORY_TABLE", "retrieval_history")
WEB_SEARCH_HISTORY_TABLE = _env_str("POSTGRES_WEB_SEARCH_HISTORY_TABLE", "web_search_history")
PGVECTOR_EMBEDDING_DIM = _env_int("PGVECTOR_EMBEDDING_DIM", 384)
PGVECTOR_REINDEX_EMBEDDING_BATCH_SIZE = _env_int("PGVECTOR_REINDEX_EMBEDDING_BATCH_SIZE", 64)
PGVECTOR_REINDEX_DB_BATCH_SIZE = _env_int("PGVECTOR_REINDEX_DB_BATCH_SIZE", 200)
PGVECTOR_REINDEX_BATCH_SLEEP_SECONDS = float(
    _env_str("PGVECTOR_REINDEX_BATCH_SLEEP_SECONDS", "0")
)
PGVECTOR_DATABASE_URL = _env_str(
    "PGVECTOR_DATABASE_URL",
    (
        "postgresql://"
        f"{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/"
        f"{POSTGRES_DB}?sslmode={POSTGRES_SSL_MODE}"
    ),
)


LLM_ENABLED = _env_flag("LLM_ENABLED", default=False)
LLM_API_KEY = _env_str("LLM_API_KEY", "")
LLM_API_BASE = _env_str("LLM_API_BASE", "https://api.openai.com/v1").rstrip("/")
LLM_CHAT_COMPLETIONS_URL = _env_str("LLM_CHAT_COMPLETIONS_URL", "").rstrip("/")
LLM_MODEL = _env_str("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SEC = float(_env_str("LLM_TIMEOUT_SEC", "20"))
LLM_MAX_TOKENS = int(_env_str("LLM_MAX_TOKENS", "220"))

WEB_SEARCH_OPENAI_ENABLED = _env_flag("WEB_SEARCH_OPENAI_ENABLED", default=False)
WEB_SEARCH_OPENAI_URL = _env_str("WEB_SEARCH_OPENAI_URL", "").rstrip("/")
WEB_SEARCH_OPENAI_API_KEY = _env_str("WEB_SEARCH_OPENAI_API_KEY", "")
WEB_SEARCH_OPENAI_MODEL = _env_str("WEB_SEARCH_OPENAI_MODEL", LLM_MODEL)
WEB_SEARCH_OPENAI_TIMEOUT_SEC = float(_env_str("WEB_SEARCH_OPENAI_TIMEOUT_SEC", "20"))

SERPAPI_ENABLED = _env_flag("SERPAPI_ENABLED", default=False)
SERPAPI_API_KEY = _env_str("SERPAPI_API_KEY", "")
SERPAPI_ENGINE = _env_str("SERPAPI_ENGINE", "google")
SERPAPI_NUM_RESULTS = int(_env_str("SERPAPI_NUM_RESULTS", "5"))
SERPAPI_TIMEOUT_SEC = float(_env_str("SERPAPI_TIMEOUT_SEC", "15"))

# Celery is an optional offload path for heavy reindex jobs so the web process
# does not have to run CPU-heavy embeddings/DB work in its own event loop.
# When disabled (default) or unavailable, reindex keeps running as an
# in-process FastAPI background task, exactly as before.
CELERY_ENABLED = _env_flag("CELERY_ENABLED", default=False)
CELERY_BROKER_URL = _env_str("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = _env_str("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)
CELERY_REINDEX_QUEUE = _env_str("CELERY_REINDEX_QUEUE", "reindex")

ADMIN_USERNAME = _env_str("ADMIN_USERNAME", "owner")
ADMIN_PASSWORD = _env_str("ADMIN_PASSWORD", "")
ADMIN_AUTH_ENABLED = bool(ADMIN_PASSWORD)
ADMIN_SESSION_SECRET = _env_str(
    "ADMIN_SESSION_SECRET",
    "dev-session-secret-change-me-before-production",
)
ADMIN_SESSION_SECRET_CONFIGURED = bool(_env_value("ADMIN_SESSION_SECRET"))
