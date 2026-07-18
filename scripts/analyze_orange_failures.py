"""Run reproducible prediction and Grad-CAM review for orange failure cases."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.fruit_agent import FruitScannerAgent
from evaluation.orange_failures import (
    load_orange_failure_manifest,
    serialize_orange_failure,
)
from tools.explainability import render_gradcam_overlay
from utils.config import (
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    MODEL_PATH,
    OPEN_SET_GATE_PATH,
    REQUIRE_OPEN_SET_GATE,
)
from utils.version import APP_VERSION


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--overlay-dir", required=True, type=Path)
    args = parser.parse_args()

    rows = load_orange_failure_manifest(args.manifest)
    if not rows:
        raise SystemExit("Orange failure manifest contains no cases.")
    agent = FruitScannerAgent(
        model_path=MODEL_PATH,
        catalog_path=FRUIT_CATALOG_PATH,
        knowledge_base_path=KNOWLEDGE_BASE_PATH,
        open_set_gate_path=OPEN_SET_GATE_PATH,
        require_open_set_gate=REQUIRE_OPEN_SET_GATE,
    )
    args.overlay_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for row in rows:
        image_path = Path(row["image_path"])
        if not image_path.is_absolute():
            image_path = args.manifest.parent / image_path
        payload = image_path.read_bytes()
        image = Image.open(image_path).convert("RGB")
        state = agent.run(image)
        result = serialize_orange_failure(
            state,
            sample_id=row["sample_id"],
            class_names=agent.catalog.class_names,
        )
        result.update(
            {
                "physical_fruit_id": row["physical_fruit_id"],
                "expected_freshness": row["expected_freshness"],
                "device": row["device"],
                "lighting": row["lighting"],
                "background": row["background"],
                "split": row["split"],
                "input_sha256": sha256(payload).hexdigest(),
            }
        )
        explanation = state.metadata.get("explainability", {})
        if explanation.get("method") == "grad_cam":
            overlay_name = f"{row['sample_id']}-gradcam.png"
            render_gradcam_overlay(image, explanation["heatmap"]).save(
                args.overlay_dir / overlay_name,
                format="PNG",
            )
            result["gradcam_overlay"] = overlay_name
        results.append(result)

    report = {
        "schema_version": 1,
        "freshsense_version": APP_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Orange failure report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
