import csv

import pytest
from PIL import Image

from evaluation.manifest import EvaluationManifestError
from evaluation.real_world import REQUIRED_COLUMNS, build_real_world_manifest
from utils.fruit_catalog import load_fruit_catalog
from utils.config import FRUIT_CATALOG_PATH


def _write_annotations(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(**overrides):
    value = {
        "sample_id": "sample-1",
        "relative_path": "apple.jpg",
        "benchmark_split": "validation",
        "supported": "true",
        "label": "freshapples",
        "source_group": "physical-apple-1",
        "device": "phone-a",
        "lighting": "daylight",
        "background": "kitchen",
        "collection": "pilot-a",
        "reviewer": "reviewer-a",
        "notes": "",
    }
    value.update(overrides)
    return value


def test_real_world_manifest_supports_labeled_and_unsupported_images(tmp_path):
    Image.new("RGB", (20, 20), "red").save(tmp_path / "apple.jpg")
    Image.new("RGB", (20, 20), "blue").save(tmp_path / "object.jpg")
    annotations = tmp_path / "annotations.csv"
    _write_annotations(
        annotations,
        [
            _row(),
            _row(
                sample_id="sample-2",
                relative_path="object.jpg",
                benchmark_split="test",
                supported="false",
                label="",
                source_group="object-1",
            ),
        ],
    )

    manifest = build_real_world_manifest(
        annotations, tmp_path, catalog=load_fruit_catalog(FRUIT_CATALOG_PATH)
    )

    assert manifest["independent_real_world_benchmark"] is True
    assert manifest["records"][0]["label"] == "freshapples"
    assert manifest["records"][1]["supported"] is False
    assert manifest["records"][1]["label"] is None


def test_real_world_manifest_rejects_physical_group_leakage(tmp_path):
    Image.new("RGB", (20, 20), "red").save(tmp_path / "apple.jpg")
    Image.new("RGB", (20, 20), "red").save(tmp_path / "apple-2.jpg")
    annotations = tmp_path / "annotations.csv"
    _write_annotations(
        annotations,
        [
            _row(),
            _row(
                sample_id="sample-2",
                relative_path="apple-2.jpg",
                benchmark_split="test",
            ),
        ],
    )

    with pytest.raises(EvaluationManifestError, match="cross validation/test"):
        build_real_world_manifest(
            annotations, tmp_path, catalog=load_fruit_catalog(FRUIT_CATALOG_PATH)
        )
