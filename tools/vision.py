import numpy as np
from PIL import Image

from agent.state import AgentState, PredictionResult
from utils.config import CLASS_NAMES, IMAGE_SIZE


class DenseNetVisionTool:
    """Loads DenseNet201 and performs fruit freshness inference."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        try:
            from tensorflow.keras.models import load_model

            self.model = load_model(model_path)
        except Exception as exc:
            raise RuntimeError("FreshSense could not load the configured vision model.") from exc

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        image = image.resize(IMAGE_SIZE)
        arr = np.array(image).astype("float32") / 255.0
        arr = np.expand_dims(arr, axis=0)
        return arr

    def run(self, state: AgentState) -> AgentState:
        x = self._preprocess(state.image)

        probs = self.model.predict(x, verbose=0)[0]
        if len(probs) != len(CLASS_NAMES):
            raise RuntimeError("Vision model output does not match configured classes.")
        idx = int(np.argmax(probs))
        prediction = PredictionResult(
            class_name=CLASS_NAMES[idx],
            confidence=float(probs[idx]),
            raw_probabilities=probs.tolist(),
        )
        state.add_trace(
            f"DenseNetVisionTool predicted {prediction.class_name} "
            f"with confidence {prediction.confidence:.2%}."
        )

        state.prediction = prediction
        return state
