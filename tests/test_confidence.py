from PIL import Image
import pytest

from agent.state import AgentState, PredictionResult
from tools.confidence import ConfidenceTool


def test_low_confidence_returns_uncertain_result():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="freshapples",
        confidence=0.50,
        raw_probabilities=[],
    )

    tool = ConfidenceTool(min_confidence=0.70)
    state = tool.run(state)

    assert state.decision == "uncertain_input"
    assert state.status == "unsupported_or_uncertain"
    assert "confidence_gate" in state.metadata


def test_high_confidence_accepts_prediction():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="freshapples",
        confidence=0.95,
        raw_probabilities=[0.95, 0.01, 0.01, 0.01, 0.01, 0.01],
    )

    tool = ConfidenceTool(min_confidence=0.70)
    state = tool.run(state)

    assert state.decision == "accept_prediction"
    assert state.status == "prediction_accepted"


def test_ambiguous_top_two_predictions_return_uncertain_result():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="freshapples",
        confidence=0.55,
        raw_probabilities=[0.55, 0.45],
    )

    state = ConfidenceTool(min_confidence=0.50, min_prediction_margin=0.15).run(state)

    assert state.decision == "uncertain_input"
    assert state.metadata["confidence_gate"]["prediction_margin"] == pytest.approx(0.10)
    assert "top-two prediction margin" in state.structured_warnings[0].message
