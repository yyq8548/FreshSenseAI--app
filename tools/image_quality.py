import numpy as np
from PIL import ImageFilter

from agent.state import AgentState, ImageQualityResult
from utils.config import BLUR_THRESHOLD, DARK_THRESHOLD, OVEREXPOSED_THRESHOLD


class ImageQualityTool:
    """Checks whether the uploaded image is suitable for model inference."""

    def __init__(
        self,
        dark_threshold: float = DARK_THRESHOLD,
        overexposed_threshold: float = OVEREXPOSED_THRESHOLD,
        blur_threshold: float = BLUR_THRESHOLD,
    ):
        self.dark_threshold = dark_threshold
        self.overexposed_threshold = overexposed_threshold
        self.blur_threshold = blur_threshold

    def run(self, state: AgentState) -> AgentState:
        gray = state.image.convert("L")
        arr = np.array(gray).astype("float32")

        brightness = float(arr.mean())
        is_dark = brightness < self.dark_threshold
        is_overexposed = brightness > self.overexposed_threshold

        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_arr = np.array(edges).astype("float32")
        edge_strength = float(edge_arr.var())
        is_blurry = edge_strength < self.blur_threshold

        state.quality = ImageQualityResult(
            brightness=brightness,
            edge_strength=edge_strength,
            is_dark=is_dark,
            is_blurry=is_blurry,
            is_overexposed=is_overexposed,
        )

        state.add_trace(
            f"ImageQualityTool completed: brightness={brightness:.2f}, "
            f"edge_strength={edge_strength:.2f}."
        )

        if is_dark:
            state.add_warning("Image is too dark. Retake in brighter lighting.")
        if is_blurry:
            state.add_warning("Image may be blurry. Retake with a steadier camera.")
        if is_overexposed:
            state.add_warning("Image may be overexposed. Avoid direct glare.")

        return state
