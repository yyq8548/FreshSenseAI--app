"""Low-learning-rate fine tuning for the expanded FreshSense DenseNet."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import numpy as np

from evaluation.manifest import load_manifest, sha256_file
from training.mobilenet import classification_metrics


_DENSE_BLOCK = re.compile(r"^conv5_block(\d+)_")


def fine_tune_expanded_model(
    *,
    manifest_path: str | Path,
    dataset_root: str | Path,
    input_model_path: str | Path,
    output_model_path: str | Path,
    report_path: str | Path,
    batch_size: int = 32,
    epochs: int = 15,
    learning_rate: float = 2e-5,
    first_trainable_block: int = 29,
    patience: int = 4,
    seed: int = 20260719,
) -> dict[str, object]:
    import tensorflow as tf

    tf.keras.utils.set_random_seed(seed)
    manifest = load_manifest(manifest_path)
    records = [dict(record) for record in manifest["records"]]
    class_names = tuple(str(value) for value in manifest["class_order"])
    root = Path(dataset_root)
    selected = {
        split: [record for record in records if record["benchmark_split"] == split]
        for split in ("train", "validation", "test")
    }
    model = tf.keras.models.load_model(input_model_path, compile=False)
    if int(model.output_shape[-1]) != len(class_names):
        raise ValueError("Candidate model output does not match the expanded manifest.")

    trainable_layers = []
    for layer in model.layers:
        layer.trainable = False
        match = _DENSE_BLOCK.match(layer.name)
        if (
            match
            and int(match.group(1)) >= first_trainable_block
            and not isinstance(layer, tf.keras.layers.BatchNormalization)
        ):
            layer.trainable = True
            trainable_layers.append(layer.name)
        if isinstance(layer, tf.keras.Model) and "densenet" in layer.name.lower():
            layer.trainable = True
            for nested_layer in layer.layers:
                nested_layer.trainable = False
                nested_match = _DENSE_BLOCK.match(nested_layer.name)
                if (
                    nested_match
                    and int(nested_match.group(1)) >= first_trainable_block
                    and not isinstance(nested_layer, tf.keras.layers.BatchNormalization)
                ):
                    nested_layer.trainable = True
                    trainable_layers.append(f"{layer.name}/{nested_layer.name}")
    model.layers[-1].trainable = True
    trainable_layers.append(model.layers[-1].name)

    augmentation = tf.keras.Sequential(
        [
            tf.keras.layers.RandomFlip("horizontal", seed=seed),
            tf.keras.layers.RandomRotation(0.04, fill_mode="reflect", seed=seed + 1),
            tf.keras.layers.RandomZoom(0.08, fill_mode="reflect", seed=seed + 2),
            tf.keras.layers.RandomContrast(0.10, seed=seed + 3),
        ],
        name="training_augmentation",
    )
    datasets = {
        split: _build_dataset(
            tf,
            split_records,
            root=root,
            class_names=class_names,
            batch_size=batch_size,
            training=split == "train",
            augmentation=augmentation,
            seed=seed,
        )
        for split, split_records in selected.items()
    }

    train_indices = [class_names.index(str(record["label"])) for record in selected["train"]]
    counts = Counter(train_indices)
    class_weight = {
        index: len(train_indices) / (len(class_names) * counts[index])
        for index in range(len(class_names))
    }
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=learning_rate, clipnorm=1.0),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(),
        metrics=["accuracy"],
    )
    callbacks = [
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=patience, restore_best_weights=True
        ),
        tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss", factor=0.35, patience=2, min_lr=5e-7
        ),
    ]
    history = model.fit(
        datasets["train"],
        validation_data=datasets["validation"],
        epochs=epochs,
        class_weight=class_weight,
        callbacks=callbacks,
        verbose=2,
    )

    probabilities = np.asarray(model.predict(datasets["test"], verbose=0), dtype=np.float32)
    truth = np.asarray(
        [class_names.index(str(record["label"])) for record in selected["test"]],
        dtype=np.int64,
    )
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

    output_model = Path(output_model_path)
    output_model.parent.mkdir(parents=True, exist_ok=True)
    model.save(output_model)
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "architecture": "DenseNet201 expanded head plus partial conv5 fine tuning",
        "input_model_sha256": sha256_file(input_model_path),
        "model_path": output_model.name,
        "model_sha256": sha256_file(output_model),
        "manifest_sha256": sha256_file(manifest_path),
        "class_order": list(class_names),
        "first_trainable_dense_block": first_trainable_block,
        "trainable_layers": trainable_layers,
        "batch_size": batch_size,
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


def _build_dataset(
    tf,
    records,
    *,
    root: Path,
    class_names: tuple[str, ...],
    batch_size: int,
    training: bool,
    augmentation,
    seed: int,
):
    paths = [str(root / str(record["relative_path"])) for record in records]
    labels = [class_names.index(str(record["label"])) for record in records]
    dataset = tf.data.Dataset.from_tensor_slices((paths, labels))
    if training:
        dataset = dataset.shuffle(min(len(paths), 8192), seed=seed, reshuffle_each_iteration=True)

    def decode(path, label):
        image = tf.io.decode_jpeg(tf.io.read_file(path), channels=3)
        image = tf.image.resize(image, (224, 224))
        return tf.cast(image, tf.float32) / 255.0, label

    dataset = dataset.map(decode, num_parallel_calls=tf.data.AUTOTUNE)
    dataset = dataset.batch(batch_size)
    if training:
        dataset = dataset.map(
            lambda images, batch_labels: (augmentation(images, training=True), batch_labels),
            num_parallel_calls=tf.data.AUTOTUNE,
        )
    return dataset.prefetch(tf.data.AUTOTUNE)
