import numpy as np
from PIL import ImageFilter

from agent.state import AgentState, SceneAnalysisResult
from utils.config import EDGE_THRESHOLD_FLOOR, MIN_FOREGROUND_RATIO, SMALL_FRUIT_RATIO


class SceneAnalysisTool:
    """
    Lightweight advisory scene validation tool.

    This tool adds scene-related warnings but does not block inference.
    It is intentionally advisory because edge-based heuristics can over-reject
    valid images with smooth fruit surfaces or simple backgrounds.
    """

    def __init__(
        self,
        min_foreground_ratio: float = MIN_FOREGROUND_RATIO,
        small_fruit_ratio: float = SMALL_FRUIT_RATIO,
    ):
        self.min_foreground_ratio = min_foreground_ratio
        self.small_fruit_ratio = small_fruit_ratio

    def run(self, state: AgentState) -> AgentState:
        image = state.image.convert("RGB")
        width, height = image.size

        gray = image.convert("L")
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_arr = np.array(edges).astype("float32")

        threshold = max(EDGE_THRESHOLD_FLOOR, float(edge_arr.mean() + edge_arr.std()))
        foreground_mask = edge_arr > threshold
        foreground_ratio = float(foreground_mask.mean())

        likely_empty_scene = foreground_ratio < self.min_foreground_ratio
        fruit_is_too_small = foreground_ratio < self.small_fruit_ratio
        needs_crop_or_closer_photo = likely_empty_scene or fruit_is_too_small

        state.scene = SceneAnalysisResult(
            image_width=width,
            image_height=height,
            foreground_ratio=foreground_ratio,
            fruit_is_too_small=fruit_is_too_small,
            likely_empty_scene=likely_empty_scene,
            needs_crop_or_closer_photo=needs_crop_or_closer_photo,
        )

        state.add_trace(
            f"SceneAnalysisTool completed as advisory check: foreground_ratio={foreground_ratio:.4f}."
        )

        if likely_empty_scene:
            state.add_warning(
                "Scene advisory: the image may contain limited visible fruit detail, but inference will continue.",
                level="suggestion",
            )
        elif fruit_is_too_small:
            state.add_warning(
                "Scene advisory: the fruit may be small in the frame. A closer photo may improve accuracy.",
                level="suggestion",
            )

        return state
