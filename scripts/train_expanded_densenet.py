"""Train and evaluate the expanded 12-class FreshSense model."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from training.expanded_densenet import train_expanded_head


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--source-model", type=Path, default=PROJECT_ROOT / "models" / "densenet201.h5")
    parser.add_argument("--output-model", type=Path, default=PROJECT_ROOT / "models" / "densenet201-expanded.h5")
    parser.add_argument("--report", type=Path, default=PROJECT_ROOT / "evaluation" / "reports" / "expanded_12_class" / "evaluation_report.json")
    parser.add_argument("--cache", type=Path, default=PROJECT_ROOT / "models" / "embedding_cache" / "expanded_12_class.npz")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=60)
    args = parser.parse_args()
    report = train_expanded_head(
        manifest_path=args.manifest,
        dataset_root=args.dataset,
        source_model_path=args.source_model,
        output_model_path=args.output_model,
        report_path=args.report,
        cache_path=args.cache,
        batch_size=args.batch_size,
        epochs=args.epochs,
    )
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
