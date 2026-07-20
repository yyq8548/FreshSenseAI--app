from hashlib import sha256
import json
from zipfile import ZipFile, ZipInfo

import pytest

from deployment.azure.runtime_bundle import (
    RuntimeBundleError,
    _extract_safely,
    _validate_extracted_runtime,
)


def test_runtime_validation_requires_model_gate_and_manifest(tmp_path):
    root = tmp_path / "runtime"
    for relative in (
        "models/densenet201.h5",
        "models/open_set_gate.npz",
        "data/fruit_catalog.json",
        "data/food_knowledge_base.json",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test")
    embedding = root / "models" / "embedding_cache" / "model.onnx"
    embedding.parent.mkdir(parents=True, exist_ok=True)
    embedding.write_bytes(b"test")
    artifacts = {}
    for name, relative in (
        ("vision_model", "models/densenet201.h5"),
        ("open_set_gate", "models/open_set_gate.npz"),
        ("fruit_catalog", "data/fruit_catalog.json"),
        ("knowledge_base", "data/food_knowledge_base.json"),
    ):
        payload = (root / relative).read_bytes()
        artifacts[name] = {
            "path": relative,
            "bytes": len(payload),
            "sha256": sha256(payload).hexdigest(),
        }
    manifest = root / "artifacts" / "model_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps({"schema_version": 1, "artifacts": artifacts}),
        encoding="utf-8",
    )

    _validate_extracted_runtime(root)

    (root / "models/densenet201.h5").unlink()
    with pytest.raises(RuntimeBundleError, match="incomplete"):
        _validate_extracted_runtime(root)


def test_runtime_extraction_rejects_zip_path_traversal(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr("../outside.txt", "unsafe")

    with pytest.raises(RuntimeBundleError, match="unsafe path"):
        _extract_safely(archive, tmp_path / "output")
    assert not (tmp_path / "outside.txt").exists()


def test_runtime_extraction_rejects_windows_path_separators(tmp_path):
    archive = tmp_path / "windows-paths.zip"
    member = ZipInfo("placeholder")
    # Assign after construction because ZipInfo normalizes separators on
    # Windows. This creates the same malicious central-directory entry on
    # every test platform.
    member.filename = "models\\densenet201.h5"
    with ZipFile(archive, "w") as bundle:
        bundle.writestr(member, "unsafe-on-linux")

    with pytest.raises(RuntimeBundleError, match="non-POSIX path"):
        _extract_safely(archive, tmp_path / "output")
