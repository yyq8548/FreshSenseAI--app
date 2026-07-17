from hashlib import sha256

import numpy as np
import pytest

from tools.open_set import OpenSetGate, OpenSetGateError


def _write_gate(
    path,
    model_path,
    *,
    labels=("freshapple", "rottenbanana"),
    fruits=("apple", "banana"),
):
    np.savez_compressed(
        path,
        schema_version=np.asarray([2], dtype=np.int32),
        feature_layer=np.asarray(["avg_pool"]),
        gate_labels=np.asarray(labels),
        gate_fruits=np.asarray(fruits),
        centroids=np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        thresholds=np.asarray([0.8, 0.8], dtype=np.float32),
        model_sha256=np.asarray([sha256(model_path.read_bytes()).hexdigest()]),
        catalog_sha256=np.asarray(["catalog-hash"]),
        manifest_sha256=np.asarray(["manifest-hash"]),
        calibration_source=np.asarray(["unit-test"]),
    )


def test_open_set_gate_accepts_near_centroid_and_rejects_distant_vector(tmp_path):
    model = tmp_path / "model.keras"
    model.write_bytes(b"model")
    artifact = tmp_path / "gate.npz"
    labels = ("freshapple", "rottenbanana")
    _write_gate(artifact, model, labels=labels)

    gate = OpenSetGate(artifact, expected_model_path=model, expected_labels=labels)

    accepted = gate.evaluate(np.asarray([1.0, 0.1], dtype=np.float32))
    assert accepted.accepted is True
    assert accepted.nearest_fruit == "apple"
    assert gate.evaluate(np.asarray([1.0, 1.0], dtype=np.float32)).accepted is False


def test_open_set_gate_is_bound_to_model_hash(tmp_path):
    model = tmp_path / "model.keras"
    model.write_bytes(b"original")
    artifact = tmp_path / "gate.npz"
    _write_gate(artifact, model)
    model.write_bytes(b"changed")

    with pytest.raises(OpenSetGateError, match="different vision model"):
        OpenSetGate(artifact, expected_model_path=model)


def test_open_set_gate_rejects_class_order_mismatch(tmp_path):
    model = tmp_path / "model.keras"
    model.write_bytes(b"model")
    artifact = tmp_path / "gate.npz"
    _write_gate(artifact, model)

    with pytest.raises(OpenSetGateError, match="prototype order"):
        OpenSetGate(
            artifact,
            expected_model_path=model,
            expected_labels=("rottenbanana", "freshapple"),
        )
