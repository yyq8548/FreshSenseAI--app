"""Run the versioned FreshSense evaluation bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.manifest import discover_dataset_root
from evaluation.runner import run_evaluation
from utils.config import FRUIT_CATALOG_PATH, MODEL_PATH, OPEN_SET_GATE_PATH
from utils.fruit_catalog import load_fruit_catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--model", type=Path, default=Path(MODEL_PATH))
    parser.add_argument("--gate", type=Path, default=Path(OPEN_SET_GATE_PATH))
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "reports" / "current_model",
    )
    parser.add_argument("--split", choices=("train", "validation", "test"), default="test")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--synthetic-ood-count", type=int, default=192)
    parser.add_argument("--max-supported-images", type=int)
    args = parser.parse_args()

    catalog = load_fruit_catalog(FRUIT_CATALOG_PATH)
    dataset_root = discover_dataset_root(args.dataset, catalog.class_names)
    report = run_evaluation(
        manifest_path=args.manifest,
        dataset_root=dataset_root,
        model_path=args.model,
        gate_path=args.gate,
        catalog=catalog,
        output_dir=args.output,
        split=args.split,
        batch_size=args.batch_size,
        synthetic_ood_count=args.synthetic_ood_count,
        max_supported_images=args.max_supported_images,
    )
    print(json.dumps(report["metrics"]["summary"], indent=2))
    print(f"Report bundle: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
