from PIL import Image

from agent.state import AgentState, PredictionResult, ReasoningResult
from desktop.presenter import humanize_class_name, result_summary


def test_humanize_class_names():
    assert humanize_class_name("freshapples") == "Fresh Apple"
    assert humanize_class_name("rottenbanana") == "Rotten Banana"
    assert humanize_class_name("freshoranges") == "Fresh Orange"


def test_result_summary_contains_safety_guidance():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult("freshbanana", 0.93, [])
    state.reasoning = ReasoningResult(
        explanation="Visible features resemble fresh banana.",
        shelf_life_estimate="2-5 days",
        storage_advice="Store at room temperature.",
        risk_level="low",
    )
    state.recommendation = "Visual result only; inspect before eating."
    state.add_warning("Use a closer photo.", level="suggestion")

    summary = result_summary(state)

    assert summary["title"] == "Fresh Banana"
    assert summary["confidence"] == "93.0% model confidence"
    assert summary["risk"] == "Low"
    assert "Use a closer photo" in summary["details"]


def test_result_summary_handles_no_prediction():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.recommendation = "Please retake the photo."

    summary = result_summary(state)

    assert summary["title"] == "Photo retake needed"
    assert summary["confidence"] == "No reliable prediction"
