"""Expand the existing six-class DenseNet classifier to twelve classes."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image

from evaluation.manifest import load_manifest, sha256_file
from training.mobilenet import classification_metrics


LEGACY_CLASS_ORDER = (
    "freshapples",
    "freshbanana",
    "freshoranges",
    "rottenapples",
    "rottenbanana",
    "rottenoranges",
)


def train_expanded_head(
    *,
    manifest_path: str | Path,
    dataset_root: str | Path,
    source_model_path: str | Path,
    output_model_path: str | Path,
    report_path: str | Path,
    cache_path: str | Path,
    batch_size: int = 32,
    epochs: int = 60,
    patience: int = 8,
    learning_rate: float = 0.001,
    seed: int = 20260719,
) -> dict[str, object]:
    import tensorflow as tf

    tf.keras.utils.set_random_seed(seed)
    manifest = load_manifest(manifest_path)
    records = [dict(record) for record in manifest["records"]]
    class_names = tuple(str(value) for value in manifest["class_order"])
    root = Path(dataset_root)
    source_model = tf.keras.models.load_model(source_model_path, compile=False)
    feature_layer = source_model.get_layer("avg_pool")
    feature_model = tf.keras.Model(source_model.input, feature_layer.output)

    features, labels, splits, extraction_seconds = _load_or_extract_features(
        tf,
        feature_model,
        records,
        root,
        Path(cache_path),
        class_names,
        batch_size,
        source_model_path,
        manifest_path,
    )
    split_masks = {split: splits == split for split in ("train", "validation", "test")}
    train_indices = labels[split_masks["train"]]
    class_counts = Counter(int(value) for value in train_indices)
    class_weight = {
        index: len(train_indices) / (len(class_names) * class_counts[index])
        for index in range(len(class_names))
    }

    head_input = tf.keras.Input(shape=(int(feature_layer.output.shape[-1]),), name="cached_features")
    classifier = tf.keras.layers.Dense(
        len(class_names),
        activation="softmax",
        kernel_regularizer=tf.keras.regularizers.l2(1e-5),
        name="expanded_predictions",
    )
    head = tf.keras.Model(head_input, classifier(head_input), name="expanded_head")
    _initialize_from_legacy_head(source_model.layers[-1], classifier, class_names)
    head.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=["accuracy"],
    )
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=patience, restore_best_weights=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.35, patience=max(2, patience // 2), min_lr=1e-6
        ),
    ]
    history = head.fit(
        features[split_masks["train"]],
        labels[split_masks["train"]],
        validation_data=(features[split_masks["validation"]], labels[split_masks["validation"]]),
        epochs=epochs,
        batch_size=batch_size,
        class_weight=class_weight,
        callbacks=callbacks,
        verbose=2,
    )

    probabilities = np.asarray(
        head.predict(features[split_masks["test"]], batch_size=batch_size, verbose=0),
        dtype=np.float32,
    )
    truth = labels[split_masks["test"]]
    freshness = {
        str(record["label"]): str(record["freshness"]) for record in records
    }
    metrics = classification_metrics(
        truth,
        probabilities.argmax(axis=1),
        probabilities,
        class_names=class_names,
        freshness_by_label=freshness,
    )

    expanded_output = classifier(feature_layer.output)
    expanded_model = tf.keras.Model(source_model.input, expanded_output, name="FreshSenseDenseNet201Expanded")
    output_model = Path(output_model_path)
    output_model.parent.mkdir(parents=True, exist_ok=True)
    expanded_model.save(output_model)
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "DenseNet201 frozen feature extractor plus retrained linear head",
        "source_model_sha256": sha256_file(source_model_path),
        "model_path": output_model.name,
        "model_sha256": sha256_file(output_model),
        "manifest_sha256": sha256_file(manifest_path),
        "class_order": list(class_names),
        "split_images": {
            split: int(split_masks[split].sum()) for split in split_masks
        },
        "feature_extraction_seconds": extraction_seconds,
        "epochs_completed": len(history.history["loss"]),
        "best_validation_accuracy": float(max(history.history["val_accuracy"])),
        "test_metrics": metrics,
        "validity_warning": (
            "Metrics use curated/source-export data, not an independently photographed "
            "store benchmark. The model must abstain on unsupported inputs and remain advisory."
        ),
    }
    report_output = Path(report_path)
    report_output.parent.mkdir(parents=True, exist_ok=True)
    report_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _initialize_from_legacy_head(old_layer, new_layer, class_names: tuple[str, ...]) -> None:
    old_kernel, old_bias = old_layer.get_weights()
    new_kernel, new_bias = new_layer.get_weights()
    for old_index, label in enumerate(LEGACY_CLASS_ORDER):
        if label in class_names:
            new_index = class_names.index(label)
            new_kernel[:, new_index] = old_kernel[:, old_index]
            new_bias[new_index] = old_bias[old_index]
    new_layer.set_weights((new_kernel, new_bias))


def _load_or_extract_features(
    tf,
    feature_model,
    records,
    root: Path,
    cache_path: Path,
    class_names: tuple[str, ...],
    batch_size: int,
    source_model_path,
    manifest_path,
):
    model_sha = sha256_file(source_model_path)
    manifest_sha = sha256_file(manifest_path)
    if cache_path.is_file():
        with np.load(cache_path, allow_pickle=False) as cache:
            if str(cache["model_sha"].item()) == model_sha and str(cache["manifest_sha"].item()) == manifest_sha:
                return (
                    np.asarray(cache["features"], dtype=np.float32),
                    np.asarray(cache["labels"], dtype=np.int64),
                    np.asarray(cache["splits"]).astype(str),
                    float(cache["seconds"].item()),
                )

    started = time.perf_counter()
    features: list[np.ndarray] = []
    batch: list[np.ndarray] = []
    labels: list[int] = []
    splits: list[str] = []
    for record in records:
        path = root / str(record["relative_path"])
        with Image.open(path) as image:
            batch.append(
                np.asarray(image.convert("RGB").resize((224, 224)), dtype=np.float32) / 255.0
            )
        labels.append(class_names.index(str(record["label"])))
        splits.append(str(record["benchmark_split"]))
        if len(batch) >= batch_size:
            features.append(np.asarray(feature_model.predict(np.asarray(batch), verbose=0)))
            batch = []
    if batch:
        features.append(np.asarray(feature_model.predict(np.asarray(batch), verbose=0)))
    values = np.concatenate(features).astype(np.float32)
    seconds = time.perf_counter() - started
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        features=values,
        labels=np.asarray(labels, dtype=np.int64),
        splits=np.asarray(splits),
        model_sha=np.asarray(model_sha),
        manifest_sha=np.asarray(manifest_sha),
        seconds=np.asarray(seconds),
    )
    return values, np.asarray(labels), np.asarray(splits), seconds
