from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from api.settings import RAW_DATA_DIR

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


@lru_cache(maxsize=1)
def load_chunks(raw_data_dir: Path = RAW_DATA_DIR) -> tuple[LoadedChunk, ...]:
    # Cache the baseline corpus in memory for the current process.
    chunks: list[LoadedChunk] = []

    if not raw_data_dir.exists():
        return ()

    for path in sorted(raw_data_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name in IGNORED_FILENAMES:
            continue
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        chunks.extend(_build_chunks(path))

    return tuple(chunks)
