from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re

from api.settings import CHUNKS_FILE, RAW_DATA_DIR

SUPPORTED_EXTENSIONS = {".md", ".txt"}
IGNORED_FILENAMES = {"README.md", "README.txt"}
MAX_CHUNK_CHARS = 320


@dataclass(frozen=True)
class LoadedChunk:
    document_id: str
    title: str
    content: str


def _clean_text(text: str) -> str:
    return " ".join(text.split())


def _sanitize_filename(filename: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._")
    return sanitized or "uploaded_document.txt"


def _extract_title(path: Path, text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()

    return path.stem.replace("_", " ").replace("-", " ").title()


def _split_long_block(block: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    if len(block) <= max_chars:
        return [block]

    words = block.split()
    chunks: list[str] = []
    current_words: list[str] = []

    for word in words:
        candidate = " ".join([*current_words, word]).strip()
        if current_words and len(candidate) > max_chars:
            chunks.append(" ".join(current_words))
            current_words = [word]
            continue
        current_words.append(word)

    if current_words:
        chunks.append(" ".join(current_words))

    return chunks


def _build_chunks(path: Path) -> list[LoadedChunk]:
    raw_text = path.read_text(encoding="utf-8", errors="ignore")
    title = _extract_title(path, raw_text)
    blocks = [
        _clean_text(block)
        for block in raw_text.split("\n\n")
        if _clean_text(block)
    ]

    chunks: list[LoadedChunk] = []
    for block_index, block in enumerate(blocks, start=1):
        for part_index, part in enumerate(_split_long_block(block), start=1):
            chunks.append(
                LoadedChunk(
                    document_id=f"{path.stem}-{block_index}-{part_index}",
                    title=title,
                    content=part,
                )
            )

    return chunks


def _serialize_chunk(chunk: LoadedChunk) -> str:
    return json.dumps(
        {
            "document_id": chunk.document_id,
            "title": chunk.title,
            "content": chunk.content,
        },
        ensure_ascii=False,
    )


def _deserialize_chunk(line: str) -> LoadedChunk:
    payload = json.loads(line)
    return LoadedChunk(
        document_id=payload["document_id"],
        title=payload["title"],
        content=payload["content"],
    )


def _iter_supported_raw_files(raw_data_dir: Path) -> list[Path]:
    if not raw_data_dir.exists():
        return []

    return [
        path
        for path in sorted(raw_data_dir.rglob("*"))
        if path.is_file()
        and path.name not in IGNORED_FILENAMES
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def _processed_data_is_stale(raw_data_dir: Path, chunks_file: Path) -> bool:
    if not chunks_file.exists():
        return True

    chunks_mtime = chunks_file.stat().st_mtime
    for path in _iter_supported_raw_files(raw_data_dir):
        if path.stat().st_mtime > chunks_mtime:
            return True

    return False


def build_processed_chunks(
    raw_data_dir: Path = RAW_DATA_DIR,
    chunks_file: Path = CHUNKS_FILE,
) -> tuple[LoadedChunk, ...]:
    chunks: list[LoadedChunk] = []

    for path in _iter_supported_raw_files(raw_data_dir):
        chunks.extend(_build_chunks(path))

    chunks_file.parent.mkdir(parents=True, exist_ok=True)
    with chunks_file.open("w", encoding="utf-8") as file_handle:
        for chunk in chunks:
            file_handle.write(_serialize_chunk(chunk))
            file_handle.write("\n")

    return tuple(chunks)


@lru_cache(maxsize=1)
def load_chunks(
    raw_data_dir: Path = RAW_DATA_DIR,
    chunks_file: Path = CHUNKS_FILE,
) -> tuple[LoadedChunk, ...]:
    # Cache the processed baseline corpus in memory for the current process.
    if _processed_data_is_stale(raw_data_dir=raw_data_dir, chunks_file=chunks_file):
        return build_processed_chunks(raw_data_dir=raw_data_dir, chunks_file=chunks_file)

    with chunks_file.open("r", encoding="utf-8") as file_handle:
        return tuple(
            _deserialize_chunk(line)
            for line in file_handle
            if line.strip()
        )


def clear_chunks_cache() -> None:
    load_chunks.cache_clear()


def save_uploaded_document(filename: str, content: bytes, raw_data_dir: Path = RAW_DATA_DIR) -> Path:
    safe_name = _sanitize_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only .txt and .md files are supported.")

    raw_data_dir.mkdir(parents=True, exist_ok=True)

    target_path = raw_data_dir / safe_name
    target_path.write_text(content.decode("utf-8", errors="ignore"), encoding="utf-8")
    clear_chunks_cache()
    build_processed_chunks(raw_data_dir=raw_data_dir)
    return target_path
