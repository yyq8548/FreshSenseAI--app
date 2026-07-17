"""Build a versioned manifest from reviewed real-world annotations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.manifest import write_manifest
from evaluation.real_world import build_real_world_manifest
from utils.config import FRUIT_CATALOG_PATH
from utils.fruit_catalog import load_fruit_catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--images", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "manifests" / "real_world_v1.json",
    )
    parser.add_argument("--skip-image-hashes", action="store_true")
    args = parser.parse_args()

    catalog = load_fruit_catalog(FRUIT_CATALOG_PATH)
    manifest = build_real_world_manifest(
        args.annotations,
        args.images,
        catalog=catalog,
        hash_images=not args.skip_image_hashes,
    )
    digest = write_manifest(manifest, args.output)
    print(json.dumps(manifest["summary"], indent=2))
    print(f"Manifest: {args.output}")
    print(f"Manifest SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
