"""Verify every file bound into the FreshSense model artifact manifest."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from utils.artifact_manifest import ArtifactManifestError, verify_artifact_manifest


def main() -> int:
    path = PROJECT_ROOT / "artifacts" / "model_manifest.json"
    payload = verify_artifact_manifest(path, project_root=PROJECT_ROOT)
    print(
        "Verified FreshSense model artifact manifest for version "
        f"{payload['application_version']}."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ArtifactManifestError as exc:
        raise SystemExit(f"Artifact verification failed: {exc}") from exc
