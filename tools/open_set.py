"""Model-bound open-set recognition for rejecting unsupported images."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import numpy as np


OPEN_SET_SCHEMA_VERSION = 2


class OpenSetGateError(RuntimeError):
    """Raised when an open-set artifact is unavailable or incompatible."""


@dataclass(frozen=True)
class OpenSetDecision:
    accepted: bool
    nearest_label: str
    nearest_fruit: str
    similarity: float
    threshold: float


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class OpenSetGate:
    """Reject embeddings that are too far from every calibrated class centroid."""

    def __init__(
        self,
        artifact_path: str | Path,
        *,
        expected_model_path: str | Path | None = None,
        expected_labels: tuple[str, ...] | list[str] | None = None,
    ) -> None:
        self.artifact_path = Path(artifact_path)
        if not self.artifact_path.is_file():
            raise OpenSetGateError(
                "The calibrated supported-input gate is unavailable. Rebuild or reinstall FreshSense."
            )

        try:
            with np.load(self.artifact_path, allow_pickle=False) as artifact:
                schema_version = int(_scalar(artifact, "schema_version"))
                self.feature_layer = str(_scalar(artifact, "feature_layer"))
                self.model_sha256 = str(_scalar(artifact, "model_sha256"))
                self.catalog_sha256 = str(_scalar(artifact, "catalog_sha256"))
                self.manifest_sha256 = str(_scalar(artifact, "manifest_sha256"))
                self.calibration_source = str(_scalar(artifact, "calibration_source"))
                self.gate_labels = tuple(str(value) for value in artifact["gate_labels"].tolist())
                self.gate_fruits = tuple(str(value) for value in artifact["gate_fruits"].tolist())
                self.centroids = np.asarray(artifact["centroids"], dtype=np.float32)
                self.thresholds = np.asarray(artifact["thresholds"], dtype=np.float32)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise OpenSetGateError("The supported-input gate artifact is invalid.") from exc

        if schema_version != OPEN_SET_SCHEMA_VERSION:
            raise OpenSetGateError(
                f"Unsupported open-set artifact schema {schema_version}; expected {OPEN_SET_SCHEMA_VERSION}."
            )
        if not self.feature_layer:
            raise OpenSetGateError("The open-set artifact does not identify a feature layer.")
        if not self.gate_labels or len(set(self.gate_labels)) != len(self.gate_labels):
            raise OpenSetGateError("The open-set artifact has invalid prototype labels.")
        if len(self.gate_fruits) != len(self.gate_labels) or any(
            not value for value in self.gate_fruits
        ):
            raise OpenSetGateError("The open-set artifact has invalid prototype fruit mappings.")
        if self.centroids.ndim != 2 or self.centroids.shape[0] != len(self.gate_labels):
            raise OpenSetGateError("The open-set centroid matrix does not match its labels.")
        if self.thresholds.shape != (len(self.gate_labels),):
            raise OpenSetGateError("The open-set thresholds do not match their labels.")
        if not np.isfinite(self.centroids).all() or not np.isfinite(self.thresholds).all():
            raise OpenSetGateError("The open-set artifact contains non-finite values.")
        if np.any(self.thresholds < -1.0) or np.any(self.thresholds > 1.0):
            raise OpenSetGateError("Open-set cosine thresholds must be between -1 and 1.")

        self.centroids = _normalize_rows(self.centroids)
        if expected_labels is not None and tuple(expected_labels) != self.gate_labels:
            raise OpenSetGateError(
                "The open-set artifact prototype order does not match the fruit catalog."
            )
        if expected_model_path is not None:
            actual_model_hash = sha256_file(expected_model_path)
            if actual_model_hash != self.model_sha256:
                raise OpenSetGateError(
                    "The open-set artifact was calibrated for a different vision model."
                )

    @property
    def feature_size(self) -> int:
        return int(self.centroids.shape[1])

    def evaluate(self, feature_vector: np.ndarray) -> OpenSetDecision:
        feature = np.asarray(feature_vector, dtype=np.float32)
        if feature.shape != (self.feature_size,):
            raise OpenSetGateError(
                f"Expected a {self.feature_size}-value feature vector, received {feature.shape}."
            )
        norm = float(np.linalg.norm(feature))
        if not np.isfinite(norm) or norm == 0:
            raise OpenSetGateError("The vision model produced an invalid feature vector.")
        feature = feature / norm
        similarities = self.centroids @ feature
        nearest_index = int(np.argmax(similarities))
        similarity = float(similarities[nearest_index])
        threshold = float(self.thresholds[nearest_index])
        return OpenSetDecision(
            accepted=similarity >= threshold,
            nearest_label=self.gate_labels[nearest_index],
            nearest_fruit=self.gate_fruits[nearest_index],
            similarity=similarity,
            threshold=threshold,
        )


def validate_open_set_artifact(
    artifact_path: str | Path,
    *,
    model_path: str | Path,
    expected_labels: tuple[str, ...] | list[str],
) -> None:
    OpenSetGate(
        artifact_path,
        expected_model_path=model_path,
        expected_labels=expected_labels,
    )


def _scalar(artifact: np.lib.npyio.NpzFile, name: str) -> object:
    value = artifact[name]
    if value.size != 1:
        raise ValueError(f"Artifact field {name!r} must contain one value.")
    return value.reshape(-1)[0].item()


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise OpenSetGateError("Open-set centroids cannot contain zero-length vectors.")
    return matrix / norms
