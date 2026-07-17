"""Build the FreshSense supported-input open-set artifact."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.gate_builder import build_open_set_gate
from evaluation.manifest import discover_dataset_root
from utils.config import FRUIT_CATALOG_PATH, MODEL_PATH, OPEN_SET_GATE_PATH
from utils.fruit_catalog import load_fruit_catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--model", type=Path, default=Path(MODEL_PATH))
    parser.add_argument("--output", type=Path, default=Path(OPEN_SET_GATE_PATH))
    parser.add_argument(
        "--summary",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "reports" / "open_set_calibration.json",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--minimum-supported-coverage", type=float, default=0.95)
    parser.add_argument("--minimum-final-supported-coverage", type=float, default=0.90)
    parser.add_argument("--synthetic-ood-count", type=int, default=192)
    parser.add_argument("--synthetic-rejection-quantile", type=float, default=0.99)
    args = parser.parse_args()

    catalog = load_fruit_catalog(FRUIT_CATALOG_PATH)
    dataset_root = discover_dataset_root(args.dataset, catalog.class_names)
    summary = build_open_set_gate(
        manifest_path=args.manifest,
        dataset_root=dataset_root,
        model_path=args.model,
        catalog_path=FRUIT_CATALOG_PATH,
        catalog=catalog,
        output_path=args.output,
        summary_path=args.summary,
        batch_size=args.batch_size,
        minimum_supported_coverage=args.minimum_supported_coverage,
        minimum_final_supported_coverage=args.minimum_final_supported_coverage,
        synthetic_ood_count=args.synthetic_ood_count,
        synthetic_rejection_quantile=args.synthetic_rejection_quantile,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
