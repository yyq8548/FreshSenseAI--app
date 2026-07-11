"""Validate Windows release assets and generate PyInstaller version metadata."""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.startup import StartupValidationError, validate_startup


VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
MIN_MODEL_BYTES = 1024 * 1024


class ReleaseValidationError(RuntimeError):
    """Raised when a required Windows release input is unavailable or invalid."""


def read_release_version(path: Path) -> str:
    try:
        version = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise ReleaseValidationError(f"Release version file is unavailable: {path}") from exc
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ReleaseValidationError("VERSION must contain three numeric components, such as 0.2.0.")
    if any(int(component) > 65535 for component in match.groups()):
        raise ReleaseValidationError("Each VERSION component must be 65535 or lower.")
    return version


def windows_version_tuple(version: str) -> tuple[int, int, int, int]:
    match = VERSION_PATTERN.fullmatch(version)
    if match is None:
        raise ReleaseValidationError("A numeric three-component version is required.")
    return tuple(int(component) for component in match.groups()) + (0,)


def validate_release_assets(
    *,
    version_path: Path,
    model_path: Path,
    embedding_cache: Path,
    catalog_path: Path,
    knowledge_base_path: Path,
) -> str:
    version = read_release_version(version_path)
    try:
        validate_startup(
            model_path=str(model_path),
            knowledge_base_path=str(knowledge_base_path),
            fruit_catalog_path=str(catalog_path),
        )
    except StartupValidationError as exc:
        raise ReleaseValidationError(str(exc)) from exc

    if model_path.stat().st_size < MIN_MODEL_BYTES:
        raise ReleaseValidationError(
            f"The trained vision model is unexpectedly small: {model_path}"
        )
    if not embedding_cache.is_dir():
        raise ReleaseValidationError(
            f"The local embedding cache is unavailable: {embedding_cache}"
        )
    onnx_files = [path for path in embedding_cache.rglob("*.onnx") if path.stat().st_size]
    tokenizers = [
        path for path in embedding_cache.rglob("tokenizer.json") if path.stat().st_size
    ]
    if not onnx_files:
        raise ReleaseValidationError("The embedding cache contains no non-empty ONNX model.")
    if not tokenizers:
        raise ReleaseValidationError("The embedding cache contains no non-empty tokenizer.json.")
    return version


def render_windows_version_info(version: str) -> str:
    file_version = windows_version_tuple(version)
    return f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={file_version!r},
    prodvers={file_version!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'FreshSense AI'),
          StringStruct('FileDescription', 'Private on-device fruit freshness guidance'),
          StringStruct('FileVersion', '{version}'),
          StringStruct('InternalName', 'FreshSenseAI'),
          StringStruct('LegalCopyright', 'Copyright 2026 Yeqiao Yu'),
          StringStruct('OriginalFilename', 'FreshSenseAI.exe'),
          StringStruct('ProductName', 'FreshSense AI'),
          StringStruct('ProductVersion', '{version}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
'''


def _default_paths() -> dict[str, Path]:
    return {
        "version_path": PROJECT_ROOT / "VERSION",
        "model_path": PROJECT_ROOT / "models" / "densenet201.h5",
        "embedding_cache": PROJECT_ROOT / "models" / "embedding_cache",
        "catalog_path": PROJECT_ROOT / "data" / "fruit_catalog.json",
        "knowledge_base_path": PROJECT_ROOT / "data" / "food_knowledge_base.json",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    version_parser = subparsers.add_parser("version-info")
    version_parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    paths = _default_paths()
    version = validate_release_assets(**paths)
    if args.command == "version-info":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(render_windows_version_info(version), encoding="utf-8")
        print(f"Windows version metadata written to: {args.output}")
    else:
        print(f"FreshSense {version} release assets are ready.")
        print(f"Vision model: {paths['model_path']}")
        print(f"Embedding cache: {paths['embedding_cache']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReleaseValidationError as exc:
        raise SystemExit(f"Release validation failed: {exc}") from exc
