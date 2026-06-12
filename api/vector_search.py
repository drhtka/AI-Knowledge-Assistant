from __future__ import annotations

from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from api.ingestion import LoadedChunk
from api.settings import EMBEDDING_MODEL_NAME

try:
    from sentence_transformers import SentenceTransformer
except ImportError:  # pragma: no cover - runtime dependency may be installed later
    SentenceTransformer = None


def _chunk_text(chunk: LoadedChunk) -> str:
    return f"{chunk.title}\n{chunk.content}"


@lru_cache(maxsize=1)
def _build_tfidf_index(
    corpus_signature: tuple[tuple[str, str, str], ...],
) -> tuple[TfidfVectorizer, object]:
    # Keep a cached vector index for the latest processed corpus.
    documents = [
        _chunk_text(LoadedChunk(document_id=document_id, title=title, content=content))
        for document_id, title, content in corpus_signature
    ]
    vectorizer = TfidfVectorizer(lowercase=True, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(documents)
    return vectorizer, matrix


@lru_cache(maxsize=1)
def _get_embedding_model(model_name: str) -> SentenceTransformer | None:
    if SentenceTransformer is None:
        return None

    return SentenceTransformer(model_name)


@lru_cache(maxsize=1)
def _build_embedding_index(
    corpus_signature: tuple[tuple[str, str, str], ...],
    model_name: str,
) -> object | None:
    model = _get_embedding_model(model_name)
    if model is None:
        return None

    documents = [
        _chunk_text(LoadedChunk(document_id=document_id, title=title, content=content))
        for document_id, title, content in corpus_signature
    ]
    return model.encode(documents, convert_to_numpy=True, normalize_embeddings=True)


def rank_chunks_by_similarity(question: str, chunks: tuple[LoadedChunk, ...]) -> list[tuple[LoadedChunk, float]]:
    if not question.strip() or not chunks:
        return []

    corpus_signature = tuple(
        (chunk.document_id, chunk.title, chunk.content)
        for chunk in chunks
    )

    try:
        embedding_matrix = _build_embedding_index(
            corpus_signature=corpus_signature,
            model_name=EMBEDDING_MODEL_NAME,
        )
    except ValueError:
        embedding_matrix = None

    if embedding_matrix is not None:
        model = _get_embedding_model(EMBEDDING_MODEL_NAME)
        if model is not None:
            query_vector = model.encode(
                [question],
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            similarity_scores = cosine_similarity(query_vector, embedding_matrix).ravel()
        else:
            similarity_scores = []
    else:
        try:
            vectorizer, matrix = _build_tfidf_index(corpus_signature)
        except ValueError:
            return []

        query_vector = vectorizer.transform([question])
        similarity_scores = cosine_similarity(query_vector, matrix).ravel()

    ranked_results = sorted(
        (
            (chunk, float(score))
            for chunk, score in zip(chunks, similarity_scores, strict=False)
            if score > 0
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    return ranked_results
