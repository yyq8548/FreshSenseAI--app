from PIL import Image

from agent.state import AgentState, PredictionResult
from tools.rag import FoodKnowledgeRetriever


def test_rag_retrieves_banana_documents():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="rottenbanana",
        confidence=0.99,
        raw_probabilities=[],
    )

    retriever = FoodKnowledgeRetriever()
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

    retriever = FoodKnowledgeRetriever()
    state = retriever.run(state)

    assert len(state.trace) > 0
