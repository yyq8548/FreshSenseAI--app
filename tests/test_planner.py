from PIL import Image

from agent.planner import Planner
from agent.state import AgentState, ImageQualityResult, PredictionResult, SceneAnalysisResult


def test_planner_requests_retake_for_dark_image():
    state = AgentState(image=Image.new("RGB", (224, 224), color="black"))
    state.quality = ImageQualityResult(
        brightness=20,
        edge_strength=100,
        is_dark=True,
        is_blurry=False,
        is_overexposed=False,
    )
    assert Planner().plan_after_quality_check(state) == "request_retake"


def test_planner_runs_scene_analysis_for_good_image():
    state = AgentState(image=Image.new("RGB", (224, 224), color="white"))
    state.quality = ImageQualityResult(
        brightness=120,
        edge_strength=200,
        is_dark=False,
        is_blurry=False,
        is_overexposed=False,
    )
    assert Planner().plan_after_quality_check(state) == "run_scene_analysis"


def test_scene_analysis_is_advisory_even_for_empty_scene():
    state = AgentState(image=Image.new("RGB", (224, 224), color="white"))
    state.scene = SceneAnalysisResult(
        image_width=224,
        image_height=224,
        foreground_ratio=0.01,
        fruit_is_too_small=True,
        likely_empty_scene=True,
        needs_crop_or_closer_photo=True,
    )
    assert Planner().plan_after_scene_analysis(state) == "run_vision"


def test_planner_runs_vision_for_valid_scene():
    state = AgentState(image=Image.new("RGB", (224, 224), color="white"))
    state.scene = SceneAnalysisResult(
        image_width=224,
        image_height=224,
        foreground_ratio=0.20,
        fruit_is_too_small=False,
        likely_empty_scene=False,
        needs_crop_or_closer_photo=False,
    )
    assert Planner().plan_after_scene_analysis(state) == "run_vision"


def test_planner_returns_uncertain_result_after_confidence_gate():
    state = AgentState(image=Image.new("RGB", (224, 224), color="white"))
    state.prediction = PredictionResult(
        class_name="freshapples",
        confidence=0.45,
        raw_probabilities=[],
    )
    state.decision = "uncertain_input"
    assert Planner().plan_after_inference(state) == "return_uncertain_result"


def test_planner_generates_recommendation_for_high_confidence():
    state = AgentState(image=Image.new("RGB", (224, 224), color="white"))
    state.prediction = PredictionResult(
        class_name="freshapples",
        confidence=0.95,
        raw_probabilities=[],
    )
    state.decision = "accept_prediction"
    assert Planner().plan_after_inference(state) == "generate_recommendation"
