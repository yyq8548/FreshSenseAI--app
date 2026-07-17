"""Batch evaluation of the exact FreshSense model, gate, and confidence policy."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from evaluation.manifest import load_manifest, manifest_sha256, sha256_file
from evaluation.metrics import compute_metrics, write_report_bundle
from evaluation.stress import synthetic_ood_cases
from tools.open_set import OpenSetGate
from utils.config import MIN_CONFIDENCE, MIN_PREDICTION_MARGIN
from utils.fruit_catalog import FruitCatalog


def run_evaluation(
    *,
    manifest_path: str | Path,
    dataset_root: str | Path,
    model_path: str | Path,
    gate_path: str | Path,
    catalog: FruitCatalog,
    output_dir: str | Path,
    split: str = "test",
    batch_size: int = 32,
    synthetic_ood_count: int = 192,
    max_supported_images: int | None = None,
) -> dict[str, object]:
    manifest = load_manifest(manifest_path)
    records = [
        record for record in manifest["records"] if record["benchmark_split"] == split
    ]
    if max_supported_images is not None:
        records = records[:max_supported_images]
    dataset_root = Path(dataset_root)

    from tensorflow.keras import Model
    from tensorflow.keras.models import load_model

    model = load_model(model_path, compile=False)
    gate = OpenSetGate(
        gate_path,
        expected_model_path=model_path,
        expected_labels=catalog.class_names,
    )
    feature_model = Model(inputs=model.input, outputs=model.get_layer(gate.feature_layer).output)
    results: list[dict[str, object]] = []

    for start in range(0, len(records), batch_size):
        batch_records = records[start : start + batch_size]
        images = []
        for record in batch_records:
            with Image.open(dataset_root / str(record["relative_path"])) as source:
                images.append(source.convert("RGB"))
        batch_results = _evaluate_images(
            images=images,
            feature_model=feature_model,
            classifier=model.layers[-1],
            gate=gate,
            catalog=catalog,
        )
        for record, result in zip(batch_records, batch_results):
            supported = bool(record["supported"])
            results.append(
                {
                    **result,
                    "sample_id": record.get("sha256") or record["group_id"],
                    "supported": supported,
                    "true_label": record["label"] if supported else None,
                    "device": record.get("device", "unknown"),
                    "lighting": record.get("lighting", "unknown"),
                    "background": record.get("background", "unknown"),
                    "collection": record.get("collection", "unknown"),
                }
            )

    synthetic_cases = list(synthetic_ood_cases(synthetic_ood_count, seed=20260717))
    for start in range(0, len(synthetic_cases), batch_size):
        batch_cases = synthetic_cases[start : start + batch_size]
        batch_results = _evaluate_images(
            images=[image for _, image in batch_cases],
            feature_model=feature_model,
            classifier=model.layers[-1],
            gate=gate,
            catalog=catalog,
        )
        for (name, _), result in zip(batch_cases, batch_results):
            results.append(
                {
                    **result,
                    "sample_id": name,
                    "supported": False,
                    "true_label": None,
                    "device": "synthetic",
                    "lighting": "synthetic",
                    "background": "synthetic",
                    "collection": "synthetic_ood_stress",
                }
            )

    freshness_by_label = {
        item.label: item.freshness for item in catalog.classes
    }
    metrics = compute_metrics(
        results,
        class_labels=catalog.class_names,
        freshness_by_label=freshness_by_label,
    )
    legacy_summary = manifest.get("summary", {})
    independent = bool(manifest.get("independent_real_world_benchmark")) and split == "test"
    report: dict[str, object] = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_sha256": sha256_file(model_path),
        "gate_sha256": sha256_file(gate_path),
        "manifest_sha256": manifest_sha256(manifest_path),
        "benchmark_split": split,
        "class_order": list(catalog.class_names),
        "policy": {
            "minimum_confidence": MIN_CONFIDENCE,
            "minimum_prediction_margin": MIN_PREDICTION_MARGIN,
            "open_set_gate_required": True,
            "synthetic_test_seed": 20260717,
        },
        "validity": {
            "independent_real_world_benchmark": independent,
            "legacy_train_test_source_overlap": legacy_summary.get(
                "legacy_cross_split_group_overlap"
            ),
            "warning": (
                None
                if independent
                else "The current model was trained before the leakage-free grouped manifest existed. "
                "These results validate software behavior, not independent real-world accuracy."
            ),
        },
        "metrics": metrics,
        "results": results,
    }
    write_report_bundle(report, output_dir)
    return report


def _evaluate_images(*, images, feature_model, classifier, gate, catalog):
    arrays = []
    for image in images:
        arrays.append(
            np.asarray(image.convert("RGB").resize((224, 224)), dtype=np.float32) / 255.0
        )
        image.close()
    batch = np.asarray(arrays, dtype=np.float32)
    started = time.perf_counter()
    features = np.asarray(feature_model.predict(batch, verbose=0), dtype=np.float32)
    probabilities = np.asarray(classifier(features, training=False), dtype=np.float32)
    elapsed_per_image = (time.perf_counter() - started) / max(1, len(images))
    outputs = []
    for feature, probs in zip(features, probabilities):
        decision = gate.evaluate(feature)
        predicted_index = int(np.argmax(probs))
        predicted_label = catalog.class_names[predicted_index]
        sorted_probs = np.sort(probs)[::-1]
        confidence = float(sorted_probs[0])
        margin = float(sorted_probs[0] - sorted_probs[1])
        gate_fruit = decision.nearest_fruit
        predicted_fruit = catalog.class_for_label(predicted_label).fruit_id
        gate_accepted = bool(decision.accepted and gate_fruit == predicted_fruit)
        if not gate_accepted:
            accepted = False
            final_decision = "unsupported_input"
        elif confidence < MIN_CONFIDENCE or margin < MIN_PREDICTION_MARGIN:
            accepted = False
            final_decision = "uncertain_input"
        else:
            accepted = True
            final_decision = "accept_prediction"
        outputs.append(
            {
                "accepted": accepted,
                "gate_accepted": gate_accepted,
                "decision": final_decision,
                "predicted_label": predicted_label if accepted else None,
                "tentative_label": predicted_label,
                "confidence": confidence,
                "prediction_margin": margin,
                "probabilities": [float(value) for value in probs],
                "open_set_nearest_label": decision.nearest_label,
                "open_set_nearest_fruit": decision.nearest_fruit,
                "open_set_similarity": decision.similarity,
                "open_set_threshold": decision.threshold,
                "latency_seconds": elapsed_per_image,
            }
        )
    return outputs
