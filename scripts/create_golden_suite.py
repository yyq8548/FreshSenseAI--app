"""Create a private, checksum-addressed supported-image suite for real-model CI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from evaluation.manifest import discover_dataset_root, load_manifest, sha256_file
from utils.fruit_catalog import load_fruit_catalog
from utils.config import FRUIT_CATALOG_PATH


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--per-class", type=int, default=2)
    parser.add_argument(
        "--evaluation-report",
        type=Path,
        default=PROJECT_ROOT
        / "evaluation"
        / "reports"
        / "current_model"
        / "evaluation_report.json",
    )
    args = parser.parse_args()

    catalog = load_fruit_catalog(FRUIT_CATALOG_PATH)
    dataset_root = discover_dataset_root(args.dataset, catalog.class_names)
    manifest = load_manifest(args.manifest)
    evaluation = json.loads(args.evaluation_report.read_text(encoding="utf-8"))
    accepted_sample_ids = {
        str(result["sample_id"])
        for result in evaluation.get("results", [])
        if result.get("supported")
        and result.get("accepted")
        and result.get("predicted_label") == result.get("true_label")
    }
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    samples = []
    for label in catalog.class_names:
        selected = [
            record
            for record in manifest["records"]
            if record["benchmark_split"] == "test"
            and record["label"] == label
            and str(record.get("sha256")) in accepted_sample_ids
        ][: args.per_class]
        if len(selected) != args.per_class:
            raise RuntimeError(f"Not enough test images were available for {label}.")
        for index, record in enumerate(selected):
            source = dataset_root / str(record["relative_path"])
            suffix = source.suffix.lower()
            relative = Path("images") / f"{label}_{index + 1}{suffix}"
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            samples.append(
                {
                    "path": relative.as_posix(),
                    "expected_label": label,
                    "sha256": sha256_file(target),
                }
            )
    payload = {"schema_version": 1, "samples": samples}
    (destination / "golden_manifest.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Golden suite created at: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
