"""Preview or apply a FreshSense SQLite-to-PostgreSQL metadata migration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from saas.migration import migrate_saas_database
from saas.store import SaaSStoreError


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Copy FreshSense workspace metadata into an empty database. "
            "The PostgreSQL URL is read from an environment variable so a "
            "password does not appear in shell history."
        )
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "runtime" / "freshsense_saas.db",
    )
    parser.add_argument(
        "--target-env",
        default="FRESHSENSE_SAAS_DATABASE_URL",
        help="Environment variable containing the target SQLAlchemy URL.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write rows after the default dry-run validation succeeds.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    target = os.getenv(args.target_env, "").strip()
    if not target:
        parser.error(f"{args.target_env} is not configured.")
    try:
        report = migrate_saas_database(args.source, target, apply=args.apply)
    except SaaSStoreError as exc:
        print(json.dumps({"status": "blocked", "detail": str(exc)}, indent=2))
        return 2

    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
