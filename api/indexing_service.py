from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
from time import perf_counter

from api.ingestion import (
    build_document_preview,
    build_processed_chunks,
    clear_chunks_cache,
    load_chunks,
    save_uploaded_document,
)

logger = logging.getLogger("ai_knowledge_assistant.indexing")


@dataclass(frozen=True)
class ReindexResult:
    document_count: int
    chunk_count: int
    elapsed_ms: int


@dataclass(frozen=True)
class UploadedDocumentResult:
    original_filename: str
    stored_path: Path
    file_type: str
    chunks_loaded: int
    preview_text: str


def _count_chunks_for_document(chunks: tuple, document_stem: str) -> int:
    return sum(1 for chunk in chunks if chunk.document_id.startswith(document_stem))


def ensure_index_loaded() -> tuple:
    chunks = load_chunks()
    logger.info(
        "Index loaded into memory.",
        extra={
            "event": "index_loaded",
            "context": {
                "chunk_count": len(chunks),
            },
        },
    )
    return chunks


def rebuild_index() -> ReindexResult:
    started_at = perf_counter()
    clear_chunks_cache()
    chunks = build_processed_chunks()
    clear_chunks_cache()
    elapsed_ms = int((perf_counter() - started_at) * 1000)
    result = ReindexResult(
        document_count=len({chunk.source_path for chunk in chunks}),
        chunk_count=len(chunks),
        elapsed_ms=elapsed_ms,
    )
    logger.info(
        "Rebuilt processed chunks index.",
        extra={
            "event": "index_rebuilt",
            "context": {
                "document_count": result.document_count,
                "chunk_count": result.chunk_count,
                "elapsed_ms": result.elapsed_ms,
            },
        },
    )
    return result


def ingest_uploaded_document(filename: str, content: bytes) -> UploadedDocumentResult:
    stored_path = save_uploaded_document(filename, content)
    reindex_result = rebuild_index()
    chunks_loaded = _count_chunks_for_document(load_chunks(), stored_path.stem)
    result = UploadedDocumentResult(
        original_filename=filename,
        stored_path=stored_path,
        file_type=stored_path.suffix.lower().lstrip(".") or "unknown",
        chunks_loaded=chunks_loaded,
        preview_text=build_document_preview(stored_path),
    )
    logger.info(
        "Uploaded document ingested and indexed.",
        extra={
            "event": "document_ingested",
            "context": {
                "filename": result.original_filename,
                "stored_name": result.stored_path.name,
                "file_type": result.file_type,
                "chunks_loaded": result.chunks_loaded,
                "index_chunk_count": reindex_result.chunk_count,
                "elapsed_ms": reindex_result.elapsed_ms,
            },
        },
    )
    return result
