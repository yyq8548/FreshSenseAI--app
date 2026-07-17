"""Create a machine-readable FreshSense Azure readiness decision."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from deployment.azure.readiness import evaluate_azure_readiness


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evaluation-report",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "reports" / "real_world" / "evaluation_report.json",
    )
    parser.add_argument(
        "--pilot-database",
        type=Path,
        default=PROJECT_ROOT / "pilot" / "data" / "pilot.sqlite3",
    )
    parser.add_argument(
        "--test-evidence",
        type=Path,
        default=PROJECT_ROOT / "work" / "release_test_evidence.json",
    )
    parser.add_argument(
        "--approvals",
        type=Path,
        default=PROJECT_ROOT / "secrets" / "azure_approvals.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "work" / "azure_readiness.json",
    )
    args = parser.parse_args()
    report = evaluate_azure_readiness(
        evaluation_report_path=args.evaluation_report,
        pilot_database_path=args.pilot_database,
        test_evidence_path=args.test_evidence,
        approval_path=args.approvals,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"decision": report["decision"], "failed_checks": report["failed_checks"]}, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
