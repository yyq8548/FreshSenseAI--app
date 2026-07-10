import sys
import types

import numpy as np
import pytest
from PIL import Image

from agent.state import AgentState
from tools.vision import DenseNetVisionTool


def _install_fake_tensorflow(monkeypatch, model):
    models_module = types.ModuleType("tensorflow.keras.models")
    models_module.load_model = lambda _path: model
    keras_module = types.ModuleType("tensorflow.keras")
    keras_module.models = models_module
    tensorflow_module = types.ModuleType("tensorflow")
    tensorflow_module.keras = keras_module
    monkeypatch.setitem(sys.modules, "tensorflow", tensorflow_module)
    monkeypatch.setitem(sys.modules, "tensorflow.keras", keras_module)
    monkeypatch.setitem(sys.modules, "tensorflow.keras.models", models_module)


def test_model_load_failure_never_creates_demo_prediction(monkeypatch):
    models_module = types.ModuleType("tensorflow.keras.models")

    def fail_load(_path):
        raise OSError("invalid model")

    models_module.load_model = fail_load
    keras_module = types.ModuleType("tensorflow.keras")
    keras_module.models = models_module
    tensorflow_module = types.ModuleType("tensorflow")
    tensorflow_module.keras = keras_module
    monkeypatch.setitem(sys.modules, "tensorflow", tensorflow_module)
    monkeypatch.setitem(sys.modules, "tensorflow.keras", keras_module)
    monkeypatch.setitem(sys.modules, "tensorflow.keras.models", models_module)

    with pytest.raises(RuntimeError, match="could not load"):
        DenseNetVisionTool("missing.h5")


def test_model_output_must_match_configured_classes(monkeypatch):
    class InvalidModel:
        def predict(self, _input, verbose=0):
            return np.array([[0.8, 0.2]])

    _install_fake_tensorflow(monkeypatch, InvalidModel())
    tool = DenseNetVisionTool("model.h5")
    state = AgentState(image=Image.new("RGB", (224, 224)))

    with pytest.raises(RuntimeError, match="does not match"):
        tool.run(state)


def test_valid_model_prediction_is_used(monkeypatch):
    class ValidModel:
        def predict(self, _input, verbose=0):
            return np.array([[0.01, 0.92, 0.01, 0.02, 0.02, 0.02]])

    _install_fake_tensorflow(monkeypatch, ValidModel())
    tool = DenseNetVisionTool("model.h5")
    state = tool.run(AgentState(image=Image.new("RGB", (224, 224))))

    assert state.prediction is not None
    assert state.prediction.class_name == "freshbanana"
    assert state.prediction.confidence == pytest.approx(0.92)
    assert all("demo" not in step.lower() for step in state.trace)
