"""Initialize, record, summarize, and export a controlled FreshSense pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from pilot.store import PilotStore


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--store", type=Path, default=PROJECT_ROOT / "pilot" / "data" / "pilot.sqlite3"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    record = subparsers.add_parser("record")
    record.add_argument("--sample-id", required=True)
    record.add_argument("--reviewer", required=True)
    record.add_argument("--app-decision", required=True)
    record.add_argument("--predicted-freshness", choices=("fresh", "rotten"))
    record.add_argument(
        "--reviewed-outcome",
        required=True,
        choices=("fresh", "rotten", "unsupported", "uncertain"),
    )
    record.add_argument("--confidence", type=float)
    record.add_argument("--device", default="unknown")
    record.add_argument("--lighting", default="unknown")
    record.add_argument("--background", default="unknown")
    record.add_argument("--notes", default="")
    record.add_argument("--task-seconds", type=float)
    record.add_argument("--result-understood", action=argparse.BooleanOptionalAction)
    record.add_argument("--warning-helpful", action=argparse.BooleanOptionalAction)
    record.add_argument("--would-use-again", action=argparse.BooleanOptionalAction)
    record.add_argument("--usability-rating", type=int, choices=range(1, 6))
    subparsers.add_parser("summary")
    export = subparsers.add_parser("export")
    export.add_argument("--output", required=True, type=Path)
    migrate = subparsers.add_parser("migrate-jsonl")
    migrate.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()

    store = PilotStore(args.store)
    if args.command == "init":
        store.initialize()
        print(f"Pilot store initialized: {args.store}")
    elif args.command == "record":
        saved = store.add(
            sample_id=args.sample_id,
            reviewer=args.reviewer,
            app_decision=args.app_decision,
            predicted_freshness=args.predicted_freshness,
            reviewed_outcome=args.reviewed_outcome,
            confidence=args.confidence,
            device=args.device,
            lighting=args.lighting,
            background=args.background,
            notes=args.notes,
            task_seconds=args.task_seconds,
            result_understood=args.result_understood,
            warning_helpful=args.warning_helpful,
            would_use_again=args.would_use_again,
            usability_rating=args.usability_rating,
        )
        print(json.dumps(saved, indent=2))
    elif args.command == "summary":
        print(json.dumps(store.summary(), indent=2))
    elif args.command == "export":
        store.export_csv(args.output)
        print(f"Pilot CSV exported: {args.output}")
    else:
        imported = store.import_jsonl(args.source)
        print(f"Imported {imported} legacy records into: {args.store}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
