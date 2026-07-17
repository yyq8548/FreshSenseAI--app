import numpy as np
from PIL import Image

from agent.state import AgentState, PredictionResult
from tools.explainability import GradCamExplainer
from tools.open_set import OpenSetGate, OpenSetGateError
from utils.config import (
    ENABLE_GRADCAM,
    FRUIT_CATALOG_PATH,
    IMAGE_SIZE,
    OPEN_SET_GATE_PATH,
    REQUIRE_OPEN_SET_GATE,
)
from utils.fruit_catalog import FruitCatalog, load_fruit_catalog


class DenseNetVisionTool:
    """Loads DenseNet201 and performs fruit freshness inference."""

    def __init__(
        self,
        model_path: str,
        catalog: FruitCatalog | None = None,
        catalog_path: str = FRUIT_CATALOG_PATH,
        open_set_gate_path: str | None = OPEN_SET_GATE_PATH,
        require_open_set_gate: bool = REQUIRE_OPEN_SET_GATE,
        enable_gradcam: bool = ENABLE_GRADCAM,
    ):
        self.model_path = model_path
        self.catalog = catalog or load_fruit_catalog(catalog_path)
        try:
            from tensorflow.keras.models import load_model

            self.model = load_model(model_path)
        except Exception as exc:
            raise RuntimeError("FreshSense could not load the configured vision model.") from exc

        self.open_set_gate: OpenSetGate | None = None
        self.feature_model = None
        if open_set_gate_path:
            try:
                from tensorflow.keras import Model

                self.open_set_gate = OpenSetGate(
                    open_set_gate_path,
                    expected_model_path=model_path,
                    expected_labels=self.catalog.class_names,
                )
                feature_layer = self.model.get_layer(self.open_set_gate.feature_layer)
                self.feature_model = Model(inputs=self.model.input, outputs=feature_layer.output)
                if int(feature_layer.output.shape[-1]) != self.open_set_gate.feature_size:
                    raise OpenSetGateError(
                        "The model feature size does not match the open-set artifact."
                    )
            except Exception as exc:
                if require_open_set_gate:
                    raise RuntimeError(
                        "FreshSense could not load its calibrated supported-input gate."
                    ) from exc
                self.open_set_gate = None
                self.feature_model = None
        elif require_open_set_gate:
            raise RuntimeError("FreshSense requires a calibrated supported-input gate.")

        self.gradcam_explainer: GradCamExplainer | None = None
        if enable_gradcam:
            try:
                self.gradcam_explainer = GradCamExplainer(self.model)
            except Exception:
                # Explanation availability must never change the safety decision.
                self.gradcam_explainer = None

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        image = image.resize(IMAGE_SIZE)
        arr = np.array(image).astype("float32") / 255.0
        arr = np.expand_dims(arr, axis=0)
        return arr

    def run(self, state: AgentState) -> AgentState:
        x = self._preprocess(state.image)
        gate_decision = None
        if self.open_set_gate is not None and self.feature_model is not None:
            feature = np.asarray(self.feature_model.predict(x, verbose=0)[0], dtype=np.float32)
            gate_decision = self.open_set_gate.evaluate(feature)
            state.metadata["open_set_gate"] = {
                "accepted": gate_decision.accepted,
                "nearest_label": gate_decision.nearest_label,
                "nearest_fruit": gate_decision.nearest_fruit,
                "similarity": gate_decision.similarity,
                "threshold": gate_decision.threshold,
                "artifact": self.open_set_gate.artifact_path.name,
                "calibration_source": self.open_set_gate.calibration_source,
            }
            if not gate_decision.accepted:
                state.decision = "unsupported_input"
                state.status = "unsupported_image"
                state.add_warning(
                    "FreshSense could not confirm that this is one supported fruit type. "
                    "No freshness prediction was produced."
                )
                state.add_trace(
                    "OpenSetGate rejected the image before freshness classification "
                    f"(similarity={gate_decision.similarity:.4f}, "
                    f"threshold={gate_decision.threshold:.4f})."
                )
                return state
            classifier_output = self.model.layers[-1](
                np.expand_dims(feature, axis=0), training=False
            )
            probs = np.asarray(classifier_output, dtype=np.float32)[0]
        else:
            probs = self.model.predict(x, verbose=0)[0]
        if len(probs) != len(self.catalog.class_names):
            raise RuntimeError("Vision model output does not match configured classes.")
        idx = int(np.argmax(probs))
        prediction = PredictionResult(
            class_name=self.catalog.class_names[idx],
            confidence=float(probs[idx]),
            raw_probabilities=probs.tolist(),
        )
        if gate_decision is not None:
            gate_fruit = gate_decision.nearest_fruit
            prediction_fruit = self.catalog.class_for_label(prediction.class_name).fruit_id
            if gate_fruit != prediction_fruit:
                state.metadata["open_set_gate"]["accepted"] = False
                state.metadata["open_set_gate"]["reason"] = "fruit_disagreement"
                state.decision = "unsupported_input"
                state.status = "unsupported_image"
                state.add_warning(
                    "FreshSense detected conflicting fruit signals and withheld the freshness result."
                )
                state.add_trace(
                "OpenSetGate and freshness classifier disagreed on the fruit type."
                )
                return state
        state.add_trace(
            f"DenseNetVisionTool predicted {prediction.class_name} "
            f"with confidence {prediction.confidence:.2%}."
        )

        if self.gradcam_explainer is not None:
            try:
                explanation = self.gradcam_explainer.explain(x, idx)
                explanation["target_class"] = prediction.class_name
                state.metadata["explainability"] = explanation
                state.add_trace(
                    "Grad-CAM generated an influence map from "
                    f"{explanation['layer']}."
                )
            except Exception as exc:
                state.metadata["explainability"] = {
                    "available": False,
                    "reason": type(exc).__name__,
                }
                state.add_trace("Grad-CAM explanation was unavailable for this result.")

        state.prediction = prediction
        return state
