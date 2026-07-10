from PIL import Image

from agent.state import AgentState, PredictionResult
from tools.llm_reasoning import LLMReasoningTool


def test_llm_reasoning_falls_back_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult(
        class_name="freshbanana",
        confidence=0.95,
        raw_probabilities=[],
    )

    tool = LLMReasoningTool()
    state = tool.run(state)

    assert state.reasoning is not None
    assert state.reasoning.source == "rule_based"
    assert "banana" in state.reasoning.explanation.lower()
