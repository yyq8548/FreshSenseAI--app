"""Manifest validation and serialization for reviewed orange failures."""

from __future__ import annotations

import csv
from pathlib import Path

from agent.state import AgentState


REQUIRED_COLUMNS = {
    "sample_id",
    "image_path",
    "physical_fruit_id",
    "expected_freshness",
    "device",
    "lighting",
    "background",
    "split",
}


class OrangeFailureManifestError(ValueError):
    """Raised when an orange review manifest cannot support valid analysis."""


def load_orange_failure_manifest(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
            raise OrangeFailureManifestError("Orange manifest is missing required columns.")
        rows = [
            {key: (value or "").strip() for key, value in row.items()}
            for row in reader
            if any((value or "").strip() for value in row.values())
        ]

    seen_ids: set[str] = set()
    fruit_splits: dict[str, set[str]] = {}
    for row_number, row in enumerate(rows, start=2):
        if not all(row[column] for column in REQUIRED_COLUMNS):
            raise OrangeFailureManifestError(
                f"Orange manifest row {row_number} contains an empty required value."
            )
        if row["sample_id"] in seen_ids:
            raise OrangeFailureManifestError("Orange sample_id values must be unique.")
        seen_ids.add(row["sample_id"])
        if row["expected_freshness"] not in {"fresh", "rotten"}:
            raise OrangeFailureManifestError("Expected freshness must be fresh or rotten.")
        if row["split"] not in {"train", "validation", "test", "failure-review"}:
            raise OrangeFailureManifestError("Orange manifest contains an invalid split.")
        fruit_splits.setdefault(row["physical_fruit_id"], set()).add(row["split"])

    leaking = [fruit_id for fruit_id, splits in fruit_splits.items() if len(splits) > 1]
    if leaking:
        raise OrangeFailureManifestError(
            "Photos of one physical fruit cannot appear in multiple splits."
        )
    return rows


def serialize_orange_failure(
    state: AgentState,
    *,
    sample_id: str,
    class_names: tuple[str, ...],
) -> dict[str, object]:
    probabilities = state.prediction.raw_probabilities if state.prediction else []
    distribution = sorted(
        (
            {"class_name": label, "probability": float(probability)}
            for label, probability in zip(class_names, probabilities)
        ),
        key=lambda item: item["probability"],
        reverse=True,
    )
    return {
        "sample_id": sample_id,
        "decision": state.decision,
        "status": state.status,
        "prediction": state.prediction.class_name if state.prediction else None,
        "confidence": state.prediction.confidence if state.prediction else None,
        "prediction_distribution": distribution,
        "open_set_gate": state.metadata.get("open_set_gate"),
        "quality": (
            {
                "brightness": state.quality.brightness,
                "edge_strength": state.quality.edge_strength,
                "is_dark": state.quality.is_dark,
                "is_blurry": state.quality.is_blurry,
                "is_overexposed": state.quality.is_overexposed,
            }
            if state.quality
            else None
        ),
        "scene": (
            {
                "foreground_ratio": state.scene.foreground_ratio,
                "fruit_is_too_small": state.scene.fruit_is_too_small,
                "likely_empty_scene": state.scene.likely_empty_scene,
            }
            if state.scene
            else None
        ),
        "gradcam_available": state.metadata.get("explainability", {}).get("method")
        == "grad_cam",
        "warnings": [warning.message for warning in state.structured_warnings],
    }
