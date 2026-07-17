from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

from examples.insurance_rag.app import create_app
from examples.insurance_rag.retriever import PolicyKnowledgeAssistant


POLICY = Path(__file__).parents[1] / "examples" / "insurance_rag" / "fictional_policy.json"


class _SemanticStub:
    model_name = "test-policy-embedder"

    def embed_passages(self, texts):
        vectors = np.zeros((len(list(texts)), 2), dtype=np.float32)
        vectors[:, 0] = 1.0
        return vectors

    def embed_query(self, query):
        return np.asarray([1.0, 0.0], dtype=np.float32)


def test_keyword_rag_returns_citation_and_human_review():
    assistant = PolicyKnowledgeAssistant(POLICY, semantic_enabled=False)

    answer = assistant.ask("What is the property deductible?")

    assert answer["status"] == "retrieved_policy_language"
    assert answer["citations"][0]["document_id"] == "property_deductible"
    assert answer["human_review_required"] is True
    assert "fictional" in answer["disclaimer"].lower()


def test_keyword_rag_abstains_outside_policy_scope():
    assistant = PolicyKnowledgeAssistant(POLICY, semantic_enabled=False)

    answer = assistant.ask("favorite restaurant")

    assert answer["status"] == "insufficient_evidence"
    assert answer["citations"] == []


def test_companion_api_has_typed_health_and_ask_routes():
    assistant = PolicyKnowledgeAssistant(POLICY, semantic_enabled=False)
    with TestClient(create_app(assistant)) as client:
        health = client.get("/health")
        answer = client.post("/ask", json={"question": "When is proof of loss due?"})

    assert health.status_code == 200
    assert health.json()["fictional_data_only"] is True
    assert answer.status_code == 200
    assert answer.json()["citations"][0]["document_id"] == "proof_of_loss"


def test_semantic_path_reports_semantic_method():
    assistant = PolicyKnowledgeAssistant(POLICY, embedder=_SemanticStub())

    answer = assistant.ask("policy question")

    assert answer["retrieval_method"] == "semantic"
