"""Dependency-light FreshSense evaluation metrics and SVG report artifacts."""

from __future__ import annotations

import csv
from html import escape
import json
from pathlib import Path
from statistics import mean, median

import numpy as np


def compute_metrics(
    results: list[dict[str, object]],
    *,
    class_labels: tuple[str, ...],
    freshness_by_label: dict[str, str],
    calibration_bins: int = 10,
) -> dict[str, object]:
    supported = [item for item in results if bool(item["supported"])]
    unsupported = [item for item in results if not bool(item["supported"])]
    accepted_supported = [item for item in supported if bool(item["accepted"])]
    correct_supported = [
        item for item in accepted_supported if item["predicted_label"] == item["true_label"]
    ]

    columns = (*class_labels, "__withheld__")
    confusion = [[0 for _ in columns] for _ in class_labels]
    label_index = {label: index for index, label in enumerate(class_labels)}
    column_index = {label: index for index, label in enumerate(columns)}
    for item in supported:
        true_label = str(item["true_label"])
        predicted = str(item["predicted_label"]) if item["accepted"] else "__withheld__"
        confusion[label_index[true_label]][column_index[predicted]] += 1

    per_class = {}
    for label in class_labels:
        total = sum(1 for item in supported if item["true_label"] == label)
        accepted = sum(
            1 for item in supported if item["true_label"] == label and item["accepted"]
        )
        true_positive = sum(
            1
            for item in supported
            if item["true_label"] == label
            and item["accepted"]
            and item["predicted_label"] == label
        )
        predicted_positive = sum(
            1
            for item in supported
            if item["accepted"] and item["predicted_label"] == label
        )
        precision = true_positive / predicted_positive if predicted_positive else 0.0
        recall = true_positive / total if total else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {
            "total": total,
            "accepted": accepted,
            "withheld": total - accepted,
            "true_positive": true_positive,
            "precision": precision,
            "recall_including_withheld": recall,
            "f1_including_withheld": f1,
            "coverage": accepted / total if total else 0.0,
        }

    rotten = [item for item in supported if freshness_by_label[str(item["true_label"])] == "rotten"]
    false_fresh = [
        item
        for item in rotten
        if item["accepted"]
        and freshness_by_label[str(item["predicted_label"])] == "fresh"
    ]
    unsupported_accepted = [item for item in unsupported if item["accepted"]]
    calibration = _calibration(accepted_supported, class_labels, calibration_bins)
    coverage_curve = _coverage_accuracy_curve(supported)
    latency_values = [float(item["latency_seconds"]) for item in results]

    return {
        "summary": {
            "supported_images": len(supported),
            "supported_accepted": len(accepted_supported),
            "supported_withheld": len(supported) - len(accepted_supported),
            "coverage": len(accepted_supported) / len(supported) if supported else 0.0,
            "overall_accuracy_including_withheld": (
                len(correct_supported) / len(supported) if supported else 0.0
            ),
            "selective_accuracy_when_accepted": (
                len(correct_supported) / len(accepted_supported)
                if accepted_supported
                else 0.0
            ),
            "rotten_images": len(rotten),
            "rotten_to_fresh_errors": len(false_fresh),
            "rotten_to_fresh_rate": len(false_fresh) / len(rotten) if rotten else 0.0,
            "unsupported_images": len(unsupported),
            "unsupported_accepted": len(unsupported_accepted),
            "unsupported_false_acceptance_rate": (
                len(unsupported_accepted) / len(unsupported) if unsupported else None
            ),
            "mean_latency_seconds": mean(latency_values) if latency_values else None,
            "median_latency_seconds": median(latency_values) if latency_values else None,
            "p95_latency_seconds": _percentile(latency_values, 95) if latency_values else None,
        },
        "per_class": per_class,
        "confusion_matrix": {
            "rows": list(class_labels),
            "columns": list(columns),
            "values": confusion,
        },
        "calibration": calibration,
        "coverage_accuracy_curve": coverage_curve,
        "segments": {
            field: _segment_metrics(supported, field)
            for field in ("device", "lighting", "background", "collection")
        },
    }


