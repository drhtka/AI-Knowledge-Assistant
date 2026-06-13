from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re

from api.settings import (
    CHUNKS_FILE,
    CHUNK_OVERLAP_WORDS,
    CHUNK_SIZE_WORDS,
    CHUNKING_VERSION,
    RAW_DATA_DIR,
)

SUPPORTED_EXTENSIONS = {".md", ".txt"}
IGNORED_FILENAMES = {"README.md", "README.txt"}


@dataclass(frozen=True)
class LoadedChunk:
    document_id: str
    title: str
    content: str
    source_path: str
    chunk_index: int
    chunk_size_words: int
    chunk_overlap_words: int


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


def _split_text_into_word_chunks(
    text: str,
    chunk_size_words: int = CHUNK_SIZE_WORDS,
    chunk_overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[str]:
    words = text.split()
    if not words:
        return []

    # Keep the overlap smaller than the chunk to guarantee forward progress.
    normalized_overlap = min(max(chunk_overlap_words, 0), max(chunk_size_words - 1, 0))
    step = max(1, chunk_size_words - normalized_overlap)

    chunks: list[str] = []
    for start_index in range(0, len(words), step):
        end_index = start_index + chunk_size_words
        chunk_words = words[start_index:end_index]
        if not chunk_words:
            break

        chunks.append(" ".join(chunk_words))
        if end_index >= len(words):
            break

    return chunks


def _build_chunks(
    path: Path,
    chunk_size_words: int = CHUNK_SIZE_WORDS,
    chunk_overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> list[LoadedChunk]:
    raw_text = path.read_text(encoding="utf-8", errors="ignore")
    title = _extract_title(path, raw_text)
    cleaned_blocks = [
        _clean_text(block)
        for block in raw_text.split("\n\n")
        if _clean_text(block)
    ]
    document_text = "\n\n".join(cleaned_blocks)

    chunks: list[LoadedChunk] = []
    for chunk_index, chunk_text in enumerate(
        _split_text_into_word_chunks(
            document_text,
            chunk_size_words=chunk_size_words,
            chunk_overlap_words=chunk_overlap_words,
        ),
        start=1,
    ):
        chunks.append(
            LoadedChunk(
                document_id=f"{path.stem}-{chunk_index:03d}",
                title=title,
                content=chunk_text,
                source_path=str(path),
                chunk_index=chunk_index,
                chunk_size_words=chunk_size_words,
                chunk_overlap_words=chunk_overlap_words,
            )
        )

    return chunks


def _serialize_meta() -> str:
    return json.dumps(
        {
            "record_type": "meta",
            "chunk_size_words": CHUNK_SIZE_WORDS,
            "chunk_overlap_words": CHUNK_OVERLAP_WORDS,
            "chunking_version": CHUNKING_VERSION,
        },
        ensure_ascii=False,
    )


def _serialize_chunk(chunk: LoadedChunk) -> str:
    return json.dumps(
        {
            "record_type": "chunk",
            "document_id": chunk.document_id,
            "title": chunk.title,
            "content": chunk.content,
            "source_path": chunk.source_path,
            "chunk_index": chunk.chunk_index,
            "chunk_size_words": chunk.chunk_size_words,
            "chunk_overlap_words": chunk.chunk_overlap_words,
        },
        ensure_ascii=False,
    )


def _deserialize_chunk(line: str) -> LoadedChunk:
    payload = json.loads(line)
    return LoadedChunk(
        document_id=payload["document_id"],
        title=payload["title"],
        content=payload["content"],
        source_path=payload["source_path"],
        chunk_index=payload["chunk_index"],
        chunk_size_words=payload["chunk_size_words"],
        chunk_overlap_words=payload["chunk_overlap_words"],
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

    with chunks_file.open("r", encoding="utf-8") as file_handle:
        first_non_empty_line = next((line for line in file_handle if line.strip()), "")

    if not first_non_empty_line:
        return bool(_iter_supported_raw_files(raw_data_dir))

    try:
        metadata = json.loads(first_non_empty_line)
    except json.JSONDecodeError:
        return True

    return metadata != {
        "record_type": "meta",
        "chunk_size_words": CHUNK_SIZE_WORDS,
        "chunk_overlap_words": CHUNK_OVERLAP_WORDS,
        "chunking_version": CHUNKING_VERSION,
    }


def build_processed_chunks(
    raw_data_dir: Path = RAW_DATA_DIR,
    chunks_file: Path = CHUNKS_FILE,
) -> tuple[LoadedChunk, ...]:
    chunks: list[LoadedChunk] = []

    for path in _iter_supported_raw_files(raw_data_dir):
        chunks.extend(_build_chunks(path))

    chunks_file.parent.mkdir(parents=True, exist_ok=True)
    with chunks_file.open("w", encoding="utf-8") as file_handle:
        file_handle.write(_serialize_meta())
        file_handle.write("\n")
        for chunk in chunks:
            file_handle.write(_serialize_chunk(chunk))
            file_handle.write("\n")

    return tuple(chunks)


def build_experiment_chunks(
    raw_data_dir: Path = RAW_DATA_DIR,
    chunk_size_words: int = CHUNK_SIZE_WORDS,
    chunk_overlap_words: int = CHUNK_OVERLAP_WORDS,
) -> tuple[LoadedChunk, ...]:
    chunks: list[LoadedChunk] = []
    for path in _iter_supported_raw_files(raw_data_dir):
        chunks.extend(
            _build_chunks(
                path,
                chunk_size_words=chunk_size_words,
                chunk_overlap_words=chunk_overlap_words,
            )
        )
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
            if line.strip() and json.loads(line).get("record_type") == "chunk"
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
