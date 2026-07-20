"""Prepare a leakage-aware 12-class FreshSense classification dataset.

The legacy apple/banana/orange data is stored as class folders.  The newer
mango/tomato/pear exports are COCO archives, so their annotated fruit boxes
must be cropped before they are used by the classifier.  This module keeps all
crops from one source image in the same split and writes the standard
FreshSense evaluation manifest alongside the prepared images.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from typing import Iterable
from zipfile import ZipFile

from PIL import Image, ImageOps

from evaluation.manifest import canonical_source_name, sha256_file, write_manifest


CLASS_ORDER = (
    "freshapples",
    "freshbanana",
    "freshoranges",
    "freshmango",
    "freshtomato",
    "freshpear",
    "rottenapples",
    "rottenbanana",
    "rottenoranges",
    "rottenmango",
    "rottentomato",
    "rottenpear",
)

CLASS_METADATA = {
    "freshapples": ("apple", "fresh"),
    "freshbanana": ("banana", "fresh"),
    "freshoranges": ("orange", "fresh"),
    "freshmango": ("mango", "fresh"),
    "freshtomato": ("tomato", "fresh"),
    "freshpear": ("pear", "fresh"),
    "rottenapples": ("apple", "rotten"),
    "rottenbanana": ("banana", "rotten"),
    "rottenoranges": ("orange", "rotten"),
    "rottenmango": ("mango", "rotten"),
    "rottentomato": ("tomato", "rotten"),
    "rottenpear": ("pear", "rotten"),
}

COCO_ARCHIVES = {
    "Fresh Mango.coco.zip": "freshmango",
    "Fresh Tomato.coco.zip": "freshtomato",
    "fresh pear.coco.zip": "freshpear",
    "Rotten Mango.coco.zip": "rottenmango",
    "Rotten Tomato.coco.zip": "rottentomato",
    "rotten pear.coco.zip": "rottenpear",
}

_ROBOFLOW_SUFFIX = re.compile(r"\.rf\.[^.]+(?=\.[^.]+$)", re.IGNORECASE)


def prepare_expanded_dataset(
    source_root: str | Path,
    output_root: str | Path,
    *,
    image_size: int = 224,
    jpeg_quality: int = 92,
    crop_padding: float = 0.08,
    split_seed: str = "freshsense-expanded-v1",
) -> dict[str, object]:
    """Create prepared images and return a validated manifest payload."""
    source = Path(source_root).expanduser().resolve()
    output = Path(output_root).expanduser().resolve()
    train_root = source / "train"
    test_root = source / "test"
    if not train_root.is_dir() or not test_root.is_dir():
        raise FileNotFoundError("Expected source_root/train and source_root/test directories.")
    output.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    _prepare_legacy_classes(
        train_root,
        test_root,
        output,
        records,
        image_size=image_size,
        jpeg_quality=jpeg_quality,
        split_seed=split_seed,
    )
    for archive_name, label in COCO_ARCHIVES.items():
        archive_path = train_root / archive_name
        if not archive_path.is_file():
            raise FileNotFoundError(f"Missing COCO archive: {archive_path}")
        _prepare_coco_archive(
            archive_path,
            label,
            output,
            records,
            image_size=image_size,
            jpeg_quality=jpeg_quality,
            crop_padding=crop_padding,
            split_seed=split_seed,
        )

    records.sort(key=lambda item: (str(item["benchmark_split"]), str(item["label"]), str(item["relative_path"])))
    split_summary: dict[str, dict[str, int]] = {}
    for split in ("train", "validation", "test"):
        selected = [record for record in records if record["benchmark_split"] == split]
        split_summary[split] = {
            "images": len(selected),
            "source_groups": len({str(record["group_id"]) for record in selected}),
        }
    class_counts = {
        label: {
            split: sum(
                1
                for record in records
                if record["label"] == label and record["benchmark_split"] == split
            )
            for split in ("train", "validation", "test")
        }
        for label in CLASS_ORDER
    }
    manifest: dict[str, object] = {
        "schema_version": 1,
        "dataset_name": "freshsense_expanded_12_class_v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_root_name": output.name,
        "dataset_root_hint": (
            "Set FRESHSENSE_EXPANDED_DATASET_ROOT to the prepared dataset directory."
        ),
        "class_order": list(CLASS_ORDER),
        "grouping_rule": "source image identity; all COCO object crops stay together",
        "split_seed": split_seed,
        "split_ratios": {"train": 0.70, "validation": 0.15, "test": 0.15},
        "summary": {
            "images": len(records),
            "source_groups": len({str(record["group_id"]) for record in records}),
            "grouped_splits": split_summary,
            "class_counts": class_counts,
            "validity_warning": (
                "This benchmark uses existing public/source exports and is not an "
                "independent real-world store benchmark. Report metrics as development results."
            ),
        },
        "records": records,
    }
    write_manifest(manifest, output / "manifest.json")
    return manifest


def _prepare_legacy_classes(
    train_root: Path,
    test_root: Path,
    output: Path,
    records: list[dict[str, object]],
    *,
    image_size: int,
    jpeg_quality: int,
    split_seed: str,
) -> None:
    labels = CLASS_ORDER[:3] + CLASS_ORDER[6:9]
    candidates: list[tuple[Path, str, str, str]] = []
    for source_split, split_root in (("train", train_root), ("test", test_root)):
        for label in labels:
            class_dir = split_root / label
            if not class_dir.is_dir():
                raise FileNotFoundError(f"Missing legacy class directory: {class_dir}")
            for path in sorted(class_dir.iterdir(), key=lambda item: item.name.lower()):
                if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
                    continue
                source_name = canonical_source_name(path.name)
                group_id = _group_id(label, source_name)
                candidates.append((path, label, source_split, group_id))

    # Re-split all legacy source groups.  Their original train/test directories
    # contain known source-name overlap and are therefore not treated as a clean test.
    assignments = _assign_groups((item[3] for item in candidates), split_seed)
    for index, (path, label, source_split, group_id) in enumerate(candidates):
        benchmark_split = assignments[group_id]
        destination = output / benchmark_split / label / f"legacy_{index:06d}.jpg"
        try:
            with Image.open(path) as image:
                _save_classification_image(image, destination, image_size, jpeg_quality)
        except (OSError, ValueError):
            continue
        records.append(
            _record(
                destination,
                output,
                label,
                source_split,
                benchmark_split,
                group_id,
                path.name,
                "legacy_fruits_fresh_and_rotten",
            )
        )


def _prepare_coco_archive(
    archive_path: Path,
    label: str,
    output: Path,
    records: list[dict[str, object]],
    *,
    image_size: int,
    jpeg_quality: int,
    crop_padding: float,
    split_seed: str,
) -> None:
    with ZipFile(archive_path) as archive:
        annotation_entries = sorted(
            name for name in archive.namelist() if name.endswith("/_annotations.coco.json")
        )
        if not annotation_entries:
            raise ValueError(f"No COCO annotations found in {archive_path.name}.")

        staged: list[tuple[str, str, dict[str, object], list[dict[str, object]], str]] = []
        source_groups: set[str] = set()
        for annotation_entry in annotation_entries:
            source_split = annotation_entry.split("/", 1)[0]
            payload = json.loads(archive.read(annotation_entry))
            annotations_by_image: dict[int, list[dict[str, object]]] = defaultdict(list)
            for annotation in payload.get("annotations", []):
                annotations_by_image[int(annotation["image_id"])].append(annotation)
            for image_info in payload.get("images", []):
                annotations = annotations_by_image.get(int(image_info["id"]), [])
                if not annotations:
                    continue
                source_name = str(image_info["file_name"])
                canonical_name = _ROBOFLOW_SUFFIX.sub("", source_name)
                group_id = _group_id(label, canonical_name)
                staged.append((source_split, annotation_entry, image_info, annotations, group_id))
                source_groups.add(group_id)

        # Roboflow exports can place differently augmented versions of one source
        # image in separate exported splits.  Reassign every COCO source group so
        # an original image and all of its crops can never cross split boundaries.
        group_assignments = _assign_groups(source_groups, f"{split_seed}:{label}")
        output_index = 0
        for source_split, annotation_entry, image_info, annotations, group_id in staged:
            benchmark_split = group_assignments[group_id]
            image_entry = f"{source_split}/{image_info['file_name']}"
            try:
                with Image.open(BytesIO(archive.read(image_entry))) as image:
                    image = ImageOps.exif_transpose(image).convert("RGB")
                    width, height = image.size
                    for crop_index, annotation in enumerate(annotations):
                        bbox = annotation.get("bbox")
                        if not isinstance(bbox, list) or len(bbox) != 4:
                            continue
                        box = _padded_box(bbox, width, height, crop_padding)
                        if box is None:
                            continue
                        destination = (
                            output
                            / benchmark_split
                            / label
                            / f"coco_{archive_path.stem.replace(' ', '_')}_{output_index:06d}_{crop_index:02d}.jpg"
                        )
                        _save_classification_image(
                            image.crop(box), destination, image_size, jpeg_quality
                        )
                        records.append(
                            _record(
                                destination,
                                output,
                                label,
                                source_split,
                                benchmark_split,
                                group_id,
                                str(image_info["file_name"]),
                                archive_path.name,
                            )
                        )
                    output_index += 1
            except (KeyError, OSError, ValueError):
                continue


def _save_classification_image(
    image: Image.Image, destination: Path, image_size: int, jpeg_quality: int
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    prepared = ImageOps.fit(
        ImageOps.exif_transpose(image).convert("RGB"),
        (image_size, image_size),
        method=Image.Resampling.LANCZOS,
    )
    prepared.save(destination, "JPEG", quality=jpeg_quality, optimize=True)


def _padded_box(
    bbox: list[object], width: int, height: int, padding: float
) -> tuple[int, int, int, int] | None:
    x, y, box_width, box_height = (float(value) for value in bbox)
    if box_width < 8 or box_height < 8 or box_width * box_height < width * height * 0.002:
        return None
    pad_x = box_width * padding
    pad_y = box_height * padding
    left = max(0, int(x - pad_x))
    top = max(0, int(y - pad_y))
    right = min(width, int(x + box_width + pad_x + 0.999))
    bottom = min(height, int(y + box_height + pad_y + 0.999))
    return (left, top, right, bottom) if right > left and bottom > top else None


def _assign_groups(group_ids: Iterable[str], seed: str) -> dict[str, str]:
    ordered = sorted(
        set(group_ids), key=lambda value: sha256(f"{seed}:{value}".encode()).digest()
    )
    assignments = {}
    for index, group_id in enumerate(ordered):
        fraction = index / max(1, len(ordered))
        assignments[group_id] = (
            "train" if fraction < 0.70 else "validation" if fraction < 0.85 else "test"
        )
    return assignments


def _group_id(label: str, source_name: str) -> str:
    return sha256(f"{label}:{source_name.lower()}".encode("utf-8")).hexdigest()[:20]


def _record(
    destination: Path,
    root: Path,
    label: str,
    source_split: str,
    benchmark_split: str,
    group_id: str,
    source_name: str,
    collection: str,
) -> dict[str, object]:
    fruit, freshness = CLASS_METADATA[label]
    return {
        "relative_path": destination.relative_to(root).as_posix(),
        "source_split": source_split,
        "benchmark_split": benchmark_split,
        "label": label,
        "fruit": fruit,
        "freshness": freshness,
        "supported": True,
        "group_id": group_id,
        "source_name": source_name,
        "augmentation": "source_export",
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "device": "unknown",
        "lighting": "unknown",
        "background": "unknown",
        "collection": collection,
    }
