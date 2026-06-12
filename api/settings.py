from __future__ import annotations

from pathlib import Path


API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
STATIC_DIR = PROJECT_ROOT / "static"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CHUNKS_FILE = PROCESSED_DATA_DIR / "chunks.jsonl"
