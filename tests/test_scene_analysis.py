from PIL import Image

from agent.state import AgentState
from tools.scene_analysis import SceneAnalysisTool


def test_blank_image_adds_advisory_but_does_not_fail():
    image = Image.new("RGB", (224, 224), color="white")
    state = AgentState(image=image)

    tool = SceneAnalysisTool(min_foreground_ratio=0.03, small_fruit_ratio=0.08)
    state = tool.run(state)

    assert state.scene is not None
    assert state.scene.likely_empty_scene is True
    assert len(state.structured_warnings) > 0


def test_scene_analysis_adds_trace():
    image = Image.new("RGB", (224, 224), color=(120, 120, 120))
    state = AgentState(image=image)

    tool = SceneAnalysisTool()
    state = tool.run(state)

    assert len(state.trace) > 0
