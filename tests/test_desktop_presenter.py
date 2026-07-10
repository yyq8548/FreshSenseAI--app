from PIL import Image

from agent.state import AgentState, PredictionResult, ReasoningResult
from desktop.presenter import humanize_class_name, result_summary, supported_scope_text
from utils.fruit_catalog import parse_fruit_catalog


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


def test_result_summary_reports_semantic_retrieval():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult("freshbanana", 0.93, [])
    state.reasoning = ReasoningResult(
        explanation="Visible features resemble fresh banana.",
        shelf_life_estimate="2-5 days",
        storage_advice="Store at room temperature.",
        risk_level="low",
    )
    state.metadata["retrieval"] = {"method": "semantic"}

    summary = result_summary(state)

    assert "Knowledge retrieval: Local semantic embeddings." in summary["details"]


def test_result_summary_reports_keyword_fallback():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult("freshbanana", 0.93, [])
    state.reasoning = ReasoningResult(
        explanation="Visible features resemble fresh banana.",
        shelf_life_estimate="2-5 days",
        storage_advice="Store at room temperature.",
        risk_level="low",
    )
    state.metadata["retrieval"] = {"method": "keyword_fallback"}

    summary = result_summary(state)

    assert "Knowledge retrieval: Keyword fallback." in summary["details"]


def test_result_summary_handles_no_prediction():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.recommendation = "Please retake the photo."

    summary = result_summary(state)

    assert summary["title"] == "Photo retake needed"
    assert summary["confidence"] == "No reliable prediction"


def test_result_summary_hides_tentative_uncertain_class():
    state = AgentState(image=Image.new("RGB", (224, 224)))
    state.prediction = PredictionResult("freshbanana", 0.55, [0.55, 0.45])
    state.decision = "uncertain_input"
    state.recommendation = "Try another supported photo."
    state.add_warning("The prediction was ambiguous.")

    summary = result_summary(state)

    assert summary["title"] == "Unsupported or uncertain photo"
    assert summary["confidence"] == "No supported result"
    assert "Fresh Banana" not in summary.values()
    assert "withheld" in summary["details"]


def test_supported_scope_is_derived_from_catalog():
    text = supported_scope_text()

    assert "Apple" in text
    assert "Banana" in text
    assert "Orange" in text


def test_humanize_uses_configured_new_fruit_name():
    catalog = parse_fruit_catalog(
        {
            "schema_version": 1,
            "classes": [
                {"label": "freshdragonfruit", "fruit": "dragonfruit", "freshness": "fresh"},
                {"label": "rottendragonfruit", "fruit": "dragonfruit", "freshness": "rotten"},
            ],
            "fruits": [
                {
                    "id": "dragonfruit",
                    "display_name": "Dragon Fruit",
                    "fresh_shelf_life": "Configured shelf life",
                    "fresh_storage_advice": "Configured storage advice.",
                }
            ],
        }
    )

    assert humanize_class_name("freshdragonfruit", catalog=catalog) == "Fresh Dragon Fruit"