def write_report_bundle(report: dict[str, object], output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "evaluation_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    metrics = report["metrics"]
    confusion = metrics["confusion_matrix"]
    with (output / "confusion_matrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["true\\predicted", *confusion["columns"]])
        for label, values in zip(confusion["rows"], confusion["values"]):
            writer.writerow([label, *values])

    with (output / "per_class_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        fields = (
            "total",
            "accepted",
            "withheld",
            "true_positive",
            "precision",
            "recall_including_withheld",
            "f1_including_withheld",
            "coverage",
        )
        writer.writerow(["class", *fields])
        for label, values in metrics["per_class"].items():
            writer.writerow([label, *(values[field] for field in fields)])

    (output / "confusion_matrix.svg").write_text(
        _confusion_svg(confusion), encoding="utf-8"
    )
    (output / "reliability.svg").write_text(
        _line_chart_svg(
            metrics["calibration"]["bins"],
            x_key="mean_confidence",
            y_key="accuracy",
            title="Reliability diagram",
            x_label="Mean confidence",
            y_label="Observed accuracy",
            diagonal=True,
        ),
        encoding="utf-8",
    )
    (output / "coverage_accuracy.svg").write_text(
        _line_chart_svg(
            metrics["coverage_accuracy_curve"],
            x_key="coverage",
            y_key="accuracy",
            title="Accuracy versus retained coverage",
            x_label="Coverage",
            y_label="Selective accuracy",
        ),
        encoding="utf-8",
    )


def _calibration(items, class_labels, bin_count):
    bins = []
    ece = 0.0
    for index in range(bin_count):
        lower = index / bin_count
        upper = (index + 1) / bin_count
        selected = [
            item
            for item in items
            if lower <= float(item["confidence"]) < upper
            or (index == bin_count - 1 and float(item["confidence"]) == 1.0)
        ]
        if selected:
            mean_confidence = mean(float(item["confidence"]) for item in selected)
            accuracy = mean(
                1.0 if item["predicted_label"] == item["true_label"] else 0.0
                for item in selected
            )
            ece += len(selected) / max(1, len(items)) * abs(accuracy - mean_confidence)
        else:
            mean_confidence = (lower + upper) / 2
            accuracy = 0.0
        bins.append(
            {
                "lower": lower,
                "upper": upper,
                "count": len(selected),
                "mean_confidence": mean_confidence,
                "accuracy": accuracy,
            }
        )

    brier_values = []
    label_index = {label: index for index, label in enumerate(class_labels)}
    for item in items:
        probabilities = np.asarray(item["probabilities"], dtype=np.float64)
        target = np.zeros(len(class_labels), dtype=np.float64)
        target[label_index[str(item["true_label"])]] = 1.0
        brier_values.append(float(np.mean((probabilities - target) ** 2)))
    return {
        "expected_calibration_error": ece,
        "multiclass_brier_score": mean(brier_values) if brier_values else None,
        "bins": bins,
    }


def _coverage_accuracy_curve(items):
    if not items:
        return []
    gate_supported = [
        item for item in items if bool(item.get("gate_accepted", item["accepted"]))
    ]
    ordered = sorted(
        gate_supported, key=lambda item: float(item["confidence"]), reverse=True
    )
    if not ordered:
        return []
    points = []
    correct = 0
    total_supported = len(items)
    total_candidates = len(ordered)
    for index, item in enumerate(ordered, start=1):
        correct += item["predicted_label"] == item["true_label"]
        if index == total_candidates or index % max(1, total_candidates // 25) == 0:
            points.append(
                {
                    "coverage": index / total_supported,
                    "accuracy": correct / index,
                    "minimum_confidence": float(item["confidence"]),
                }
            )
    return points


def _segment_metrics(items, field):
    values = sorted({str(item.get(field, "unknown")) for item in items})
    result = {}
    for value in values:
        selected = [item for item in items if str(item.get(field, "unknown")) == value]
        accepted = [item for item in selected if item["accepted"]]
        correct = [item for item in accepted if item["predicted_label"] == item["true_label"]]
        result[value] = {
            "images": len(selected),
            "coverage": len(accepted) / len(selected) if selected else 0.0,
            "accuracy_including_withheld": len(correct) / len(selected) if selected else 0.0,
        }
    return result


def _percentile(values, percentile):
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _confusion_svg(confusion):
    rows = confusion["rows"]
    columns = confusion["columns"]
    values = confusion["values"]
    cell = 76
    left = 170
    top = 110
    width = left + cell * len(columns) + 30
    height = top + cell * len(rows) + 40
    maximum = max(max(row) for row in values) or 1
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="20" y="32" font-family="Segoe UI" font-size="20" font-weight="700">Confusion matrix</text>',
    ]
    for column, label in enumerate(columns):
        x = left + column * cell + cell / 2
        pieces.append(
            f'<text x="{x}" y="90" text-anchor="middle" font-family="Segoe UI" font-size="11">{escape(label)}</text>'
        )
    for row, label in enumerate(rows):
        y = top + row * cell + cell / 2
        pieces.append(
            f'<text x="160" y="{y + 4}" text-anchor="end" font-family="Segoe UI" font-size="11">{escape(label)}</text>'
        )
        for column, value in enumerate(values[row]):
            intensity = value / maximum
            shade = int(245 - intensity * 145)
            x = left + column * cell
            y0 = top + row * cell
            pieces.append(
                f'<rect x="{x}" y="{y0}" width="{cell}" height="{cell}" fill="rgb({shade},{min(250, shade + 35)},{shade})" stroke="#ffffff"/>'
            )
            pieces.append(
                f'<text x="{x + cell / 2}" y="{y0 + cell / 2 + 5}" text-anchor="middle" font-family="Segoe UI" font-size="14">{value}</text>'
            )
    pieces.append("</svg>")
    return "\n".join(pieces)


def _line_chart_svg(points, *, x_key, y_key, title, x_label, y_label, diagonal=False):
    width, height = 760, 480
    left, right, top, bottom = 70, 25, 55, 65
    plot_width = width - left - right
    plot_height = height - top - bottom
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="20" y="30" font-family="Segoe UI" font-size="20" font-weight="700">{escape(title)}</text>',
        f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top + plot_height}" stroke="#333"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_height}" stroke="#333"/>',
    ]
    for index in range(6):
        value = index / 5
        x = left + value * plot_width
        y = top + (1 - value) * plot_height
        pieces.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + plot_height}" stroke="#eee"/>')
        pieces.append(f'<line x1="{left}" y1="{y}" x2="{left + plot_width}" y2="{y}" stroke="#eee"/>')
        pieces.append(f'<text x="{x}" y="{top + plot_height + 20}" text-anchor="middle" font-family="Segoe UI" font-size="11">{value:.1f}</text>')
        pieces.append(f'<text x="{left - 10}" y="{y + 4}" text-anchor="end" font-family="Segoe UI" font-size="11">{value:.1f}</text>')
    if diagonal:
        pieces.append(f'<line x1="{left}" y1="{top + plot_height}" x2="{left + plot_width}" y2="{top}" stroke="#999" stroke-dasharray="6 5"/>')
    valid = [point for point in points if point.get(x_key) is not None and point.get(y_key) is not None]
    if valid:
        coordinates = " ".join(
            f'{left + float(point[x_key]) * plot_width},{top + (1 - float(point[y_key])) * plot_height}'
            for point in valid
        )
        pieces.append(f'<polyline points="{coordinates}" fill="none" stroke="#237A45" stroke-width="3"/>')
        for point in valid:
            x = left + float(point[x_key]) * plot_width
            y = top + (1 - float(point[y_key])) * plot_height
            pieces.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#237A45"/>')
    pieces.append(f'<text x="{left + plot_width / 2}" y="{height - 18}" text-anchor="middle" font-family="Segoe UI" font-size="13">{escape(x_label)}</text>')
    pieces.append(f'<text x="18" y="{top + plot_height / 2}" text-anchor="middle" transform="rotate(-90 18 {top + plot_height / 2})" font-family="Segoe UI" font-size="13">{escape(y_label)}</text>')
    pieces.append("</svg>")
    return "\n".join(pieces)
