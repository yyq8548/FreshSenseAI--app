"""Privacy-preserving SQLite records for a limited reviewed pilot."""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from statistics import mean, median
from uuid import uuid4


PILOT_SCHEMA_VERSION = 2
APP_DECISIONS = frozenset(
    {"accept_prediction", "uncertain_input", "unsupported_input", "retake_photo"}
)
REVIEWED_OUTCOMES = frozenset({"fresh", "rotten", "unsupported", "uncertain"})
BOOLEAN_FIELDS = ("result_understood", "warning_helpful", "would_use_again")


class PilotStoreError(ValueError):
    """Raised when pilot input or persisted records are invalid."""


class PilotStore:
    """Store anonymized review metadata in a local SQLite database."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS pilot_metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL
                    );
                    CREATE TABLE IF NOT EXISTS pilot_records (
                        record_id TEXT PRIMARY KEY,
                        recorded_at_utc TEXT NOT NULL,
                        sample_id TEXT NOT NULL,
                        reviewer TEXT NOT NULL,
                        app_decision TEXT NOT NULL,
                        predicted_freshness TEXT,
                        reviewed_outcome TEXT NOT NULL,
                        confidence REAL,
                        outcome_category TEXT NOT NULL,
                        device TEXT NOT NULL,
                        lighting TEXT NOT NULL,
                        background TEXT NOT NULL,
                        notes TEXT NOT NULL,
                        task_seconds REAL,
                        result_understood INTEGER,
                        warning_helpful INTEGER,
                        would_use_again INTEGER,
                        usability_rating INTEGER
                    );
                    CREATE INDEX IF NOT EXISTS idx_pilot_sample
                        ON pilot_records(sample_id);
                    CREATE INDEX IF NOT EXISTS idx_pilot_outcome
                        ON pilot_records(outcome_category);
                    """
                )
                existing = connection.execute(
                    "SELECT value FROM pilot_metadata WHERE key = 'schema_version'"
                ).fetchone()
                if existing is None:
                    connection.execute(
                        "INSERT INTO pilot_metadata(key, value) VALUES('schema_version', ?)",
                        (str(PILOT_SCHEMA_VERSION),),
                    )
                elif int(existing[0]) != PILOT_SCHEMA_VERSION:
                    raise PilotStoreError("Pilot store contains an unsupported schema.")
        except sqlite3.DatabaseError as exc:
            raise PilotStoreError(
                "Pilot store is not a valid FreshSense SQLite database. "
                "Use migrate-jsonl for a legacy JSONL store."
            ) from exc

    def add(
        self,
        *,
        sample_id: str,
        reviewer: str,
        app_decision: str,
        predicted_freshness: str | None,
        reviewed_outcome: str,
        confidence: float | None,
        device: str = "unknown",
        lighting: str = "unknown",
        background: str = "unknown",
        notes: str = "",
        task_seconds: float | None = None,
        result_understood: bool | None = None,
        warning_helpful: bool | None = None,
        would_use_again: bool | None = None,
        usability_rating: int | None = None,
    ) -> dict[str, object]:
        _validate_record(
            sample_id=sample_id,
            reviewer=reviewer,
            app_decision=app_decision,
            predicted_freshness=predicted_freshness,
            reviewed_outcome=reviewed_outcome,
            confidence=confidence,
            task_seconds=task_seconds,
            result_understood=result_understood,
            warning_helpful=warning_helpful,
            would_use_again=would_use_again,
            usability_rating=usability_rating,
        )
        record = {
            "schema_version": PILOT_SCHEMA_VERSION,
            "record_id": str(uuid4()),
            "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
            "sample_id": sample_id.strip(),
            "reviewer": reviewer.strip(),
            "app_decision": app_decision,
            "predicted_freshness": predicted_freshness,
            "reviewed_outcome": reviewed_outcome,
            "confidence": confidence,
            "outcome_category": _outcome_category(
                app_decision, predicted_freshness, reviewed_outcome
            ),
            "device": device.strip() or "unknown",
            "lighting": lighting.strip() or "unknown",
            "background": background.strip() or "unknown",
            "notes": notes.strip(),
            "task_seconds": task_seconds,
            "result_understood": result_understood,
            "warning_helpful": warning_helpful,
            "would_use_again": would_use_again,
            "usability_rating": usability_rating,
        }
        self.initialize()
        fields = tuple(key for key in record if key != "schema_version")
        values = [
            _sqlite_value(record[field]) if field in BOOLEAN_FIELDS else record[field]
            for field in fields
        ]
        placeholders = ", ".join("?" for _ in fields)
        with self._connect() as connection:
            connection.execute(
                f"INSERT INTO pilot_records ({', '.join(fields)}) VALUES ({placeholders})",
                values,
            )
        return record

    def records(self) -> list[dict[str, object]]:
        if not self.path.exists():
            return []
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM pilot_records ORDER BY recorded_at_utc, record_id"
            ).fetchall()
        records = []
        for row in rows:
            record = dict(row)
            record["schema_version"] = PILOT_SCHEMA_VERSION
            for field in BOOLEAN_FIELDS:
                record[field] = (
                    None if record[field] is None else bool(record[field])
                )
            records.append(record)
        return records

    def summary(self) -> dict[str, object]:
        records = self.records()
        categories = {
            category: sum(record["outcome_category"] == category for record in records)
            for category in (
                "correct",
                "false_fresh",
                "false_rotten",
                "uncertain",
                "unsupported",
                "retake",
                "not_comparable",
            )
        }
        reviewed_supported = sum(
            record["reviewed_outcome"] in {"fresh", "rotten"} for record in records
        )
        task_times = [float(item["task_seconds"]) for item in records if item["task_seconds"] is not None]
        ratings = [int(item["usability_rating"]) for item in records if item["usability_rating"] is not None]
        return {
            "records": len(records),
            "reviewers": len({str(record["reviewer"]) for record in records}),
            "reviewed_supported": reviewed_supported,
            "categories": categories,
            "false_fresh_rate": (
                categories["false_fresh"] / reviewed_supported
                if reviewed_supported
                else None
            ),
            "median_task_seconds": median(task_times) if task_times else None,
            "mean_usability_rating": mean(ratings) if ratings else None,
            "median_usability_rating": median(ratings) if ratings else None,
            "result_comprehension_rate": _boolean_rate(records, "result_understood"),
            "warning_helpful_rate": _boolean_rate(records, "warning_helpful"),
            "would_use_again_rate": _boolean_rate(records, "would_use_again"),
        }

    def export_csv(self, destination: str | Path) -> None:
        records = self.records()
        output = Path(destination)
        output.parent.mkdir(parents=True, exist_ok=True)
        fields = (
            "record_id",
            "recorded_at_utc",
            "sample_id",
            "reviewer",
            "app_decision",
            "predicted_freshness",
            "reviewed_outcome",
            "confidence",
            "outcome_category",
            "device",
            "lighting",
            "background",
            "task_seconds",
            "result_understood",
            "warning_helpful",
            "would_use_again",
            "usability_rating",
            "notes",
        )
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)

    def import_jsonl(self, source: str | Path) -> int:
        """Import validated records from the schema-v1 metadata-only JSONL store."""
        imported = 0
        for line_number, line in enumerate(
            Path(source).read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            try:
                legacy = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PilotStoreError(
                    f"Legacy pilot JSON is invalid on line {line_number}."
                ) from exc
            self.add(
                sample_id=str(legacy.get("sample_id", "")),
                reviewer=str(legacy.get("reviewer", "")),
                app_decision=str(legacy.get("app_decision", "")),
                predicted_freshness=legacy.get("predicted_freshness"),
                reviewed_outcome=str(legacy.get("reviewed_outcome", "")),
                confidence=legacy.get("confidence"),
                device=str(legacy.get("device", "unknown")),
                lighting=str(legacy.get("lighting", "unknown")),
                background=str(legacy.get("background", "unknown")),
                notes=str(legacy.get("notes", "")),
            )
            imported += 1
        return imported

    def import_csv(self, source: str | Path) -> int:
        """Import reviewed metadata from the public-beta observation template."""
        imported = 0
        with Path(source).open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            required = {
                "sample_id",
                "reviewer",
                "app_decision",
                "predicted_freshness",
                "reviewed_outcome",
                "confidence",
            }
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise PilotStoreError("Pilot CSV is missing required columns.")
            for row_number, row in enumerate(reader, start=2):
                if not any((value or "").strip() for value in row.values()):
                    continue
                try:
                    self.add(
                        sample_id=row["sample_id"],
                        reviewer=row["reviewer"],
                        app_decision=row["app_decision"],
                        predicted_freshness=_optional_text(row.get("predicted_freshness")),
                        reviewed_outcome=row["reviewed_outcome"],
                        confidence=_optional_float(row.get("confidence")),
                        device=row.get("device", "unknown"),
                        lighting=row.get("lighting", "unknown"),
                        background=row.get("background", "unknown"),
                        notes=row.get("notes", ""),
                        task_seconds=_optional_float(row.get("task_seconds")),
                        result_understood=_optional_bool(row.get("result_understood")),
                        warning_helpful=_optional_bool(row.get("warning_helpful")),
                        would_use_again=_optional_bool(row.get("would_use_again")),
                        usability_rating=_optional_int(row.get("usability_rating")),
                    )
                except (KeyError, TypeError, ValueError, PilotStoreError) as exc:
                    raise PilotStoreError(
                        f"Pilot CSV row {row_number} is invalid: {exc}"
                    ) from exc
                imported += 1
        return imported

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def _validate_record(**values: object) -> None:
    sample_id = str(values["sample_id"])
    if not sample_id.strip() or any(sep in sample_id for sep in ("/", "\\", ":")):
        raise PilotStoreError(
            "sample_id must be an anonymized identifier, not a photo path."
        )
    if not str(values["reviewer"]).strip():
        raise PilotStoreError("A reviewer identifier is required.")
    if values["app_decision"] not in APP_DECISIONS:
        raise PilotStoreError("Unsupported app_decision.")
    if values["reviewed_outcome"] not in REVIEWED_OUTCOMES:
        raise PilotStoreError("Unsupported reviewed_outcome.")
    predicted = values["predicted_freshness"]
    if predicted not in {None, "fresh", "rotten"}:
        raise PilotStoreError("predicted_freshness must be fresh, rotten, or omitted.")
    if values["app_decision"] != "accept_prediction" and predicted is not None:
        raise PilotStoreError("Withheld results cannot contain a predicted freshness.")
    confidence = values["confidence"]
    if confidence is not None and not 0.0 <= float(confidence) <= 1.0:
        raise PilotStoreError("confidence must be between 0 and 1.")
    task_seconds = values["task_seconds"]
    if task_seconds is not None and not 0.0 < float(task_seconds) <= 3600.0:
        raise PilotStoreError("task_seconds must be between 0 and 3600.")
    for field in BOOLEAN_FIELDS:
        value = values[field]
        if value is not None and not isinstance(value, bool):
            raise PilotStoreError(f"{field} must be true, false, or omitted.")
    rating = values["usability_rating"]
    if rating is not None and (not isinstance(rating, int) or not 1 <= rating <= 5):
        raise PilotStoreError("usability_rating must be an integer from 1 to 5.")


def _sqlite_value(value: object) -> int | None:
    return None if value is None else int(bool(value))


def _optional_text(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _optional_float(value: str | None) -> float | None:
    cleaned = (value or "").strip()
    return float(cleaned) if cleaned else None


def _optional_int(value: str | None) -> int | None:
    cleaned = (value or "").strip()
    return int(cleaned) if cleaned else None


def _optional_bool(value: str | None) -> bool | None:
    cleaned = (value or "").strip().lower()
    if not cleaned:
        return None
    if cleaned in {"true", "yes", "1"}:
        return True
    if cleaned in {"false", "no", "0"}:
        return False
    raise ValueError("boolean values must be yes/no, true/false, or 1/0")


def _boolean_rate(records: list[dict[str, object]], field: str) -> float | None:
    values = [bool(item[field]) for item in records if item[field] is not None]
    return sum(values) / len(values) if values else None


def _outcome_category(
    app_decision: str, predicted_freshness: str | None, reviewed_outcome: str
) -> str:
    if app_decision == "unsupported_input":
        return "unsupported"
    if app_decision == "uncertain_input":
        return "uncertain"
    if app_decision == "retake_photo":
        return "retake"
    if reviewed_outcome not in {"fresh", "rotten"}:
        return "not_comparable"
    if predicted_freshness == reviewed_outcome:
        return "correct"
    if predicted_freshness == "fresh" and reviewed_outcome == "rotten":
        return "false_fresh"
    if predicted_freshness == "rotten" and reviewed_outcome == "fresh":
        return "false_rotten"
    return "not_comparable"
