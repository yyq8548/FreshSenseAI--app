"""Cryptographic association of FreshSense runtime and evaluation artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Mapping

import numpy as np

from evaluation.manifest import sha256_file


ARTIFACT_MANIFEST_SCHEMA_VERSION = 1


class ArtifactManifestError(RuntimeError):
    """Raised when runtime/evaluation artifacts are missing, altered, or unrelated."""


def build_artifact_manifest(
    *,
    project_root: str | Path,
    application_version: str,
    artifacts: Mapping[str, str | Path],
    class_order: tuple[str, ...] | list[str],
    fruit_order: tuple[str, ...] | list[str],
) -> dict[str, object]:
    root = Path(project_root).resolve()
    resolved: dict[str, Path] = {}
    entries: dict[str, dict[str, object]] = {}
    for name, supplied_path in artifacts.items():
        path = Path(supplied_path).resolve()
        if not path.is_file() or path.stat().st_size == 0:
            raise ArtifactManifestError(f"Required artifact is unavailable: {path}")
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise ArtifactManifestError(
                f"Artifact {name!r} must be located under the project root."
            ) from exc
        resolved[name] = path
        entries[name] = {
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }

    required = {
        "vision_model",
        "open_set_gate",
        "fruit_catalog",
        "knowledge_base",
        "evaluation_manifest",
        "evaluation_report",
        "gate_calibration_report",
    }
    missing = required - set(resolved)
    if missing:
        raise ArtifactManifestError(
            "Artifact mapping is incomplete: " + ", ".join(sorted(missing))
        )

    try:
        report = json.loads(resolved["evaluation_report"].read_text(encoding="utf-8"))
        with np.load(resolved["open_set_gate"], allow_pickle=False) as gate:
            gate_model_hash = str(gate["model_sha256"].reshape(-1)[0])
            gate_manifest_hash = str(gate["manifest_sha256"].reshape(-1)[0])
            gate_catalog_hash = str(gate["catalog_sha256"].reshape(-1)[0])
            gate_schema = int(gate["schema_version"].reshape(-1)[0])
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ArtifactManifestError(
            "The gate or evaluation report cannot be inspected."
        ) from exc

    model_hash = str(entries["vision_model"]["sha256"])
    manifest_hash = str(entries["evaluation_manifest"]["sha256"])
    gate_hash = str(entries["open_set_gate"]["sha256"])
    catalog_hash = str(entries["fruit_catalog"]["sha256"])
    expected = {
        "gate.model_sha256": (gate_model_hash, model_hash),
        "gate.manifest_sha256": (gate_manifest_hash, manifest_hash),
        "gate.catalog_sha256": (gate_catalog_hash, catalog_hash),
        "report.model_sha256": (report.get("model_sha256"), model_hash),
        "report.gate_sha256": (report.get("gate_sha256"), gate_hash),
        "report.manifest_sha256": (report.get("manifest_sha256"), manifest_hash),
    }
    mismatches = [name for name, values in expected.items() if values[0] != values[1]]
    if mismatches:
        raise ArtifactManifestError(
            "Runtime and evaluation artifacts are not cryptographically associated: "
            + ", ".join(mismatches)
        )

    return {
        "schema_version": ARTIFACT_MANIFEST_SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "application_version": application_version,
        "class_order": list(class_order),
        "fruit_order": list(fruit_order),
        "artifacts": entries,
        "associations": {
            "model_sha256": model_hash,
            "gate_sha256": gate_hash,
            "evaluation_manifest_sha256": manifest_hash,
            "evaluation_report_sha256": entries["evaluation_report"]["sha256"],
            "gate_schema_version": gate_schema,
        },
        "evaluation_validity": report.get("validity", {}),
        "evaluation_summary": report.get("metrics", {}).get("summary", {}),
    }


def write_artifact_manifest(payload: dict[str, object], destination: str | Path) -> str:
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(serialized)
    return sha256_file(output)


def verify_artifact_manifest(
    manifest_path: str | Path, *, project_root: str | Path
) -> dict[str, object]:
    path = Path(manifest_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactManifestError("The model artifact manifest is unavailable or invalid.") from exc
    if payload.get("schema_version") != ARTIFACT_MANIFEST_SCHEMA_VERSION:
        raise ArtifactManifestError("Unsupported model artifact manifest schema.")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ArtifactManifestError("The model artifact manifest contains no artifacts.")

    root = Path(project_root).resolve()
    for name, entry in artifacts.items():
        if not isinstance(entry, dict):
            raise ArtifactManifestError(f"Artifact entry {name!r} is invalid.")
        relative = Path(str(entry.get("path", "")))
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ArtifactManifestError(f"Artifact {name!r} escapes the project root.") from exc
        if not candidate.is_file():
            raise ArtifactManifestError(f"Artifact {name!r} is unavailable: {candidate}")
        if candidate.stat().st_size != int(entry.get("bytes", -1)):
            raise ArtifactManifestError(f"Artifact {name!r} size does not match its manifest.")
        if sha256_file(candidate) != entry.get("sha256"):
            raise ArtifactManifestError(f"Artifact {name!r} checksum does not match its manifest.")
    return payload
