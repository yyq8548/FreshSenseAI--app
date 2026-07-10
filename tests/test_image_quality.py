from PIL import Image

from agent.state import AgentState
from tools.image_quality import ImageQualityTool


def test_dark_image_is_flagged():
    image = Image.new("RGB", (224, 224), color="black")
    state = AgentState(image=image)

    tool = ImageQualityTool()
    state = tool.run(state)

    assert state.quality is not None
    assert state.quality.is_dark is True


def test_overexposed_image_is_flagged():
    image = Image.new("RGB", (224, 224), color="white")
    state = AgentState(image=image)

    tool = ImageQualityTool()
    state = tool.run(state)

    assert state.quality is not None
    assert state.quality.is_overexposed is True


def test_quality_tool_adds_trace():
    image = Image.new("RGB", (224, 224), color=(120, 120, 120))
    state = AgentState(image=image)

    tool = ImageQualityTool()
    state = tool.run(state)

    assert len(state.trace) > 0
