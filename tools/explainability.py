"""Grad-CAM influence maps for accepted FreshSense classifications."""

from __future__ import annotations

from base64 import b64encode
from io import BytesIO
from typing import Any

import numpy as np
from PIL import Image


GRADCAM_DISCLAIMER = (
    "The overlay highlights image regions that influenced the model. "
    "It does not prove spoilage or identify a food-safety hazard."
)


class ExplainabilityUnavailableError(RuntimeError):
    """Raised when a model cannot provide a valid Grad-CAM explanation."""


class GradCamExplainer:
    """Generate a normalized Grad-CAM map from the final spatial model layer."""

    def __init__(self, model: Any, layer_name: str | None = None) -> None:
        try:
            import tensorflow as tf

            self._tf = tf
            self.model = model
            self.layer_name = layer_name or find_last_spatial_layer(model)
            target_layer = model.get_layer(self.layer_name)
            classifier_output = model.outputs[0]
            self._gradient_model = tf.keras.Model(
                inputs=model.inputs,
                outputs=(target_layer.output, classifier_output),
            )
        except Exception as exc:
            raise ExplainabilityUnavailableError(
                "The configured model does not expose a Grad-CAM layer."
            ) from exc

    def explain(self, model_input: np.ndarray, class_index: int) -> dict[str, object]:
        values = np.asarray(model_input, dtype=np.float32)
        if values.ndim != 4 or values.shape[0] != 1:
            raise ExplainabilityUnavailableError(
                "Grad-CAM requires one preprocessed image batch."
            )
        if class_index < 0:
            raise ExplainabilityUnavailableError("Grad-CAM class index is invalid.")

        tf = self._tf
        try:
            tensor = tf.convert_to_tensor(values)
            with tf.GradientTape() as tape:
                convolution_output, predictions = self._gradient_model(
                    tensor, training=False
                )
                if class_index >= int(predictions.shape[-1]):
                    raise ExplainabilityUnavailableError(
                        "Grad-CAM class index exceeds the model output."
                    )
                target_score = predictions[:, class_index]
            gradients = tape.gradient(target_score, convolution_output)
            if gradients is None:
                raise ExplainabilityUnavailableError(
                    "The model did not produce explanation gradients."
                )
            pooled_gradients = tf.reduce_mean(gradients, axis=(0, 1, 2))
            spatial = convolution_output[0]
            heatmap = tf.reduce_sum(spatial * pooled_gradients, axis=-1)
            heatmap = tf.nn.relu(heatmap)
            maximum = float(tf.reduce_max(heatmap).numpy())
            if not np.isfinite(maximum) or maximum <= 0.0:
                raise ExplainabilityUnavailableError(
                    "The model produced an empty explanation map."
                )
            normalized = np.asarray(heatmap.numpy() / maximum, dtype=np.float32)
        except ExplainabilityUnavailableError:
            raise
        except Exception as exc:
            raise ExplainabilityUnavailableError(
                "The Grad-CAM explanation could not be generated."
            ) from exc

        return {
            "method": "grad_cam",
            "layer": self.layer_name,
            "target_class_index": class_index,
            "heatmap": normalized,
            "peak_activation": float(normalized.max()),
            "active_fraction": float(np.mean(normalized >= 0.5)),
            "disclaimer": GRADCAM_DISCLAIMER,
        }


def find_last_spatial_layer(model: Any) -> str:
    """Return the final layer whose output contains height, width, and channels."""
    for layer in reversed(getattr(model, "layers", ())):
        try:
            shape = tuple(layer.output.shape)
        except Exception:
            continue
        if len(shape) == 4 and all(value is None or int(value) > 0 for value in shape):
            return str(layer.name)
    raise ExplainabilityUnavailableError(
        "No spatial feature layer is available for Grad-CAM."
    )


def render_gradcam_overlay(
    image: Image.Image,
    heatmap: np.ndarray,
    *,
    alpha: float = 0.42,
) -> Image.Image:
    """Blend a compact heatmap over an RGB image without writing it to disk."""
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("Grad-CAM overlay alpha must be between 0 and 1.")
    values = np.asarray(heatmap, dtype=np.float32)
    if values.ndim != 2 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("Grad-CAM heatmap must be a finite two-dimensional array.")
    values = np.clip(values, 0.0, 1.0)
    small = Image.fromarray(np.uint8(values * 255), mode="L")
    resized = np.asarray(
        small.resize(image.size, Image.Resampling.BILINEAR), dtype=np.float32
    ) / 255.0

    red = np.clip(2.0 * resized, 0.0, 1.0)
    green = np.clip(2.0 - np.abs(4.0 * resized - 2.0), 0.0, 1.0)
    blue = np.clip(1.4 - 2.0 * resized, 0.0, 1.0)
    color = np.stack((red, green, blue), axis=-1)
    base = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    blended = (1.0 - alpha) * base + alpha * color
    return Image.fromarray(np.uint8(np.clip(blended, 0.0, 1.0) * 255), mode="RGB")


def gradcam_overlay_base64(image: Image.Image, heatmap: np.ndarray) -> str:
    """Encode an in-memory PNG overlay for an explicitly requested API response."""
    buffer = BytesIO()
    render_gradcam_overlay(image, heatmap).save(buffer, format="PNG", optimize=True)
    return b64encode(buffer.getvalue()).decode("ascii")
