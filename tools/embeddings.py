"""Local dense-text embedding backend used by semantic retrieval."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Protocol

import numpy as np


class EmbeddingUnavailableError(RuntimeError):
    """Raised when the configured local embedding backend cannot be used."""


class TextEmbedder(Protocol):
    model_name: str

    def embed_passages(self, texts: Iterable[str]) -> np.ndarray:
        """Return one dense vector per knowledge passage."""

    def embed_query(self, query: str) -> np.ndarray:
        """Return one dense vector for a retrieval query."""


class FastEmbedTextEmbedder:
    """CPU-only ONNX text embeddings through Qdrant FastEmbed."""

    def __init__(
        self,
        *,
        model_name: str,
        cache_dir: str,
        local_files_only: bool = True,
        threads: int = 2,
    ) -> None:
        self.model_name = model_name
        self.cache_dir = Path(cache_dir)
        try:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                model_name=model_name,
                cache_dir=str(self.cache_dir),
                threads=threads,
                local_files_only=local_files_only,
            )
        except Exception as exc:
            raise EmbeddingUnavailableError(
                "The configured local semantic-embedding model is unavailable."
            ) from exc

    def embed_passages(self, texts: Iterable[str]) -> np.ndarray:
        values = list(texts)
        if not values:
            return np.empty((0, 0), dtype=np.float32)
        try:
            vectors = list(self._model.passage_embed(values))
        except Exception as exc:
            raise EmbeddingUnavailableError("Knowledge passages could not be embedded.") from exc
        return _normalized_matrix(vectors)

    def embed_query(self, query: str) -> np.ndarray:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Semantic retrieval queries must be non-empty strings.")
        try:
            vectors = list(self._model.query_embed(query))
        except Exception as exc:
            raise EmbeddingUnavailableError("The semantic retrieval query could not be embedded.") from exc
        if len(vectors) != 1:
            raise EmbeddingUnavailableError("The embedding backend returned an invalid query shape.")
        return _normalized_vector(vectors[0])


def _normalized_matrix(vectors: Iterable[np.ndarray]) -> np.ndarray:
    matrix = np.asarray(list(vectors), dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise EmbeddingUnavailableError("The embedding backend returned an invalid passage shape.")
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise EmbeddingUnavailableError("The embedding backend returned a zero-length passage vector.")
    return matrix / norms


def _normalized_vector(vector: np.ndarray) -> np.ndarray:
    value = np.asarray(vector, dtype=np.float32)
    if value.ndim != 1 or value.size == 0:
        raise EmbeddingUnavailableError("The embedding backend returned an invalid query vector.")
    norm = float(np.linalg.norm(value))
    if norm == 0:
        raise EmbeddingUnavailableError("The embedding backend returned a zero-length query vector.")
    return value / norm
