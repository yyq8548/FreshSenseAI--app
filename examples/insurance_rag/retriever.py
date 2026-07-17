"""Citation-first retrieval over an explicitly fictional insurance policy."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

import numpy as np

from tools.embeddings import FastEmbedTextEmbedder, TextEmbedder
from utils.config import (
    EMBEDDING_CACHE_DIR,
    EMBEDDING_LOCAL_FILES_ONLY,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_THREADS,
)


DEMO_DISCLAIMER = (
    "This uses a fictional policy for software demonstration only. It is not "
    "insurance, legal, coverage, pricing, or claims advice. Human review is required."
)
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "can",
        "does",
        "for",
        "how",
        "is",
        "it",
        "my",
        "of",
        "person",
        "should",
        "the",
        "this",
        "to",
        "what",
        "when",
    }
)


class PolicyKnowledgeAssistant:
    def __init__(
        self,
        policy_path: str | Path,
        *,
        embedder: TextEmbedder | None = None,
        semantic_enabled: bool = True,
        top_k: int = 3,
        minimum_semantic_score: float = 0.65,
        minimum_keyword_score: int = 2,
    ) -> None:
        self.policy_path = Path(policy_path)
        self.documents = _load_documents(self.policy_path)
        self.top_k = top_k
        self.minimum_semantic_score = minimum_semantic_score
        self.minimum_keyword_score = minimum_keyword_score
        self.embedder: TextEmbedder | None = None
        self.embeddings: np.ndarray | None = None
        self.semantic_error: str | None = None
        if semantic_enabled:
            try:
                self.embedder = embedder or FastEmbedTextEmbedder(
                    model_name=EMBEDDING_MODEL_NAME,
                    cache_dir=EMBEDDING_CACHE_DIR,
                    local_files_only=EMBEDDING_LOCAL_FILES_ONLY,
                    threads=EMBEDDING_THREADS,
                )
                self.embeddings = _normalize_rows(
                    self.embedder.embed_passages(
                        [_document_text(document) for document in self.documents]
                    )
                )
            except Exception as exc:
                self.semantic_error = type(exc).__name__
                self.embedder = None
                self.embeddings = None

    @property
    def semantic_ready(self) -> bool:
        return self.embedder is not None and self.embeddings is not None

    def ask(self, question: str) -> dict[str, object]:
        if not isinstance(question, str) or not question.strip():
            raise ValueError("A non-empty policy question is required.")
        documents, method = self._retrieve(question)
        if not documents:
            return {
                "status": "insufficient_evidence",
                "answer": (
                    "The fictional policy does not provide enough evidence to answer "
                    "this question. Refer it to a qualified human reviewer."
                ),
                "citations": [],
                "retrieval_method": method,
                "human_review_required": True,
                "disclaimer": DEMO_DISCLAIMER,
            }
        lead = documents[0]
        return {
            "status": "retrieved_policy_language",
            "answer": str(lead["text"]),
            "citations": [
                {
                    "document_id": document["id"],
                    "citation": document["citation"],
                    "score": document["score"],
                }
                for document in documents
            ],
            "retrieval_method": method,
            "human_review_required": True,
            "disclaimer": DEMO_DISCLAIMER,
        }

    def _retrieve(self, question: str) -> tuple[list[dict[str, Any]], str]:
        if self.semantic_ready:
            try:
                query = _normalize_vector(self.embedder.embed_query(question))
                semantic_scores = self.embeddings @ query
                query_tokens = Counter(_tokens(question))
                ranked = []
                for index, document in enumerate(self.documents):
                    document_tokens = Counter(_tokens(_document_text(document)))
                    keyword_score = sum(
                        min(query_tokens[token], document_tokens[token])
                        for token in query_tokens
                    )
                    semantic_score = float(semantic_scores[index])
                    if (
                        keyword_score < self.minimum_keyword_score
                        and semantic_score < self.minimum_semantic_score
                    ):
                        continue
                    hybrid_score = semantic_score + 0.08 * min(keyword_score, 3)
                    ranked.append((hybrid_score, semantic_score, keyword_score, document))
                ranked.sort(key=lambda item: (-item[0], str(item[3]["id"])))
                results = [
                    {
                        **document,
                        "score": round(hybrid_score, 6),
                        "semantic_score": round(semantic_score, 6),
                        "keyword_score": keyword_score,
                    }
                    for hybrid_score, semantic_score, keyword_score, document in ranked[: self.top_k]
                ]
                return results, "semantic"
            except Exception as exc:
                self.semantic_error = type(exc).__name__
                self.embedder = None
                self.embeddings = None

        query_tokens = Counter(_tokens(question))
        scored = []
        for document in self.documents:
            document_tokens = Counter(_tokens(_document_text(document)))
            score = sum(
                min(query_tokens[token], document_tokens[token]) for token in query_tokens
            )
            if score >= self.minimum_keyword_score:
                scored.append((score, document))
        scored.sort(key=lambda item: (-item[0], str(item[1]["id"])))
        return (
            [
                {**document, "score": float(score)}
                for score, document in scored[: self.top_k]
            ],
            "keyword_fallback",
        )


def _load_documents(path: Path) -> list[dict[str, str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("The fictional policy knowledge source is invalid.") from exc
    required = {"id", "citation", "topic", "text"}
    if not isinstance(value, list) or not value:
        raise ValueError("The fictional policy must contain documents.")
    if any(not isinstance(item, dict) or not required.issubset(item) for item in value):
        raise ValueError("A fictional policy document is missing required fields.")
    return [{key: str(item[key]) for key in required} for item in value]


def _document_text(document: dict[str, str]) -> str:
    return f"Topic: {document['topic']}. Citation: {document['citation']}. {document['text']}"


def _tokens(text: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOP_WORDS
    ]


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float32)
    if values.ndim != 2 or not values.size:
        raise ValueError("Policy passage embeddings are invalid.")
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("Policy passage embeddings contain a zero vector.")
    return values / norms


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    value = np.asarray(vector, dtype=np.float32)
    if value.ndim != 1 or not value.size:
        raise ValueError("Policy query embedding is invalid.")
    norm = float(np.linalg.norm(value))
    if norm == 0:
        raise ValueError("Policy query embedding is a zero vector.")
    return value / norm
