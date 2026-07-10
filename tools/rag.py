import json
import os
import re
from collections import Counter
from typing import Dict, List

from agent.state import AgentState, RetrievalResult
from utils.config import FRUIT_CATALOG_PATH, KNOWLEDGE_BASE_PATH, RAG_TOP_K
from utils.fruit_catalog import FruitCatalog, load_fruit_catalog


class FoodKnowledgeRetriever:
    """
    Lightweight local RAG retriever.

    This uses keyword overlap rather than embeddings to keep the project simple,
    free to run locally, and easy to test. It can later be replaced with vector
    search using embeddings.
    """

    def __init__(
        self,
        knowledge_base_path: str = KNOWLEDGE_BASE_PATH,
        top_k: int = RAG_TOP_K,
        catalog: FruitCatalog | None = None,
        catalog_path: str = FRUIT_CATALOG_PATH,
    ):
        self.knowledge_base_path = knowledge_base_path
        self.top_k = top_k
        self.catalog = catalog or load_fruit_catalog(catalog_path)
        self.documents = self._load_documents()

    def run(self, state: AgentState) -> AgentState:
        query = self._build_query(state)
        docs = self.retrieve(query=query, state=state)

        state.retrieval = RetrievalResult(query=query, documents=docs)
        state.add_trace(f"FoodKnowledgeRetriever retrieved {len(docs)} documents.")
        return state

    def retrieve(self, query: str, state: AgentState | None = None) -> List[Dict]:
        query_tokens = self._tokenize(query)
        query_counter = Counter(query_tokens)

        scored_docs = []
        for doc in self.documents:
            doc_text = " ".join([
                doc.get("fruit", ""),
                doc.get("topic", ""),
                doc.get("text", ""),
            ])
            doc_tokens = self._tokenize(doc_text)
            doc_counter = Counter(doc_tokens)

            score = sum(min(query_counter[tok], doc_counter[tok]) for tok in query_counter)

            # Fruit-specific boost based on prediction label.
            if state and state.prediction:
                fruit_type = self._extract_fruit_type(state.prediction.class_name)
                if doc.get("fruit") == fruit_type:
                    score += 3
                if doc.get("fruit") == "general":
                    score += 1

            if score > 0:
                scored_docs.append((score, doc))

        scored_docs.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored_docs[: self.top_k]]

    def _load_documents(self) -> List[Dict]:
        if not os.path.exists(self.knowledge_base_path):
            return []

        with open(self.knowledge_base_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_query(self, state: AgentState) -> str:
        if state.prediction is None:
            return "general fruit storage shelf life food safety spoilage"

        class_definition = self.catalog.class_for_label(state.prediction.class_name)
        freshness = class_definition.freshness
        fruit_type = class_definition.fruit_id

        return f"{fruit_type} {freshness} storage shelf life food safety spoilage"

    def _extract_fruit_type(self, label: str) -> str:
        return self.catalog.class_for_label(label).fruit_id

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z]+", text.lower())
