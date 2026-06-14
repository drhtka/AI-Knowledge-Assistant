from __future__ import annotations

from functools import lru_cache
from typing import Literal

from api.embeddings import compose_embedding_text, encode_query, encode_texts
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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
def _build_embedding_index(
    corpus_signature: tuple[tuple[str, str, str], ...],
    model_name: str,
) -> object | None:
    documents = [
        compose_embedding_text(title, content)
        for _, title, content in corpus_signature
    ]
    return encode_texts(documents, model_name=model_name)


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

    query_vector = encode_query(question, model_name=EMBEDDING_MODEL_NAME)
    if query_vector is None:
        return []

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
