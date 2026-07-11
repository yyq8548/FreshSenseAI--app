"""FreshSense application version shared by source and packaged builds."""

from __future__ import annotations

from pathlib import Path
import re
import sys


VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
PROJECT_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def read_app_version(path: Path | None = None) -> str:
    """Read a three-component release version, with a safe source fallback."""
    version_path = path or PROJECT_ROOT / "VERSION"
    try:
        value = version_path.read_text(encoding="utf-8").strip()
    except OSError:
        return "development"
    return value if VERSION_PATTERN.fullmatch(value) else "development"


APP_VERSION = read_app_version()
