from pathlib import Path

import pytest
from PIL import Image

from agent.state import AgentState, ReasoningResult
from ui.presentation import analysis_signature, discover_sample_images, result_tone


def test_discover_sample_images_is_ordered_and_non_recursive(tmp_path: Path):
    for folder_name in ("apples", "bananas", "oranges"):
        folder = tmp_path / folder_name
        folder.mkdir()
        Image.new("RGB", (8, 8)).save(folder / "b.png")
        Image.new("RGB", (8, 8)).save(folder / "a.png")
        nested = folder / "nested"
        nested.mkdir()
        Image.new("RGB", (8, 8)).save(nested / "duplicate.png")

    samples = discover_sample_images(tmp_path, per_fruit=1)

    assert [sample.fruit_id for sample in samples] == ["apple", "banana", "orange"]
    assert all(sample.path.name == "a.png" for sample in samples)


def test_discover_sample_images_rejects_invalid_limit(tmp_path: Path):
    with pytest.raises(ValueError, match="at least one"):
        discover_sample_images(tmp_path, per_fruit=0)


def test_result_tone_reflects_decision_and_risk():
    state = AgentState(image=Image.new("RGB", (8, 8)))
    state.decision = "accept_prediction"
    state.reasoning = ReasoningResult("", "", "", "high")
    assert result_tone(state) == "danger"

    state.decision = "unsupported_input"
    assert result_tone(state) == "caution"


def test_analysis_signature_changes_with_content():
    assert analysis_signature("sample.png", b"one") != analysis_signature(
        "sample.png", b"two"
    )
