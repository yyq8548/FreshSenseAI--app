"""Run a real-model smoke test across every configured freshness class."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.state import AgentState
from tools.vision import DenseNetVisionTool
from utils.config import (
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    MODEL_PATH,
    OPEN_SET_GATE_PATH,
)
from utils.startup import validate_startup


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--maximum-candidates", type=int, default=50)
    args = parser.parse_args()

    dataset_root = args.dataset.resolve()
    manifest_path = args.manifest or dataset_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    labels = tuple(str(label) for label in manifest["class_order"])

    validate_startup(
        MODEL_PATH,
        KNOWLEDGE_BASE_PATH,
        FRUIT_CATALOG_PATH,
        OPEN_SET_GATE_PATH,
        True,
    )
    tool = DenseNetVisionTool(
        MODEL_PATH,
        open_set_gate_path=OPEN_SET_GATE_PATH,
        require_open_set_gate=True,
        enable_gradcam=False,
    )

    passed = 0
    for label in labels:
        candidates = [
            record
            for record in manifest["records"]
            if record["benchmark_split"] == "test" and record["label"] == label
        ]
        for candidate_index, record in enumerate(
            candidates[: args.maximum_candidates], start=1
        ):
            path = dataset_root / str(record["relative_path"])
            with Image.open(path) as source:
                state = tool.run(
                    AgentState(image=source.convert("RGB")),
                    generate_explanation=False,
                )
            if (
                state.decision != "unsupported_input"
                and state.prediction is not None
                and state.prediction.class_name == label
            ):
                print(
                    f"PASS {label:14s} confidence={state.prediction.confidence:.4f} "
                    f"candidate={candidate_index}"
                )
                passed += 1
                break
        else:
            raise RuntimeError(
                f"No accepted correct smoke sample was found for {label} within "
                f"{args.maximum_candidates} candidates."
            )

    print(f"Windows real-model smoke: {passed}/{len(labels)} classes passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
