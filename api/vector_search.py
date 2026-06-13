from __future__ import annotations

from functools import lru_cache
from importlib import metadata
from typing import Literal

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from packaging.version import InvalidVersion, Version

from api.ingestion import LoadedChunk
from api.settings import EMBEDDING_MODEL_NAME

RetrievalMode = Literal["auto", "tfidf", "embeddings"]

@lru_cache(maxsize=1)
def _build_tfidf_index(
    corpus_signature: tuple[tuple[str, str, str], ...],
) -> tuple[TfidfVectorizer, object]:
    # Keep a cached vector index for the latest processed corpus.
    documents = [
        f"{title}\n{content}"
        for _, title, content in corpus_signature
    ]
    vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(documents)
    return vectorizer, matrix


@lru_cache(maxsize=1)
def _embedding_stack_available() -> bool:
    try:
        torch_version = Version(metadata.version("torch"))
        transformers_version = Version(metadata.version("transformers"))
        numpy_version = Version(metadata.version("numpy"))
        metadata.version("sentence-transformers")
    except (metadata.PackageNotFoundError, InvalidVersion):
        return False

    # Newer Transformers disables older PyTorch versions at import time.
    if transformers_version >= Version("5.0.0") and torch_version < Version("2.4.0"):
        return False

    # PyTorch 2.2 wheels in this project are not compatible with NumPy 2.x.
    if numpy_version >= Version("2.0.0") and torch_version < Version("2.4.0"):
        return False

    return True


@lru_cache(maxsize=1)
def _get_embedding_model(model_name: str) -> object | None:
    if not _embedding_stack_available():
        return None

    try:
        from sentence_transformers import SentenceTransformer
    except Exception:  # pragma: no cover - runtime dependency may be installed later
        return None

    try:
        return SentenceTransformer(model_name)
    except Exception:  # pragma: no cover - model download or initialization may fail at runtime
        return None


@lru_cache(maxsize=1)
def _build_embedding_index(
    corpus_signature: tuple[tuple[str, str, str], ...],
    model_name: str,
) -> object | None:
    model = _get_embedding_model(model_name)
    if model is None:
        return None

    documents = [
        f"{title}\n{content}"
        for _, title, content in corpus_signature
    ]
    return model.encode(documents, convert_to_numpy=True, normalize_embeddings=True)


def _corpus_signature(chunks: tuple[LoadedChunk, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(
        (chunk.document_id, chunk.title, chunk.content)
        for chunk in chunks
    )


def _rank_from_scores(chunks: tuple[LoadedChunk, ...], similarity_scores: object) -> list[tuple[LoadedChunk, float]]:
    return sorted(
        (
            (chunk, float(score))
            for chunk, score in zip(chunks, similarity_scores, strict=False)
            if score > 0
        ),
        key=lambda item: item[1],
        reverse=True,
    )


def rank_chunks_by_tfidf(question: str, chunks: tuple[LoadedChunk, ...]) -> list[tuple[LoadedChunk, float]]:
    if not question.strip() or not chunks:
        return []

    try:
        vectorizer, matrix = _build_tfidf_index(_corpus_signature(chunks))
    except ValueError:
        return []

    query_vector = vectorizer.transform([question])
    similarity_scores = cosine_similarity(query_vector, matrix).ravel()
    return _rank_from_scores(chunks, similarity_scores)


def rank_chunks_by_embeddings(question: str, chunks: tuple[LoadedChunk, ...]) -> list[tuple[LoadedChunk, float]]:
    if not question.strip() or not chunks:
        return []

    try:
        embedding_matrix = _build_embedding_index(
            corpus_signature=_corpus_signature(chunks),
            model_name=EMBEDDING_MODEL_NAME,
        )
    except Exception:
        return []

    if embedding_matrix is None:
        return []

    model = _get_embedding_model(EMBEDDING_MODEL_NAME)
    if model is None:
        return []

    query_vector = model.encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    similarity_scores = cosine_similarity(query_vector, embedding_matrix).ravel()
    return _rank_from_scores(chunks, similarity_scores)


def rank_chunks_by_similarity(
    question: str,
    chunks: tuple[LoadedChunk, ...],
    mode: RetrievalMode = "auto",
) -> list[tuple[LoadedChunk, float]]:
    if mode == "tfidf":
        return rank_chunks_by_tfidf(question=question, chunks=chunks)
    if mode == "embeddings":
        return rank_chunks_by_embeddings(question=question, chunks=chunks)

    embedding_results = rank_chunks_by_embeddings(question=question, chunks=chunks)
    if embedding_results:
        return embedding_results

    return rank_chunks_by_tfidf(question=question, chunks=chunks)
