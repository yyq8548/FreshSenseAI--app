from PIL import Image

from agent.state import AgentState, PredictionResult, ReasoningResult
from tools.recommendation import RecommendationTool


def test_recommendation_for_retake():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.decision = "retake_photo"

    tool = RecommendationTool()
    state = tool.run(state)

    assert "retake" in state.recommendation.lower()


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
