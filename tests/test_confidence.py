from PIL import Image

from agent.state import AgentState, PredictionResult
from tools.confidence import ConfidenceTool


def test_low_confidence_requests_retake():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="freshapples",
        confidence=0.50,
        raw_probabilities=[],
    )

    tool = ConfidenceTool(min_confidence=0.70)
    state = tool.run(state)

    assert state.decision == "retake_photo"
    assert state.status == "low_confidence"


def test_high_confidence_accepts_prediction():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="freshapples",
        confidence=0.95,
        raw_probabilities=[],
    )

    tool = ConfidenceTool(min_confidence=0.70)
    state = tool.run(state)

    assert state.decision == "accept_prediction"
    assert state.status == "prediction_accepted"
