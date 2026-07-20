"""Train a 12-class DenseNet201 head on an ImageNet visual backbone."""

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


def train_imagenet_densenet_head(
    *,
    manifest_path: str | Path,
    dataset_root: str | Path,
    output_model_path: str | Path,
    report_path: str | Path,
    cache_path: str | Path,
    batch_size: int = 64,
    epochs: int = 80,
    patience: int = 10,
    learning_rate: float = 0.001,
    seed: int = 20260719,
) -> dict[str, object]:
    import tensorflow as tf

    tf.keras.utils.set_random_seed(seed)
    manifest = load_manifest(manifest_path)
    records = [dict(record) for record in manifest["records"]]
    class_names = tuple(str(value) for value in manifest["class_order"])
    root = Path(dataset_root)

    backbone = tf.keras.applications.DenseNet201(
        include_top=False,
        weights="imagenet",
        input_shape=(224, 224, 3),
        pooling=None,
    )
    backbone.trainable = False
    runtime_input = tf.keras.Input(shape=(224, 224, 3), name="image")
    normalized = tf.keras.layers.Normalization(
        mean=(0.485, 0.456, 0.406),
        variance=(0.229**2, 0.224**2, 0.225**2),
        name="imagenet_preprocess",
    )(runtime_input)
    feature_map = backbone(normalized, training=False)
    feature_output = tf.keras.layers.GlobalAveragePooling2D(name="avg_pool")(feature_map)
    feature_model = tf.keras.Model(runtime_input, feature_output, name="imagenet_densenet_features")
    features, labels, splits, extraction_seconds = _load_or_extract_features(
        feature_model,
        records,
        root,
        Path(cache_path),
        class_names,
        batch_size,
        sha256_file(manifest_path),
    )
    masks = {split: splits == split for split in ("train", "validation", "test")}
    train_indices = labels[masks["train"]]
    counts = Counter(int(value) for value in train_indices)
    class_weight = {
        index: len(train_indices) / (len(class_names) * counts[index])
        for index in range(len(class_names))
    }

    head_input = tf.keras.Input(shape=(int(feature_model.output_shape[-1]),), name="cached_features")
    classifier = tf.keras.layers.Dense(
        len(class_names),
        activation="softmax",
        kernel_regularizer=tf.keras.regularizers.l2(1e-5),
        name="expanded_predictions",
    )
    head = tf.keras.Model(head_input, classifier(head_input), name="imagenet_densenet_head")
    head.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=["accuracy"],
    )
    history = head.fit(
        features[masks["train"]],
        labels[masks["train"]],
        validation_data=(features[masks["validation"]], labels[masks["validation"]]),
        epochs=epochs,
        batch_size=batch_size,
        class_weight=class_weight,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss", patience=patience, restore_best_weights=True
            ),
            tf.keras.callbacks.ReduceLROnPlateau(
                monitor="val_loss", factor=0.35, patience=4, min_lr=1e-6
            ),
        ],
        verbose=2,
    )
    probabilities = np.asarray(
        head.predict(features[masks["test"]], batch_size=batch_size, verbose=0),
        dtype=np.float32,
    )
    truth = labels[masks["test"]]
    freshness = {str(record["label"]): str(record["freshness"]) for record in records}
    metrics = classification_metrics(
        truth,
        probabilities.argmax(axis=1),
        probabilities,
        class_names=class_names,
        freshness_by_label=freshness,
    )

    model = tf.keras.Model(
        feature_model.input,
        classifier(feature_model.output),
        name="FreshSenseDenseNet201ImageNetExpanded",
    )
    output_model = Path(output_model_path)
    output_model.parent.mkdir(parents=True, exist_ok=True)
    model.save(output_model)
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "ImageNet DenseNet201 frozen backbone plus 12-class linear head",
        "model_path": output_model.name,
        "model_sha256": sha256_file(output_model),
        "manifest_sha256": sha256_file(manifest_path),
        "class_order": list(class_names),
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


def _load_or_extract_features(
    feature_model,
    records,
    root: Path,
    cache_path: Path,
    class_names: tuple[str, ...],
    batch_size: int,
    manifest_sha: str,
):
    if cache_path.is_file():
        with np.load(cache_path, allow_pickle=False) as cache:
            if str(cache["manifest_sha"].item()) == manifest_sha:
                return (
                    np.asarray(cache["features"], dtype=np.float32),
                    np.asarray(cache["labels"], dtype=np.int64),
                    np.asarray(cache["splits"]).astype(str),
                    float(cache["seconds"].item()),
                )

    started = time.perf_counter()
    feature_batches: list[np.ndarray] = []
    image_batch: list[np.ndarray] = []
    labels: list[int] = []
    splits: list[str] = []
    for record in records:
        with Image.open(root / str(record["relative_path"])) as image:
            image_batch.append(
                np.asarray(image.convert("RGB").resize((224, 224)), dtype=np.float32) / 255.0
            )
        labels.append(class_names.index(str(record["label"])))
        splits.append(str(record["benchmark_split"]))
        if len(image_batch) >= batch_size:
            feature_batches.append(
                np.asarray(feature_model.predict(np.asarray(image_batch, dtype=np.float32), verbose=0))
            )
            image_batch = []
    if image_batch:
        feature_batches.append(
            np.asarray(feature_model.predict(np.asarray(image_batch, dtype=np.float32), verbose=0))
        )
    features = np.concatenate(feature_batches).astype(np.float32)
    seconds = time.perf_counter() - started
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_path,
        features=features,
        labels=np.asarray(labels, dtype=np.int64),
        splits=np.asarray(splits),
        manifest_sha=np.asarray(manifest_sha),
        seconds=np.asarray(seconds),
    )
    return features, np.asarray(labels), np.asarray(splits), seconds
