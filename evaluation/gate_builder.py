"""Calibrate a model-bound class-centroid open-set artifact."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from evaluation.manifest import load_manifest, manifest_sha256, sha256_file
from evaluation.stress import synthetic_ood_cases
from utils.fruit_catalog import FruitCatalog


def build_open_set_gate(
    *,
    manifest_path: str | Path,
    dataset_root: str | Path,
    model_path: str | Path,
    catalog_path: str | Path,
    catalog: FruitCatalog,
    output_path: str | Path,
    summary_path: str | Path,
    feature_layer: str = "avg_pool",
    batch_size: int = 32,
    minimum_supported_coverage: float = 0.95,
    minimum_final_supported_coverage: float = 0.90,
    synthetic_ood_count: int = 192,
    synthetic_rejection_quantile: float = 0.99,
) -> dict[str, object]:
    if not 0.5 <= minimum_supported_coverage < 1.0:
        raise ValueError("minimum_supported_coverage must be between 0.5 and 1.0.")
    if not 0.5 <= minimum_final_supported_coverage <= minimum_supported_coverage:
        raise ValueError(
            "minimum_final_supported_coverage must be between 0.5 and "
            "minimum_supported_coverage."
        )
    manifest = load_manifest(manifest_path)
    records = manifest["records"]
    dataset_name = str(manifest.get("dataset_name", "unspecified_dataset"))
    dataset_root = Path(dataset_root)

    from tensorflow.keras import Model
    from tensorflow.keras.models import load_model

    model = load_model(model_path, compile=False)
    layer = model.get_layer(feature_layer)
    feature_model = Model(inputs=model.input, outputs=layer.output)

    training_records = [record for record in records if record["benchmark_split"] == "train"]
    validation_records = [
        record for record in records if record["benchmark_split"] == "validation"
    ]
    training_features, training_labels, train_seconds = _extract_features(
        feature_model, training_records, dataset_root, batch_size
    )
    validation_features, validation_labels, validation_seconds = _extract_features(
        feature_model, validation_records, dataset_root, batch_size
    )

    gate_labels = tuple(catalog.class_names)
    gate_fruits = tuple(catalog.class_for_label(label).fruit_id for label in gate_labels)
    normalized_training = _normalize_rows(training_features)
    normalized_validation = _normalize_rows(validation_features)
    centroids = []
    for label in gate_labels:
        selected = normalized_training[np.asarray(training_labels) == label]
        if not len(selected):
            raise RuntimeError(f"No training embeddings were available for {label}.")
        centroid = selected.mean(axis=0)
        centroid /= np.linalg.norm(centroid)
        centroids.append(centroid)
    centroid_matrix = np.asarray(centroids, dtype=np.float32)

    validation_similarities = normalized_validation @ centroid_matrix.T
    nearest_indices = np.argmax(validation_similarities, axis=1)
    nearest_scores = validation_similarities[np.arange(len(validation_similarities)), nearest_indices]

    base_thresholds = []
    supported_by_prototype: dict[str, dict[str, float | int]] = {}
    rejection_quantile = 1.0 - minimum_supported_coverage
    for class_index, label in enumerate(gate_labels):
        class_mask = np.asarray(validation_labels) == label
        own_scores = validation_similarities[class_mask, class_index]
        if not len(own_scores):
            raise RuntimeError(f"No validation embeddings were available for {label}.")
        threshold = float(np.quantile(own_scores, rejection_quantile))
        base_thresholds.append(threshold)
        supported_by_prototype[label] = {
            "validation_images": int(class_mask.sum()),
            "threshold": threshold,
            "own_centroid_coverage": float(np.mean(own_scores >= threshold)),
            "nearest_centroid_agreement": float(np.mean(nearest_indices[class_mask] == class_index)),
        }
    synthetic_calibration_seed = 20260716
    synthetic_images = list(
        synthetic_ood_cases(synthetic_ood_count, seed=synthetic_calibration_seed)
    )
    synthetic_features, synthetic_seconds = _extract_image_features(
        feature_model,
        [image for _, image in synthetic_images],
        batch_size,
    )
    normalized_synthetic = _normalize_rows(synthetic_features)
    synthetic_similarities = normalized_synthetic @ centroid_matrix.T
    synthetic_nearest = np.argmax(synthetic_similarities, axis=1)
    synthetic_scores = synthetic_similarities[
        np.arange(len(synthetic_similarities)), synthetic_nearest
    ]
    thresholds = []
    for class_index, label in enumerate(gate_labels):
        nearest_ood_scores = synthetic_scores[synthetic_nearest == class_index]
        ood_threshold = (
            float(np.quantile(nearest_ood_scores, synthetic_rejection_quantile))
            if len(nearest_ood_scores)
            else -1.0
        )
        class_mask = np.asarray(validation_labels) == label
        own_scores = validation_similarities[class_mask, class_index]
        coverage_cap = float(
            np.quantile(own_scores, 1.0 - minimum_final_supported_coverage)
        )
        threshold = min(
            max(base_thresholds[class_index], ood_threshold), coverage_cap
        )
        thresholds.append(threshold)
        supported_by_prototype[label]["supported_only_threshold"] = base_thresholds[
            class_index
        ]
        supported_by_prototype[label]["synthetic_ood_threshold"] = ood_threshold
        supported_by_prototype[label]["coverage_cap_threshold"] = coverage_cap
        supported_by_prototype[label]["threshold"] = threshold
        supported_by_prototype[label]["final_validation_coverage"] = float(
            np.mean(validation_similarities[class_mask, class_index] >= threshold)
        )
    threshold_array = np.asarray(thresholds, dtype=np.float32)
    synthetic_accepted = synthetic_scores >= threshold_array[synthetic_nearest]

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        output,
        schema_version=np.asarray([2], dtype=np.int32),
        feature_layer=np.asarray([feature_layer]),
        gate_labels=np.asarray(gate_labels),
        gate_fruits=np.asarray(gate_fruits),
        centroids=centroid_matrix,
        thresholds=threshold_array,
        model_sha256=np.asarray([sha256_file(model_path)]),
        catalog_sha256=np.asarray([sha256_file(catalog_path)]),
        manifest_sha256=np.asarray([manifest_sha256(manifest_path)]),
        calibration_source=np.asarray([f"{dataset_name}_grouped_validation"]),
        minimum_supported_coverage=np.asarray([minimum_supported_coverage], dtype=np.float32),
        minimum_final_supported_coverage=np.asarray(
            [minimum_final_supported_coverage], dtype=np.float32
        ),
        synthetic_ood_count=np.asarray([synthetic_ood_count], dtype=np.int32),
        synthetic_calibration_seed=np.asarray([synthetic_calibration_seed], dtype=np.int32),
        synthetic_rejection_quantile=np.asarray(
            [synthetic_rejection_quantile], dtype=np.float32
        ),
        created_at_utc=np.asarray([datetime.now(timezone.utc).isoformat()]),
    )

    summary: dict[str, object] = {
        "schema_version": 2,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "artifact": output.name,
        "artifact_sha256": sha256_file(output),
        "model_sha256": sha256_file(model_path),
        "manifest_sha256": manifest_sha256(manifest_path),
        "feature_layer": feature_layer,
        "feature_size": int(centroid_matrix.shape[1]),
        "minimum_supported_coverage": minimum_supported_coverage,
        "minimum_final_supported_coverage": minimum_final_supported_coverage,
        "synthetic_rejection_quantile": synthetic_rejection_quantile,
        "synthetic_calibration_seed": synthetic_calibration_seed,
        "validation_images": len(validation_records),
        "validation_nearest_centroid_agreement": float(
            np.mean(nearest_indices == np.asarray([gate_labels.index(label) for label in validation_labels]))
        ),
        "validation_gate_coverage": float(
            np.mean(nearest_scores >= threshold_array[nearest_indices])
        ),
        "synthetic_ood_images": len(synthetic_images),
        "synthetic_ood_false_acceptance_rate": float(np.mean(synthetic_accepted)),
        "prototype_calibration": supported_by_prototype,
        "feature_extraction_seconds": {
            "train": round(train_seconds, 3),
            "validation": round(validation_seconds, 3),
            "synthetic_ood": round(synthetic_seconds, 3),
        },
        "validity_warning": (
            f"This gate was calibrated on {dataset_name}, not an independently photographed "
            "real-world store benchmark. Recalibrate it after representative unsupported-image "
            "and store-pilot data are collected."
        ),
    }
    summary_output = Path(summary_path)
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _extract_features(feature_model, records, dataset_root: Path, batch_size: int):
    images: list[Image.Image] = []
    labels: list[str] = []
    features: list[np.ndarray] = []
    started = time.perf_counter()
    for record in records:
        path = dataset_root / str(record["relative_path"])
        with Image.open(path) as source:
            images.append(source.convert("RGB"))
        labels.append(str(record["label"]))
        if len(images) >= batch_size:
            batch_features, _ = _extract_image_features(feature_model, images, batch_size)
            features.append(batch_features)
            images = []
    if images:
        batch_features, _ = _extract_image_features(feature_model, images, batch_size)
        features.append(batch_features)
    return np.concatenate(features), labels, time.perf_counter() - started


def _extract_image_features(feature_model, images: list[Image.Image], batch_size: int):
    started = time.perf_counter()
    arrays = []
    for image in images:
        resized = image.convert("RGB").resize((224, 224))
        arrays.append(np.asarray(resized, dtype=np.float32) / 255.0)
        image.close()
    values = feature_model.predict(
        np.asarray(arrays, dtype=np.float32), batch_size=batch_size, verbose=0
    )
    return np.asarray(values, dtype=np.float32), time.perf_counter() - started


def _normalize_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise RuntimeError("Feature extraction produced a zero-length vector.")
    return values / norms
