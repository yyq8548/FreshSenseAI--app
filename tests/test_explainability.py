from types import SimpleNamespace

import numpy as np
from PIL import Image
import pytest

from tools.explainability import (
    ExplainabilityUnavailableError,
    find_last_spatial_layer,
    gradcam_overlay_base64,
    render_gradcam_overlay,
)


def test_find_last_spatial_layer_uses_final_rank_four_output():
    model = SimpleNamespace(
        layers=[
            SimpleNamespace(name="conv_a", output=SimpleNamespace(shape=(None, 14, 14, 32))),
            SimpleNamespace(name="conv_b", output=SimpleNamespace(shape=(None, 7, 7, 64))),
            SimpleNamespace(name="pool", output=SimpleNamespace(shape=(None, 64))),
        ]
    )

    assert find_last_spatial_layer(model) == "conv_b"


def test_find_last_spatial_layer_rejects_non_spatial_model():
    model = SimpleNamespace(
        layers=[SimpleNamespace(name="dense", output=SimpleNamespace(shape=(None, 6)))]
    )

    with pytest.raises(ExplainabilityUnavailableError, match="No spatial"):
        find_last_spatial_layer(model)


def test_gradcam_overlay_is_same_size_and_encodes_png():
    image = Image.new("RGB", (20, 12), "white")
    heatmap = np.asarray([[0.0, 0.5], [0.75, 1.0]], dtype=np.float32)

    overlay = render_gradcam_overlay(image, heatmap)
    encoded = gradcam_overlay_base64(image, heatmap)

    assert overlay.size == image.size
    assert overlay.mode == "RGB"
    assert encoded.startswith("iVBOR")


def test_gradcam_overlay_rejects_invalid_heatmap():
    with pytest.raises(ValueError, match="two-dimensional"):
        render_gradcam_overlay(Image.new("RGB", (10, 10)), np.asarray([0.0, 1.0]))
