"""Install a verified cloud runtime bundle without printing its signed URL."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from deployment.azure.runtime_bundle import RuntimeBundleError, prepare_runtime_bundle


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    args = parser.parse_args()
    url = os.getenv("FRESHSENSE_RUNTIME_BUNDLE_URL", "").strip()
    checksum = os.getenv("FRESHSENSE_RUNTIME_BUNDLE_SHA256", "").strip()
    if not url or not checksum:
        print(json.dumps({"status": "blocked", "detail": "Runtime bundle settings are missing."}))
        return 2
    try:
        report = prepare_runtime_bundle(
            url=url,
            expected_sha256=checksum,
            target=args.target,
        )
    except RuntimeBundleError as exc:
        print(json.dumps({"status": "blocked", "detail": str(exc)}))
        return 2
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
