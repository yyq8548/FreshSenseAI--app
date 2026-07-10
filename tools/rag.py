"""Curated local semantic retrieval with a transparent keyword fallback."""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from typing import Dict, List

import numpy as np

from agent.state import AgentState, RetrievalResult
from tools.embeddings import FastEmbedTextEmbedder, TextEmbedder
from utils.config import (
    EMBEDDING_CACHE_DIR,
    EMBEDDING_LOCAL_FILES_ONLY,
    EMBEDDING_MODEL_NAME,
    EMBEDDING_THREADS,
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    RAG_TOP_K,
    SEMANTIC_RAG_ENABLED,
)
from utils.fruit_catalog import FruitCatalog, load_fruit_catalog


class FoodKnowledgeRetriever:
    """Rank reviewed food guidance with local dense text embeddings."""

    def __init__(
        self,
        knowledge_base_path: str = KNOWLEDGE_BASE_PATH,
        top_k: int = RAG_TOP_K,
        catalog: FruitCatalog | None = None,
        catalog_path: str = FRUIT_CATALOG_PATH,
        embedder: TextEmbedder | None = None,
        semantic_enabled: bool = SEMANTIC_RAG_ENABLED,
    ):
        self.knowledge_base_path = knowledge_base_path
        self.top_k = top_k
        self.catalog = catalog or load_fruit_catalog(catalog_path)
        self.documents = self._load_documents()
        self.semantic_enabled = semantic_enabled
        self.embedder: TextEmbedder | None = None
        self._document_embeddings: np.ndarray | None = None
        self.semantic_error_type: str | None = None
        self.last_method = "keyword"

        if semantic_enabled:
            self._initialize_semantic_retrieval(embedder)

    @property
    def semantic_ready(self) -> bool:
        return self.embedder is not None and self._document_embeddings is not None

    def run(self, state: AgentState) -> AgentState:
        query = self._build_query(state)
        docs = self.retrieve(query=query, state=state)

        state.retrieval = RetrievalResult(query=query, documents=docs)
        state.metadata["retrieval"] = {
            "method": self.last_method,
            "model": (
                self.embedder.model_name if self.last_method == "semantic" and self.embedder else None
            ),
            "documents": len(docs),
        }
        if self.last_method == "semantic":
            state.add_trace(
                f"FoodKnowledgeRetriever semantically retrieved {len(docs)} documents "
                f"with {self.embedder.model_name}."
            )
        else:
            if self.semantic_enabled:
                state.add_warning(
                    "Semantic knowledge retrieval is unavailable; using local keyword retrieval.",
                    level="suggestion",
                )
            state.add_trace(
                f"FoodKnowledgeRetriever used keyword fallback for {len(docs)} documents "
                f"({self.semantic_error_type or 'semantic retrieval disabled'})."
            )
        return state

    def retrieve(self, query: str, state: AgentState | None = None) -> List[Dict]:
        eligible_indices = self._eligible_indices(state)
        if self.semantic_ready:
            try:
                documents = self._semantic_retrieve(query, eligible_indices)
                self.last_method = "semantic"
                return documents
            except Exception as exc:
                self.semantic_error_type = type(exc).__name__
                self.embedder = None
                self._document_embeddings = None

        self.last_method = "keyword_fallback" if self.semantic_enabled else "keyword"
        return self._keyword_retrieve(query, eligible_indices)

    def _initialize_semantic_retrieval(self, embedder: TextEmbedder | None) -> None:
        try:
            active_embedder = embedder or FastEmbedTextEmbedder(
                model_name=EMBEDDING_MODEL_NAME,
                cache_dir=EMBEDDING_CACHE_DIR,
                local_files_only=EMBEDDING_LOCAL_FILES_ONLY,
                threads=EMBEDDING_THREADS,
            )
            passage_texts = [self._document_text(document) for document in self.documents]
            embeddings = np.asarray(
                active_embedder.embed_passages(passage_texts),
                dtype=np.float32,
            )
            if embeddings.ndim != 2 or embeddings.shape[0] != len(self.documents):
                raise RuntimeError("Embedding count does not match the knowledge base.")
            self._document_embeddings = _normalize_rows(embeddings)
            self.embedder = active_embedder
        except Exception as exc:
            self.semantic_error_type = type(exc).__name__
            self.embedder = None
            self._document_embeddings = None

    def _semantic_retrieve(self, query: str, eligible_indices: list[int]) -> List[Dict]:
        if not self.embedder or self._document_embeddings is None:
            raise RuntimeError("Semantic retrieval is not initialized.")
        query_embedding = _normalize_vector(self.embedder.embed_query(query))
        if query_embedding.shape[0] != self._document_embeddings.shape[1]:
            raise RuntimeError("Query and passage embedding dimensions do not match.")

        scored_docs = []
        for index in eligible_indices:
            score = float(np.dot(self._document_embeddings[index], query_embedding))
            scored_docs.append((score, self.documents[index]))
        scored_docs.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                **document,
                "retrieval_method": "semantic",
                "retrieval_score": round(score, 6),
            }
            for score, document in scored_docs[: self.top_k]
        ]

    def _keyword_retrieve(self, query: str, eligible_indices: list[int]) -> List[Dict]:
        query_counter = Counter(self._tokenize(query))
        scored_docs = []
        for index in eligible_indices:
            document = self.documents[index]
            doc_counter = Counter(self._tokenize(self._document_text(document)))
            score = sum(min(query_counter[token], doc_counter[token]) for token in query_counter)
            if score > 0:
                scored_docs.append((score, document))
        scored_docs.sort(key=lambda item: item[0], reverse=True)
        return [
            {
                **document,
                "retrieval_method": "keyword_fallback" if self.semantic_enabled else "keyword",
                "retrieval_score": float(score),
            }
            for score, document in scored_docs[: self.top_k]
        ]

    def _eligible_indices(self, state: AgentState | None) -> list[int]:
        if state is None:
            return list(range(len(self.documents)))
        if state.prediction is None:
            return [
                index
                for index, document in enumerate(self.documents)
                if document.get("fruit") == "general"
            ]

        fruit_id = self.catalog.class_for_label(state.prediction.class_name).fruit_id
        return [
            index
            for index, document in enumerate(self.documents)
            if document.get("fruit") in {fruit_id, "general"}
        ]

    def _load_documents(self) -> List[Dict]:
        if not os.path.exists(self.knowledge_base_path):
            return []
        with open(self.knowledge_base_path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _build_query(self, state: AgentState) -> str:
        if state.prediction is None:
            return "general fruit photo quality food safety and spoilage guidance"

        class_definition = self.catalog.class_for_label(state.prediction.class_name)
        fruit = self.catalog.fruits[class_definition.fruit_id]
        return (
            f"{fruit.display_name} {class_definition.freshness} produce: "
            "storage, shelf life, visible spoilage, and food safety guidance"
        )

    @staticmethod
    def _document_text(document: Dict) -> str:
        topic = str(document.get("topic", "")).replace("_", " ")
        return (
            f"Fruit: {document.get('fruit', '')}. "
            f"Topic: {topic}. "
            f"Guidance: {document.get('text', '')}"
        )

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z]+", text.lower())


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float32)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError("Passage embeddings must be a non-empty matrix.")
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("Passage embeddings cannot contain zero-length vectors.")
    return values / norms


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    value = np.asarray(vector, dtype=np.float32)
    if value.ndim != 1 or value.size == 0:
        raise ValueError("Query embedding must be a non-empty vector.")
    norm = float(np.linalg.norm(value))
    if norm == 0:
        raise ValueError("Query embedding cannot be a zero-length vector.")
    return value / norm
