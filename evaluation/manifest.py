"""Dataset auditing and leakage-free, source-grouped benchmark manifests."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Iterable

from utils.fruit_catalog import FruitCatalog


MANIFEST_SCHEMA_VERSION = 1
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
AUGMENTATION_PREFIXES = (
    "rotated_by_15_",
    "rotated_by_30_",
    "rotated_by_45_",
    "rotated_by_60_",
    "rotated_by_75_",
    "saltandpepper_",
    "translation_",
    "vertical_flip_",
)


class EvaluationManifestError(ValueError):
    """Raised when a benchmark manifest or source dataset is invalid."""


def sha256_file(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_source_name(filename: str) -> str:
    lowered = filename.lower()
    for prefix in AUGMENTATION_PREFIXES:
        if lowered.startswith(prefix):
            return filename[len(prefix) :]
    return filename


def discover_dataset_root(path: str | Path, class_names: Iterable[str]) -> Path:
    """Choose the most complete train/test directory under a supplied dataset path."""
    base = Path(path).expanduser().resolve()
    candidates = [base, base / "dataset"]
    required = tuple(class_names)
    scored: list[tuple[int, Path]] = []
    for candidate in candidates:
        if all((candidate / split / label).is_dir() for split in ("train", "test") for label in required):
            count = sum(
                1
                for split in ("train", "test")
                for label in required
                for item in (candidate / split / label).iterdir()
                if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
            )
            scored.append((count, candidate))
    if not scored:
        raise EvaluationManifestError(
            f"No complete train/test dataset with the configured classes was found under {base}."
        )
    return max(scored, key=lambda item: (item[0], len(item[1].parts)))[1]


def build_grouped_manifest(
    dataset_path: str | Path,
    *,
    catalog: FruitCatalog,
    seed: str = "freshsense-0.3-group-split-v1",
    ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
    hash_images: bool = True,
) -> dict[str, object]:
    if len(ratios) != 3 or any(value <= 0 for value in ratios):
        raise EvaluationManifestError("Split ratios must contain three positive values.")
    total_ratio = sum(ratios)
    ratios = tuple(value / total_ratio for value in ratios)
    dataset_root = discover_dataset_root(dataset_path, catalog.class_names)

    records: list[dict[str, object]] = []
    groups_by_label: dict[str, set[str]] = defaultdict(set)
    source_split_groups: dict[str, set[str]] = defaultdict(set)
    for source_split in ("train", "test"):
        for label in catalog.class_names:
            class_definition = catalog.class_for_label(label)
            class_dir = dataset_root / source_split / label
            for image_path in sorted(class_dir.iterdir(), key=lambda value: value.name.lower()):
                if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
                    continue
                source_name = canonical_source_name(image_path.name)
                group_key = f"{label}:{source_name}"
                group_id = sha256(group_key.encode("utf-8")).hexdigest()[:20]
                groups_by_label[label].add(group_id)
                source_split_groups[source_split].add(group_id)
                record = {
                    "relative_path": image_path.relative_to(dataset_root).as_posix(),
                    "source_split": source_split,
                    "benchmark_split": None,
                    "label": label,
                    "fruit": class_definition.fruit_id,
                    "freshness": class_definition.freshness,
                    "supported": True,
                    "group_id": group_id,
                    "source_name": source_name,
                    "augmentation": _augmentation_name(image_path.name),
                    "bytes": image_path.stat().st_size,
                    "sha256": sha256_file(image_path) if hash_images else None,
                    "device": "unknown",
                    "lighting": "unknown",
                    "background": "unknown",
                    "collection": "legacy_kaggle",
                }
                records.append(record)

    assignments: dict[str, str] = {}
    split_names = ("train", "validation", "test")
    for label, group_ids in groups_by_label.items():
        ordered = sorted(
            group_ids,
            key=lambda group_id: sha256(f"{seed}:{label}:{group_id}".encode("utf-8")).digest(),
        )
        train_end = round(len(ordered) * ratios[0])
        validation_end = train_end + round(len(ordered) * ratios[1])
        for index, group_id in enumerate(ordered):
            if index < train_end:
                split = split_names[0]
            elif index < validation_end:
                split = split_names[1]
            else:
                split = split_names[2]
            assignments[group_id] = split

    for record in records:
        record["benchmark_split"] = assignments[str(record["group_id"])]

    overlap = source_split_groups["train"] & source_split_groups["test"]
    split_summary: dict[str, dict[str, int]] = {}
    for split in split_names:
        split_records = [record for record in records if record["benchmark_split"] == split]
        split_summary[split] = {
            "images": len(split_records),
            "source_groups": len({str(record["group_id"]) for record in split_records}),
        }

    manifest: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset_name": "fruits_fresh_and_rotten_grouped_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_root_name": dataset_root.name,
        "dataset_root_hint": "Set FRESHSENSE_BENCHMARK_ROOT to the canonical dataset directory.",
        "class_order": list(catalog.class_names),
        "grouping_rule": "label plus filename after stripping one known augmentation prefix",
        "split_seed": seed,
        "split_ratios": dict(zip(split_names, ratios)),
        "summary": {
            "images": len(records),
            "source_groups": len(assignments),
            "legacy_train_groups": len(source_split_groups["train"]),
            "legacy_test_groups": len(source_split_groups["test"]),
            "legacy_cross_split_group_overlap": len(overlap),
            "legacy_test_group_overlap_fraction": (
                len(overlap) / len(source_split_groups["test"])
                if source_split_groups["test"]
                else 0.0
            ),
            "legacy_split_is_independent": not overlap,
            "grouped_splits": split_summary,
        },
        "records": records,
    }
    _validate_manifest(manifest)
    return manifest


def write_manifest(manifest: dict[str, object], destination: str | Path) -> str:
    output = Path(destination)
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with output.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(serialized)
    return sha256_file(output)


def load_manifest(path: str | Path) -> dict[str, object]:
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationManifestError("The evaluation manifest is unavailable or invalid JSON.") from exc
    _validate_manifest(manifest)
    return manifest


def manifest_sha256(path: str | Path) -> str:
    return sha256_file(path)


def _augmentation_name(filename: str) -> str:
    lowered = filename.lower()
    for prefix in AUGMENTATION_PREFIXES:
        if lowered.startswith(prefix):
            return prefix.rstrip("_")
    return "original"


def _validate_manifest(manifest: object) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise EvaluationManifestError("Unsupported evaluation manifest schema.")
    records = manifest.get("records")
    if not isinstance(records, list) or not records:
        raise EvaluationManifestError("An evaluation manifest must contain records.")
    required = {
        "relative_path",
        "source_split",
        "benchmark_split",
        "label",
        "fruit",
        "freshness",
        "supported",
        "group_id",
    }
    for record in records:
        if not isinstance(record, dict) or not required.issubset(record):
            raise EvaluationManifestError("An evaluation record is missing required fields.")
        if record["benchmark_split"] not in {"train", "validation", "test"}:
            raise EvaluationManifestError("Evaluation records contain an invalid split.")

    groups_by_split: dict[str, set[str]] = defaultdict(set)
    for record in records:
        groups_by_split[str(record["benchmark_split"])].add(str(record["group_id"]))
    if (
        groups_by_split["train"] & groups_by_split["validation"]
        or groups_by_split["train"] & groups_by_split["test"]
        or groups_by_split["validation"] & groups_by_split["test"]
    ):
        raise EvaluationManifestError("Source groups cross benchmark split boundaries.")
