"""Create the FreshSense model/evaluation artifact manifest."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.artifact_manifest import build_artifact_manifest, write_artifact_manifest
from utils.fruit_catalog import load_fruit_catalog
from utils.config import FRUIT_CATALOG_PATH
from utils.version import read_app_version


def main() -> int:
    catalog = load_fruit_catalog(FRUIT_CATALOG_PATH)
    artifacts = {
        "vision_model": PROJECT_ROOT / "models" / "densenet201.h5",
        "open_set_gate": PROJECT_ROOT / "models" / "open_set_gate.npz",
        "fruit_catalog": PROJECT_ROOT / "data" / "fruit_catalog.json",
        "knowledge_base": PROJECT_ROOT / "data" / "food_knowledge_base.json",
        "evaluation_manifest": PROJECT_ROOT
        / "evaluation"
        / "manifests"
        / "legacy_grouped_v1.json",
        "evaluation_report": PROJECT_ROOT
        / "evaluation"
        / "reports"
        / "current_model"
        / "evaluation_report.json",
        "gate_calibration_report": PROJECT_ROOT
        / "evaluation"
        / "reports"
        / "gate_calibration_final.json",
    }
    payload = build_artifact_manifest(
        project_root=PROJECT_ROOT,
        application_version=read_app_version(PROJECT_ROOT / "VERSION"),
        artifacts=artifacts,
        class_order=catalog.class_names,
        fruit_order=catalog.fruit_ids,
    )
    output = PROJECT_ROOT / "artifacts" / "model_manifest.json"
    digest = write_artifact_manifest(payload, output)
    print(f"Artifact manifest: {output}")
    print(f"Artifact manifest SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
