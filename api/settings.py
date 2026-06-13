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


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


CHUNK_SIZE_WORDS = _env_int("CHUNK_SIZE_WORDS", 120)
CHUNK_OVERLAP_WORDS = _env_int("CHUNK_OVERLAP_WORDS", 30)


LLM_ENABLED = _env_flag("LLM_ENABLED", default=False)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_API_BASE = os.getenv("LLM_API_BASE", "https://api.openai.com/v1").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT_SEC = float(os.getenv("LLM_TIMEOUT_SEC", "20"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "220"))

SERPAPI_ENABLED = _env_flag("SERPAPI_ENABLED", default=False)
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "")
SERPAPI_ENGINE = os.getenv("SERPAPI_ENGINE", "google")
SERPAPI_NUM_RESULTS = int(os.getenv("SERPAPI_NUM_RESULTS", "5"))
SERPAPI_TIMEOUT_SEC = float(os.getenv("SERPAPI_TIMEOUT_SEC", "15"))
