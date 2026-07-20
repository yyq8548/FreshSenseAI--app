"""Run the versioned FreshSense Manager Chat evaluation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.manager_chat import run_manager_chat_evaluation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "manifests" / "manager_chat_v1.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "reports" / "manager_chat_v1",
    )
    parser.add_argument("--mode", choices=("fallback", "openai"), default="fallback")
    args = parser.parse_args()

    report = run_manager_chat_evaluation(
        manifest_path=args.manifest,
        output_dir=args.output,
        mode=args.mode,
    )
    print(json.dumps(report["metrics"], indent=2))
    print(f"Quality gate: {'PASS' if report['quality_gates']['passed'] else 'FAIL'}")
    print(f"Report bundle: {args.output}")
    return 0 if report["quality_gates"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
