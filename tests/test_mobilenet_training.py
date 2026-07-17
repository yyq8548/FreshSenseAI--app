import numpy as np
import pytest

from training.mobilenet import classification_metrics, select_manifest_records


def _manifest():
    return {
        "records": [
            {
                "benchmark_split": "train",
                "supported": True,
                "label": "freshapple",
                "freshness": "fresh",
                "relative_path": "train/a.png",
                "sha256": "same",
            },
            {
                "benchmark_split": "train",
                "supported": True,
                "label": "freshapple",
                "freshness": "fresh",
                "relative_path": "train/a-copy.png",
                "sha256": "same",
            },
            {
                "benchmark_split": "test",
                "supported": True,
                "label": "rottenapple",
                "freshness": "rotten",
                "relative_path": "test/b.png",
                "sha256": "different",
            },
        ]
    }


def test_manifest_selection_is_split_scoped_and_byte_deduplicated():
    selected = select_manifest_records(_manifest(), "train")

    assert len(selected) == 1
    assert selected[0]["sha256"] == "same"


def test_manifest_selection_rejects_unknown_split():
    with pytest.raises(ValueError, match="train, validation, or test"):
        select_manifest_records(_manifest(), "legacy")


def test_classification_metrics_track_false_fresh():
    metrics = classification_metrics(
        np.asarray([0, 1, 1]),
        np.asarray([0, 0, 1]),
        np.asarray([[0.9, 0.1], [0.8, 0.2], [0.1, 0.9]]),
        class_names=("freshapple", "rottenapple"),
        freshness_by_label={"freshapple": "fresh", "rottenapple": "rotten"},
    )

    assert metrics["accuracy"] == pytest.approx(2 / 3)
    assert metrics["rotten_to_fresh_errors"] == 1
    assert metrics["rotten_to_fresh_rate"] == pytest.approx(0.5)
