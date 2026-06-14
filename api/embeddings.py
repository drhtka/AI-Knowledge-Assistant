from __future__ import annotations

from functools import lru_cache
from importlib import metadata
from typing import Sequence

from packaging.version import InvalidVersion, Version

from api.settings import EMBEDDING_MODEL_NAME


def compose_embedding_text(title: str, content: str) -> str:
    return f"{title}\n{content}"


@lru_cache(maxsize=1)
def embedding_stack_available() -> bool:
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
def get_embedding_model(model_name: str = EMBEDDING_MODEL_NAME) -> object | None:
    if not embedding_stack_available():
        return None

    try:
        from sentence_transformers import SentenceTransformer
    except Exception:  # pragma: no cover - runtime dependency may be installed later
        return None

    try:
        return SentenceTransformer(model_name)
    except Exception:  # pragma: no cover - model download or initialization may fail at runtime
        return None


def encode_texts(
    texts: Sequence[str],
    *,
    model_name: str = EMBEDDING_MODEL_NAME,
) -> object | None:
    model = get_embedding_model(model_name)
    if model is None:
        return None

    try:
        return model.encode(
            list(texts),
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
    except Exception:
        return None


def encode_query(
    question: str,
    *,
    model_name: str = EMBEDDING_MODEL_NAME,
) -> object | None:
    return encode_texts((question,), model_name=model_name)


def vector_to_pgvector_literal(vector: object) -> str:
    values = vector.tolist() if hasattr(vector, "tolist") else vector
    if values and isinstance(values[0], (list, tuple)):
        values = values[0]
    return "[" + ",".join(f"{float(value):.12g}" for value in values) + "]"
