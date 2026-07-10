"""Private, on-device scan history storage for the desktop application."""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


HISTORY_SCHEMA_VERSION = 1
DEFAULT_MAX_RECORDS = 200


class HistoryStorageError(RuntimeError):
    """Raised when scan history cannot be safely read or written."""


@dataclass(frozen=True)
class ScanHistoryRecord:
    record_id: str
    created_at: str
    image_name: str
    result_title: str
    confidence: float | None
    risk: str
    decision: str
    status: str

    @classmethod
    def create(
        cls,
        *,
        image_name: str,
        result_title: str,
        confidence: float | None,
        risk: str,
        decision: str,
        status: str,
        created_at: str | None = None,
        record_id: str | None = None,
    ) -> "ScanHistoryRecord":
        safe_image_name = image_name.replace("\\", "/").rsplit("/", 1)[-1].strip()
        record = cls(
            record_id=record_id or uuid4().hex,
            created_at=created_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            image_name=safe_image_name,
            result_title=result_title.strip(),
            confidence=confidence,
            risk=risk.strip(),
            decision=decision.strip(),
            status=status.strip(),
        )
        record.validate()
        return record

    @classmethod
    def from_dict(cls, payload: object) -> "ScanHistoryRecord":
        if not isinstance(payload, dict):
            raise HistoryStorageError("Every scan-history record must be an object.")
        required = {
            "record_id",
            "created_at",
            "image_name",
            "result_title",
            "confidence",
            "risk",
            "decision",
            "status",
        }
        if set(payload) != required:
            raise HistoryStorageError("A scan-history record has missing or unknown fields.")
        record = cls(**payload)
        record.validate()
        return record

    def validate(self) -> None:
        text_fields = {
            "record_id": self.record_id,
            "created_at": self.created_at,
            "image_name": self.image_name,
            "result_title": self.result_title,
            "risk": self.risk,
            "decision": self.decision,
            "status": self.status,
        }
        if any(not isinstance(value, str) or not value.strip() for value in text_fields.values()):
            raise HistoryStorageError("Scan-history text fields must be non-empty strings.")
        if "/" in self.image_name or "\\" in self.image_name:
            raise HistoryStorageError("Scan history stores file names, not full image paths.")
        try:
            datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise HistoryStorageError("Scan-history timestamps must be ISO-8601 values.") from exc
        if self.confidence is not None:
            if not isinstance(self.confidence, (int, float)) or not 0 <= self.confidence <= 1:
                raise HistoryStorageError("Scan-history confidence must be between 0 and 1.")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def default_history_path() -> Path:
    override = os.getenv("FRESHSENSE_HISTORY_PATH")
    if override:
        return Path(override).expanduser()

    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "FreshSense" / "scan_history.json"
    return Path.home() / ".freshsense" / "scan_history.json"


class ScanHistoryStore:
    def __init__(self, path: str | Path | None = None, max_records: int = DEFAULT_MAX_RECORDS):
        if max_records < 1:
            raise ValueError("max_records must be at least 1.")
        self.path = Path(path) if path is not None else default_history_path()
        self.max_records = max_records

    def list_records(self) -> list[ScanHistoryRecord]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HistoryStorageError("Scan history is unavailable or contains invalid JSON.") from exc

        if not isinstance(payload, dict) or payload.get("schema_version") != HISTORY_SCHEMA_VERSION:
            raise HistoryStorageError("Scan history has an unsupported schema version.")
        raw_records = payload.get("records")
        if not isinstance(raw_records, list):
            raise HistoryStorageError("Scan history must contain a records list.")
        return [ScanHistoryRecord.from_dict(item) for item in raw_records]

    def add(self, record: ScanHistoryRecord) -> None:
        record.validate()
        records = [item for item in self.list_records() if item.record_id != record.record_id]
        self._write([record, *records][: self.max_records])

    def clear(self) -> None:
        self._write([])

    def export_csv(self, destination: str | Path) -> int:
        records = self.list_records()
        output = Path(destination)
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    [
                        "created_at",
                        "image_name",
                        "result",
                        "confidence",
                        "risk",
                        "decision",
                        "status",
                    ]
                )
                for record in records:
                    writer.writerow(
                        [
                            record.created_at,
                            record.image_name,
                            record.result_title,
                            "" if record.confidence is None else f"{record.confidence:.6f}",
                            record.risk,
                            record.decision,
                            record.status,
                        ]
                    )
        except OSError as exc:
            raise HistoryStorageError("Scan history could not be exported.") from exc
        return len(records)

    def _write(self, records: list[ScanHistoryRecord]) -> None:
        payload = {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "records": [record.to_dict() for record in records],
        }
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError as exc:
            raise HistoryStorageError("Scan history could not be saved.") from exc
