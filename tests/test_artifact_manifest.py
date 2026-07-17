import json

import pytest

from evaluation.manifest import sha256_file
from utils.artifact_manifest import ArtifactManifestError, verify_artifact_manifest


def test_artifact_manifest_verifies_files_and_detects_tampering(tmp_path):
    artifact = tmp_path / "model.bin"
    artifact.write_bytes(b"original")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "application_version": "0.3.0",
                "artifacts": {
                    "vision_model": {
                        "path": "model.bin",
                        "bytes": artifact.stat().st_size,
                        "sha256": sha256_file(artifact),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    assert verify_artifact_manifest(manifest, project_root=tmp_path)[
        "application_version"
    ] == "0.3.0"

    artifact.write_bytes(b"changed!")
    with pytest.raises(ArtifactManifestError, match="checksum"):
        verify_artifact_manifest(manifest, project_root=tmp_path)
