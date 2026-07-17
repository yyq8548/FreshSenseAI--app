"""Build a reviewed, independently collected real-world benchmark manifest."""

from __future__ import annotations

from collections import defaultdict
import csv
from datetime import datetime, timezone
from pathlib import Path

from evaluation.manifest import (
    EvaluationManifestError,
    IMAGE_EXTENSIONS,
    MANIFEST_SCHEMA_VERSION,
    sha256_file,
)
from utils.fruit_catalog import FruitCatalog


REQUIRED_COLUMNS = (
    "sample_id",
    "relative_path",
    "benchmark_split",
    "supported",
    "label",
    "source_group",
    "device",
    "lighting",
    "background",
    "collection",
    "reviewer",
    "notes",
)


def build_real_world_manifest(
    annotations_path: str | Path,
    image_root: str | Path,
    *,
    catalog: FruitCatalog,
    hash_images: bool = True,
) -> dict[str, object]:
    root = Path(image_root).expanduser().resolve()
    if not root.is_dir():
        raise EvaluationManifestError(f"Real-world image root is unavailable: {root}")

    with Path(annotations_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames or ())
        if missing:
            raise EvaluationManifestError(
                "Real-world annotations are missing columns: " + ", ".join(sorted(missing))
            )
        rows = list(reader)
    if not rows:
        raise EvaluationManifestError("Real-world annotations contain no samples.")

    records: list[dict[str, object]] = []
    sample_ids: set[str] = set()
    group_splits: dict[str, set[str]] = defaultdict(set)
    for row_number, row in enumerate(rows, start=2):
        sample_id = row["sample_id"].strip()
        relative_path = row["relative_path"].strip().replace("\\", "/")
        split = row["benchmark_split"].strip().lower()
        source_group = row["source_group"].strip()
        if not sample_id or sample_id in sample_ids:
            raise EvaluationManifestError(
                f"Row {row_number} has a missing or duplicate sample_id."
            )
        if split not in {"validation", "test"}:
            raise EvaluationManifestError(
                f"Row {row_number} must use validation or test as benchmark_split."
            )
        if not source_group:
            raise EvaluationManifestError(f"Row {row_number} is missing source_group.")
        supported = _parse_boolean(row["supported"], row_number)
        label = row["label"].strip()
        if supported:
            if label not in catalog.class_names:
                raise EvaluationManifestError(
                    f"Row {row_number} has unsupported class label {label!r}."
                )
            class_definition = catalog.class_for_label(label)
            fruit = class_definition.fruit_id
            freshness = class_definition.freshness
        else:
            if label:
                raise EvaluationManifestError(
                    f"Row {row_number} is unsupported and must leave label blank."
                )
            fruit = None
            freshness = None

        image_path = (root / relative_path).resolve()
        try:
            image_path.relative_to(root)
        except ValueError as exc:
            raise EvaluationManifestError(
                f"Row {row_number} points outside the image root."
            ) from exc
        if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_EXTENSIONS:
            raise EvaluationManifestError(
                f"Row {row_number} image is missing or unsupported: {relative_path}"
            )

        sample_ids.add(sample_id)
        group_splits[source_group].add(split)
        records.append(
            {
                "relative_path": relative_path,
                "source_split": "independent_collection",
                "benchmark_split": split,
                "label": label or None,
                "fruit": fruit,
                "freshness": freshness,
                "supported": supported,
                "group_id": source_group,
                "sample_id": sample_id,
                "bytes": image_path.stat().st_size,
                "sha256": sha256_file(image_path) if hash_images else None,
                "device": row["device"].strip() or "unknown",
                "lighting": row["lighting"].strip() or "unknown",
                "background": row["background"].strip() or "unknown",
                "collection": row["collection"].strip() or "real_world",
                "reviewer": row["reviewer"].strip(),
                "notes": row["notes"].strip(),
            }
        )

    crossing = sorted(group for group, splits in group_splits.items() if len(splits) > 1)
    if crossing:
        raise EvaluationManifestError(
            "Physical source groups cross validation/test boundaries: "
            + ", ".join(crossing[:5])
        )

    summary = {}
    for split in ("validation", "test"):
        selected = [record for record in records if record["benchmark_split"] == split]
        summary[split] = {
            "images": len(selected),
            "supported": sum(bool(record["supported"]) for record in selected),
            "unsupported": sum(not bool(record["supported"]) for record in selected),
            "source_groups": len({record["group_id"] for record in selected}),
        }
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "dataset_name": "freshsense_real_world_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_root_name": root.name,
        "dataset_root_hint": "Set FRESHSENSE_BENCHMARK_ROOT to the reviewed image directory.",
        "class_order": list(catalog.class_names),
        "grouping_rule": "one physical fruit, scene, or capture burst per source_group",
        "independent_real_world_benchmark": True,
        "summary": {"real_world_splits": summary},
        "records": records,
    }


def _parse_boolean(value: str, row_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise EvaluationManifestError(
        f"Row {row_number} supported must be true/false, yes/no, or 1/0."
    )
