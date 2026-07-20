"""Fine tune the expanded DenseNet candidate on WSL2 GPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from training.fine_tune_densenet import fine_tune_expanded_model


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--input-model", type=Path, default=PROJECT_ROOT / "models" / "densenet201-expanded.h5")
    parser.add_argument("--output-model", type=Path, default=PROJECT_ROOT / "models" / "densenet201-expanded-finetuned.h5")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "evaluation" / "reports" / "expanded_12_class" / "fine_tuned_evaluation_report.json")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--first-trainable-block", type=int, default=29)
    args = parser.parse_args()
    report = fine_tune_expanded_model(
        manifest_path=args.manifest,
        dataset_root=args.dataset,
        input_model_path=args.input_model,
        output_model_path=args.output_model,
        report_path=args.report,
        batch_size=args.batch_size,
        epochs=args.epochs,
        first_trainable_block=args.first_trainable_block,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
