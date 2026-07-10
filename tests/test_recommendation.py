from PIL import Image

from agent.state import AgentState, PredictionResult, ReasoningResult
from tools.recommendation import RecommendationTool
from utils.fruit_catalog import parse_fruit_catalog


def test_recommendation_for_retake():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.decision = "retake_photo"

    tool = RecommendationTool()
    state = tool.run(state)

    assert "retake" in state.recommendation.lower()


def test_recommendation_for_uncertain_input_names_supported_scope():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.decision = "uncertain_input"
    state.prediction = PredictionResult("freshbanana", 0.55, [0.55, 0.45])

    state = RecommendationTool().run(state)

    assert "could not produce a supported" in state.recommendation.lower()
    assert "apple" in state.recommendation.lower()
    assert "banana" in state.recommendation.lower()
    assert "orange" in state.recommendation.lower()


def test_recommendation_includes_reasoning_details():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="freshbanana",
        confidence=0.93,
        raw_probabilities=[],
    )
    state.reasoning = ReasoningResult(
        explanation="Fresh banana detected.",
        shelf_life_estimate="2-5 days at room temperature",
        storage_advice="Store at room temperature.",
        risk_level="low",
    )

    tool = RecommendationTool()
    state = tool.run(state)

    assert "2-5 days" in state.recommendation
    assert "store" in state.recommendation.lower()


def test_recommendation_uses_configured_freshness_not_label_text():
    catalog = parse_fruit_catalog(
        {
            "schema_version": 1,
            "classes": [
                {"label": "goodmango", "fruit": "mango", "freshness": "fresh"},
                {"label": "spoiledmango", "fruit": "mango", "freshness": "rotten"},
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
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult("spoiledmango", 0.96, [])

    state = RecommendationTool(catalog=catalog).run(state)

    assert "rotten or low-quality" in state.recommendation
