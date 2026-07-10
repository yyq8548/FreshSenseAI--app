import json

import numpy as np
from PIL import Image

from agent.state import AgentState, PredictionResult
from tools.rag import FoodKnowledgeRetriever
from utils.fruit_catalog import parse_fruit_catalog


def test_rag_retrieves_banana_documents():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="rottenbanana",
        confidence=0.99,
        raw_probabilities=[],
    )

    retriever = FoodKnowledgeRetriever(semantic_enabled=False)
    state = retriever.run(state)

    assert state.retrieval is not None
    assert len(state.retrieval.documents) > 0
    assert any(doc["fruit"] == "banana" for doc in state.retrieval.documents)


def test_rag_adds_trace():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="freshapples",
        confidence=0.95,
        raw_probabilities=[],
    )

    retriever = FoodKnowledgeRetriever(semantic_enabled=False)
    state = retriever.run(state)

    assert len(state.trace) > 0


def test_rag_handles_retake_state_without_prediction():
    state = AgentState(image=Image.new("RGB", (224, 224)))

    state = FoodKnowledgeRetriever(semantic_enabled=False).run(state)

    assert state.retrieval is not None
    assert state.retrieval.query.startswith("general fruit")


def test_rag_retrieves_knowledge_for_configured_new_fruit(tmp_path):
    catalog = parse_fruit_catalog(
        {
            "schema_version": 1,
            "classes": [
                {"label": "freshmango", "fruit": "mango", "freshness": "fresh"},
                {"label": "rottenmango", "fruit": "mango", "freshness": "rotten"},
            ],
            "fruits": [
                {
                    "id": "mango",
                    "display_name": "Mango",
                    "fresh_shelf_life": "3 days",
                    "fresh_storage_advice": "Store at room temperature.",
                }
            ],
        }
    )
    knowledge_path = tmp_path / "knowledge.json"
    knowledge_path.write_text(
        json.dumps(
            [
                {
                    "id": "mango_storage",
                    "fruit": "mango",
                    "topic": "storage",
                    "text": "Store mangoes at room temperature until ripe.",
                }
            ]
        ),
        encoding="utf-8",
    )
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult("freshmango", 0.95, [])

    state = FoodKnowledgeRetriever(
        knowledge_base_path=str(knowledge_path),
        catalog=catalog,
        semantic_enabled=False,
    ).run(state)

    assert state.retrieval is not None
    assert state.retrieval.documents[0]["fruit"] == "mango"


class _SemanticStub:
    model_name = "test/semantic-embedding"

    def embed_passages(self, texts):
        return np.asarray(
            [
                [1.0, 0.0] if "cold temperatures" in text.lower() else [0.0, 1.0]
                for text in texts
            ],
            dtype=np.float32,
        )

    def embed_query(self, query):
        return np.asarray([1.0, 0.0], dtype=np.float32)


class _BrokenEmbedder:
    model_name = "test/broken"

    def embed_passages(self, texts):
        raise RuntimeError("embedding backend failed")

    def embed_query(self, query):
        raise RuntimeError("embedding backend failed")


def test_semantic_rag_ranks_conceptual_match_without_keyword_overlap(tmp_path):
    knowledge_path = tmp_path / "semantic-knowledge.json"
    knowledge_path.write_text(
        json.dumps(
            [
                {
                    "id": "cold_storage",
                    "fruit": "general",
                    "topic": "handling",
                    "text": "Cold temperatures slow deterioration after harvest.",
                },
                {
                    "id": "photo_quality",
                    "fruit": "general",
                    "topic": "camera",
                    "text": "Use an evenly illuminated image with the subject centered.",
                },
            ]
        ),
        encoding="utf-8",
    )
    retriever = FoodKnowledgeRetriever(
        knowledge_base_path=str(knowledge_path),
        embedder=_SemanticStub(),
        semantic_enabled=True,
    )

    documents = retriever.retrieve("preserve produce after purchase")

    assert documents[0]["id"] == "cold_storage"
    assert documents[0]["retrieval_method"] == "semantic"
    assert documents[0]["retrieval_score"] == 1.0


def test_semantic_rag_reports_model_and_method_in_agent_state():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult("freshbanana", 0.95, [])
    retriever = FoodKnowledgeRetriever(
        embedder=_SemanticStub(),
        semantic_enabled=True,
    )

    state = retriever.run(state)

    assert state.metadata["retrieval"]["method"] == "semantic"
    assert state.metadata["retrieval"]["model"] == "test/semantic-embedding"
    assert all(
        document["fruit"] in {"banana", "general"}
        for document in state.retrieval.documents
    )


def test_semantic_rag_falls_back_transparently_when_embeddings_are_unavailable():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult("freshbanana", 0.95, [])
    retriever = FoodKnowledgeRetriever(
        embedder=_BrokenEmbedder(),
        semantic_enabled=True,
    )

    state = retriever.run(state)

    assert state.metadata["retrieval"]["method"] == "keyword_fallback"
    assert state.retrieval is not None
    assert len(state.retrieval.documents) > 0
    assert any("keyword retrieval" in warning.message for warning in state.structured_warnings)
