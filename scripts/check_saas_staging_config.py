"""Validate Azure staging environment variables without printing secrets."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from deployment.azure.staging import validate_staging_configuration


def main() -> int:
    report = validate_staging_configuration(os.environ)
    print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
