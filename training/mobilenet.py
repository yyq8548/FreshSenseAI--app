"""Grouped MobileNetV2 training and MLflow experiment tracking."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any

import numpy as np

from evaluation.manifest import load_manifest, manifest_sha256, sha256_file


@dataclass(frozen=True)
class MobileNetTrainingConfig:
    manifest_path: Path
    dataset_root: Path
    output_dir: Path
    tracking_database: Path
    experiment_name: str = "FreshSense-MobileNetV2"
    run_name: str | None = None
    weights: str | None = "imagenet"
    epochs: int = 12
    batch_size: int = 32
    learning_rate: float = 0.001
    dropout: float = 0.25
    patience: int = 3
    seed: int = 20260717
    max_per_class: int | None = None
    deduplicate_sha: bool = True


def select_manifest_records(
    manifest: dict[str, object],
    split: str,
    *,
    deduplicate_sha: bool = True,
    max_per_class: int | None = None,
) -> list[dict[str, object]]:
    """Select a deterministic, optionally byte-deduplicated benchmark split."""
    if split not in {"train", "validation", "test"}:
        raise ValueError("Training split must be train, validation, or test.")
    selected = sorted(
        (
            dict(record)
            for record in manifest.get("records", [])
            if record.get("benchmark_split") == split and bool(record.get("supported"))
        ),
        key=lambda record: (str(record["label"]), str(record["relative_path"])),
    )
    if deduplicate_sha:
        seen: set[str] = set()
        deduplicated = []
        for record in selected:
            identity = str(record.get("sha256") or record["relative_path"])
            if identity in seen:
                continue
            seen.add(identity)
            deduplicated.append(record)
        selected = deduplicated

    if max_per_class is not None:
        if max_per_class <= 0:
            raise ValueError("max_per_class must be positive when provided.")
        counts: dict[str, int] = defaultdict(int)
        limited = []
        for record in selected:
            label = str(record["label"])
            if counts[label] >= max_per_class:
                continue
            limited.append(record)
            counts[label] += 1
        selected = limited
    if not selected:
        raise ValueError(f"No supported records were selected for {split}.")
    return selected


def classification_metrics(
    true_indices: np.ndarray,
    predicted_indices: np.ndarray,
    probabilities: np.ndarray,
    *,
    class_names: tuple[str, ...],
    freshness_by_label: dict[str, str],
) -> dict[str, object]:
    """Dependency-light multiclass metrics for a model-comparison report."""
    truth = np.asarray(true_indices, dtype=np.int64)
    predictions = np.asarray(predicted_indices, dtype=np.int64)
    probs = np.asarray(probabilities, dtype=np.float64)
    if truth.ndim != 1 or predictions.shape != truth.shape:
        raise ValueError("True and predicted labels must be matching vectors.")
    if probs.shape != (truth.size, len(class_names)):
        raise ValueError("Probability matrix does not match labels and classes.")

    confusion = np.zeros((len(class_names), len(class_names)), dtype=np.int64)
    for actual, predicted in zip(truth, predictions):
        confusion[int(actual), int(predicted)] += 1

    per_class: dict[str, dict[str, float | int]] = {}
    f1_values = []
    for index, label in enumerate(class_names):
        true_positive = int(confusion[index, index])
        false_positive = int(confusion[:, index].sum() - true_positive)
        false_negative = int(confusion[index, :].sum() - true_positive)
        support = int(confusion[index, :].sum())
        precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
        recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[label] = {
            "support": support,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    rotten_total = 0
    false_fresh = 0
    for actual, predicted in zip(truth, predictions):
        actual_label = class_names[int(actual)]
        predicted_label = class_names[int(predicted)]
        if freshness_by_label[actual_label] == "rotten":
            rotten_total += 1
            if freshness_by_label[predicted_label] == "fresh":
                false_fresh += 1

    confidence = probs.max(axis=1) if truth.size else np.asarray([], dtype=np.float64)
    return {
        "images": int(truth.size),
        "accuracy": float(np.mean(truth == predictions)) if truth.size else 0.0,
        "macro_f1": float(np.mean(f1_values)) if f1_values else 0.0,
        "mean_confidence": float(np.mean(confidence)) if confidence.size else 0.0,
        "rotten_images": rotten_total,
        "rotten_to_fresh_errors": false_fresh,
        "rotten_to_fresh_rate": false_fresh / rotten_total if rotten_total else 0.0,
        "per_class": per_class,
        "confusion_matrix": confusion.tolist(),
    }


def run_mobilenet_experiment(config: MobileNetTrainingConfig) -> dict[str, object]:
    """Train, evaluate, save, and track one MobileNetV2 comparison run."""
    try:
        import mlflow
        import tensorflow as tf
    except ImportError as exc:
        raise RuntimeError(
            "Install requirements-training.txt before running the MLflow experiment."
        ) from exc

    manifest = load_manifest(config.manifest_path)
    class_names = tuple(str(label) for label in manifest["class_order"])
    freshness_by_label = {
        str(record["label"]): str(record["freshness"])
        for record in manifest["records"]
    }
    records = {
        split: select_manifest_records(
            manifest,
            split,
            deduplicate_sha=config.deduplicate_sha,
            max_per_class=config.max_per_class,
        )
        for split in ("train", "validation", "test")
    }
    for split_records in records.values():
        for record in split_records:
            path = config.dataset_root / str(record["relative_path"])
            if not path.is_file():
                raise FileNotFoundError(f"Manifest image is unavailable: {path}")

    tf.keras.utils.set_random_seed(config.seed)
    datasets = {
        split: _build_dataset(
            tf,
            split_records,
            dataset_root=config.dataset_root,
            class_names=class_names,
            batch_size=config.batch_size,
            training=split == "train",
            seed=config.seed,
        )
        for split, split_records in records.items()
    }
    model = _build_model(
        tf,
        class_count=len(class_names),
        weights=config.weights,
        dropout=config.dropout,
        learning_rate=config.learning_rate,
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    model_path = config.output_dir / "mobilenetv2.keras"
    report_path = config.output_dir / "evaluation_report.json"
    comparison_path = config.output_dir / "comparison_summary.md"
    config.tracking_database.parent.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{config.tracking_database.resolve().as_posix()}")
    mlflow.set_experiment(config.experiment_name)

    with mlflow.start_run(run_name=config.run_name) as active_run:
        mlflow.log_params(
            {
                "architecture": "MobileNetV2",
                "weights": config.weights or "none",
                "epochs": config.epochs,
                "batch_size": config.batch_size,
                "learning_rate": config.learning_rate,
                "dropout": config.dropout,
                "patience": config.patience,
                "seed": config.seed,
                "manifest_sha256": manifest_sha256(config.manifest_path),
                "deduplicate_sha": config.deduplicate_sha,
                "max_per_class": config.max_per_class or "all",
                "train_images": len(records["train"]),
                "validation_images": len(records["validation"]),
                "test_images": len(records["test"]),
            }
        )
        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=config.patience,
                restore_best_weights=True,
            )
        ]
        history = model.fit(
            datasets["train"],
            validation_data=datasets["validation"],
            epochs=config.epochs,
            callbacks=callbacks,
            verbose=2,
        )
        for epoch, values in enumerate(zip(*history.history.values())):
            for name, value in zip(history.history, values):
                mlflow.log_metric(name, float(value), step=epoch)

        true_indices = np.asarray(
            [class_names.index(str(record["label"])) for record in records["test"]],
            dtype=np.int64,
        )
        started = time.perf_counter()
        probabilities = np.asarray(model.predict(datasets["test"], verbose=0))
        latency = (time.perf_counter() - started) / max(1, len(true_indices))
        predicted_indices = probabilities.argmax(axis=1)
        metrics = classification_metrics(
            true_indices,
            predicted_indices,
            probabilities,
            class_names=class_names,
            freshness_by_label=freshness_by_label,
        )
        metrics["mean_batch_inference_seconds_per_image"] = latency
        model.save(model_path)

        report: dict[str, object] = {
            "schema_version": 1,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "architecture": "MobileNetV2",
            "class_order": list(class_names),
            "manifest_sha256": manifest_sha256(config.manifest_path),
            "mlflow_run_id": active_run.info.run_id,
            "configuration": {
                **asdict(config),
                "manifest_path": "evaluation/manifests/legacy_grouped_v1.json",
                "dataset_root": "external-local-dataset",
                "output_dir": "generated-local-artifact",
                "tracking_database": "local-mlflow-sqlite",
            },
            "split_counts": {split: len(items) for split, items in records.items()},
            "validity": {
                "source_grouped_split": True,
                "independent_real_world_benchmark": False,
                "warning": (
                    "This experiment uses grouped legacy web images. It is suitable for "
                    "architecture comparison, not a real-world field-accuracy claim."
                ),
            },
            "metrics": metrics,
            "model_bytes": model_path.stat().st_size,
            "model_sha256": sha256_file(model_path),
        }
        report_path.write_text(
            json.dumps(report, indent=2, default=str, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        comparison_path.write_text(_comparison_markdown(report), encoding="utf-8")
        mlflow.log_metrics(
            {
                "test_accuracy": float(metrics["accuracy"]),
                "test_macro_f1": float(metrics["macro_f1"]),
                "test_rotten_to_fresh_rate": float(metrics["rotten_to_fresh_rate"]),
                "test_seconds_per_image": float(latency),
            }
        )
        mlflow.log_artifact(str(report_path), artifact_path="evaluation")
        mlflow.log_artifact(str(comparison_path), artifact_path="evaluation")
        mlflow.log_artifact(str(model_path), artifact_path="model")
        return report


def _build_dataset(
    tf: Any,
    records: list[dict[str, object]],
    *,
    dataset_root: Path,
    class_names: tuple[str, ...],
    batch_size: int,
    training: bool,
    seed: int,
) -> Any:
    paths = [str(dataset_root / str(record["relative_path"])) for record in records]
    labels = [class_names.index(str(record["label"])) for record in records]
    dataset = tf.data.Dataset.from_tensor_slices((paths, labels))
    if training:
        dataset = dataset.shuffle(len(paths), seed=seed, reshuffle_each_iteration=True)

    def load_image(path, label):
        content = tf.io.read_file(path)
        image = tf.io.decode_image(content, channels=3, expand_animations=False)
        image.set_shape((None, None, 3))
        image = tf.image.resize(image, (224, 224))
        return image, tf.one_hot(label, len(class_names))

    return (
        dataset.map(load_image, num_parallel_calls=tf.data.AUTOTUNE)
        .batch(batch_size)
        .prefetch(tf.data.AUTOTUNE)
    )


def _build_model(
    tf: Any,
    *,
    class_count: int,
    weights: str | None,
    dropout: float,
    learning_rate: float,
) -> Any:
    inputs = tf.keras.Input(shape=(224, 224, 3), name="image")
    normalized = tf.keras.applications.mobilenet_v2.preprocess_input(inputs)
    base = tf.keras.applications.MobileNetV2(
        include_top=False,
        weights=weights,
        input_shape=(224, 224, 3),
    )
    base.trainable = False
    features = base(normalized, training=False)
    pooled = tf.keras.layers.GlobalAveragePooling2D(name="avg_pool")(features)
    regularized = tf.keras.layers.Dropout(dropout, name="dropout")(pooled)
    outputs = tf.keras.layers.Dense(class_count, activation="softmax", name="predictions")(
        regularized
    )
    model = tf.keras.Model(inputs, outputs, name="freshsense_mobilenetv2")
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _comparison_markdown(report: dict[str, object]) -> str:
    metrics = report["metrics"]
    return (
        "# MobileNetV2 comparison result\n\n"
        f"- Accuracy: {float(metrics['accuracy']):.4f}\n"
        f"- Macro F1: {float(metrics['macro_f1']):.4f}\n"
        f"- Rotten-to-fresh rate: {float(metrics['rotten_to_fresh_rate']):.4f}\n"
        f"- Mean batch inference seconds/image: "
        f"{float(metrics['mean_batch_inference_seconds_per_image']):.6f}\n"
        f"- Model bytes: {int(report['model_bytes'])}\n\n"
        "This grouped legacy comparison is not an independent field-accuracy claim.\n"
    )
