import json

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


def test_rag_handles_retake_state_without_prediction():
    state = AgentState(image=Image.new("RGB", (224, 224)))

    state = FoodKnowledgeRetriever().run(state)

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
    ).run(state)

    assert state.retrieval is not None
    assert state.retrieval.documents[0]["fruit"] == "mango"
