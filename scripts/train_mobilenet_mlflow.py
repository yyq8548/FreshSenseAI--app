"""Run a grouped MobileNetV2 FreshSense experiment tracked in local MLflow."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from training.mobilenet import MobileNetTrainingConfig, run_mobilenet_experiment


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "manifests" / "legacy_grouped_v1.json",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=os.getenv("FRESHSENSE_BENCHMARK_ROOT"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "work" / "mobilenetv2_experiment",
    )
    parser.add_argument(
        "--tracking-database",
        type=Path,
        default=PROJECT_ROOT / "work" / "mlflow.db",
    )
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=0.001)
    parser.add_argument("--weights", choices=("imagenet", "none"), default="imagenet")
    parser.add_argument("--run-name")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Use four images per class, one epoch, and no downloaded weights.",
    )
    args = parser.parse_args()
    if args.dataset_root is None:
        parser.error("--dataset-root or FRESHSENSE_BENCHMARK_ROOT is required")

    config = MobileNetTrainingConfig(
        manifest_path=args.manifest,
        dataset_root=args.dataset_root,
        output_dir=args.output_dir,
        tracking_database=args.tracking_database,
        run_name=args.run_name,
        weights=None if args.smoke or args.weights == "none" else "imagenet",
        epochs=1 if args.smoke else args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_per_class=4 if args.smoke else None,
    )
    report = run_mobilenet_experiment(config)
    print(f"MLflow run: {report['mlflow_run_id']}")
    print(f"Report: {args.output_dir / 'evaluation_report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
