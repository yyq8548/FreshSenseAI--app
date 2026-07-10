from PIL import Image

from agent.state import AgentState, PredictionResult
from tools.reasoning import RuleBasedReasoningTool


def test_reasoning_for_fresh_apple():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="freshapples",
        confidence=0.98,
        raw_probabilities=[],
    )

    tool = RuleBasedReasoningTool()
    state = tool.run(state)

    assert state.reasoning is not None
    assert state.reasoning.risk_level == "low"
    assert "apple" in state.reasoning.explanation.lower()
    assert "5-7" in state.reasoning.shelf_life_estimate


def test_reasoning_for_rotten_orange():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="rottenoranges",
        confidence=0.96,
        raw_probabilities=[],
    )

    tool = RuleBasedReasoningTool()
    state = tool.run(state)

    assert state.reasoning is not None
    assert state.reasoning.risk_level == "high"
    assert "discard" in state.reasoning.storage_advice.lower() or "avoid" in state.reasoning.storage_advice.lower()
