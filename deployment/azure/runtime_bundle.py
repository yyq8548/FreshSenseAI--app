"""Checksum-first preparation of immutable FreshSense cloud model artifacts."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from utils.artifact_manifest import ArtifactManifestError, verify_artifact_manifest


MAX_RUNTIME_BUNDLE_BYTES = 1024 * 1024 * 1024
REQUIRED_RUNTIME_FILES = (
    "models/densenet201.h5",
    "models/open_set_gate.npz",
    "artifacts/model_manifest.json",
    "data/fruit_catalog.json",
    "data/food_knowledge_base.json",
)


class RuntimeBundleError(RuntimeError):
    """Raised when a runtime bundle is unavailable, unsafe, or unverified."""


def prepare_runtime_bundle(
    *,
    url: str,
    expected_sha256: str,
    target: str | Path,
) -> dict[str, object]:
    expected = _validate_sha256(expected_sha256)
    if not url.strip().lower().startswith("https://"):
        raise RuntimeBundleError("The runtime bundle URL must use HTTPS.")
    target_path = Path(target).expanduser().resolve()
    marker = target_path / ".bundle.sha256"
    if marker.is_file() and marker.read_text(encoding="ascii").strip() == expected:
        _validate_extracted_runtime(target_path)
        return {"status": "reused", "sha256": expected, "target": str(target_path)}

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="freshsense-download-", dir=target_path.parent
    ) as temp_dir:
        archive = Path(temp_dir) / "runtime-bundle.zip"
        actual = _download_and_hash(url, archive)
        if actual != expected:
            raise RuntimeBundleError("The runtime bundle checksum does not match.")
        staging = target_path.with_name(f"{target_path.name}.staging-{uuid4().hex}")
        try:
            _extract_safely(archive, staging)
            _validate_extracted_runtime(staging)
            (staging / ".bundle.sha256").write_text(expected + "\n", encoding="ascii")
            if target_path.exists():
                shutil.rmtree(target_path)
            staging.replace(target_path)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return {"status": "installed", "sha256": expected, "target": str(target_path)}


def _download_and_hash(url: str, destination: Path) -> str:
    request = Request(url, headers={"User-Agent": "FreshSense-runtime-preparer/1"})
    digest = sha256()
    written = 0
    try:
        with urlopen(request, timeout=120) as response, destination.open("wb") as output:
            if urlsplit(response.geturl()).scheme.lower() != "https":
                raise RuntimeBundleError("The runtime bundle redirect must preserve HTTPS.")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_RUNTIME_BUNDLE_BYTES:
                raise RuntimeBundleError("The runtime bundle is larger than allowed.")
            while chunk := response.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_RUNTIME_BUNDLE_BYTES:
                    raise RuntimeBundleError("The runtime bundle is larger than allowed.")
                digest.update(chunk)
                output.write(chunk)
    except RuntimeBundleError:
        raise
    except (OSError, ValueError) as exc:
        raise RuntimeBundleError("The runtime bundle could not be downloaded.") from exc
    return digest.hexdigest()


def _extract_safely(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    try:
        with ZipFile(archive) as bundle:
            root = destination.resolve()
            expanded_bytes = 0
            for member in bundle.infolist():
                # ZipInfo normalizes backslashes to forward slashes on Windows.
                # Validate the original central-directory name so an archive has
                # the same safety result on every deployment platform.
                if "\\" in member.orig_filename:
                    raise RuntimeBundleError(
                        "The runtime bundle contains a non-POSIX path."
                    )
                candidate = (root / member.filename).resolve()
                if candidate != root and root not in candidate.parents:
                    raise RuntimeBundleError("The runtime bundle contains an unsafe path.")
                if member.file_size > MAX_RUNTIME_BUNDLE_BYTES:
                    raise RuntimeBundleError("A runtime artifact is larger than allowed.")
                expanded_bytes += member.file_size
                if expanded_bytes > MAX_RUNTIME_BUNDLE_BYTES:
                    raise RuntimeBundleError("The expanded runtime bundle is larger than allowed.")
            bundle.extractall(root)
    except BadZipFile as exc:
        raise RuntimeBundleError("The runtime bundle is not a valid ZIP archive.") from exc


def _validate_extracted_runtime(root: Path) -> None:
    missing = [relative for relative in REQUIRED_RUNTIME_FILES if not (root / relative).is_file()]
    embedding_root = root / "models" / "embedding_cache"
    if not embedding_root.is_dir() or not any(embedding_root.rglob("*.onnx")):
        missing.append("models/embedding_cache/**/*.onnx")
    if missing:
        raise RuntimeBundleError(
            "The runtime bundle is incomplete: " + ", ".join(missing)
        )
    try:
        verify_artifact_manifest(
            root / "artifacts" / "model_manifest.json",
            project_root=root,
        )
    except ArtifactManifestError as exc:
        raise RuntimeBundleError(
            "The runtime artifact manifest could not be verified."
        ) from exc


def _validate_sha256(value: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", normalized):
        raise RuntimeBundleError("A lowercase 64-character SHA-256 is required.")
    return normalized


__all__ = ["RuntimeBundleError", "prepare_runtime_bundle"]
