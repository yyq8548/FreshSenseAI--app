from PIL import Image

from agent.state import AgentState, PredictionResult
from tools.reasoning import RuleBasedReasoningTool
from utils.fruit_catalog import parse_fruit_catalog


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


def test_reasoning_uses_new_fruit_guidance_from_catalog():
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
                    "fresh_shelf_life": "3-5 configured days",
                    "fresh_storage_advice": "Use the configured mango storage guidance.",
                }
            ],
        }
    )
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult("freshmango", 0.97, [])

    state = RuleBasedReasoningTool(catalog=catalog).run(state)

    assert state.reasoning is not None
    assert "mango" in state.reasoning.explanation.lower()
    assert state.reasoning.shelf_life_estimate == "3-5 configured days"
    assert state.reasoning.storage_advice == "Use the configured mango storage guidance."
