import json

import pytest

from desktop.history import (
    HistoryStorageError,
    ScanHistoryRecord,
    ScanHistoryStore,
    default_history_path,
)


def _record(index: int, confidence: float | None = 0.95) -> ScanHistoryRecord:
    return ScanHistoryRecord.create(
        record_id=f"record-{index}",
        created_at=f"2026-07-10T12:00:{index:02d}+00:00",
        image_name=rf"C:\private\photos\fruit-{index}.png",
        result_title="Fresh Apple" if confidence is not None else "Unsupported or uncertain photo",
        confidence=confidence,
        risk="Low" if confidence is not None else "Unknown",
        decision="accept_prediction" if confidence is not None else "uncertain_input",
        status="prediction_accepted" if confidence is not None else "unsupported_or_uncertain",
    )


def test_history_round_trip_stores_filename_without_photo_path(tmp_path):
    history_path = tmp_path / "history.json"
    store = ScanHistoryStore(history_path)

    store.add(_record(1))

    records = store.list_records()
    assert records[0].image_name == "fruit-1.png"
    raw_history = history_path.read_text(encoding="utf-8")
    assert "private" not in raw_history
    assert "photos" not in raw_history


def test_history_keeps_newest_records_with_bounded_retention(tmp_path):
    store = ScanHistoryStore(tmp_path / "history.json", max_records=2)

    store.add(_record(1))
    store.add(_record(2))
    store.add(_record(3))

    assert [record.record_id for record in store.list_records()] == ["record-3", "record-2"]


def test_history_preserves_uncertain_result_without_tentative_confidence(tmp_path):
    store = ScanHistoryStore(tmp_path / "history.json")

    store.add(_record(1, confidence=None))

    record = store.list_records()[0]
    assert record.result_title == "Unsupported or uncertain photo"
    assert record.confidence is None
    assert record.decision == "uncertain_input"


def test_history_rejects_corrupt_data_instead_of_overwriting_it(tmp_path):
    history_path = tmp_path / "history.json"
    history_path.write_text("not-json", encoding="utf-8")
    store = ScanHistoryStore(history_path)

    with pytest.raises(HistoryStorageError, match="invalid JSON"):
        store.add(_record(1))

    assert history_path.read_text(encoding="utf-8") == "not-json"


def test_history_exports_csv_and_can_be_cleared(tmp_path):
    store = ScanHistoryStore(tmp_path / "history.json")
    store.add(_record(1))
    export_path = tmp_path / "exports" / "history.csv"

    count = store.export_csv(export_path)

    exported = export_path.read_text(encoding="utf-8-sig")
    assert count == 1
    assert "created_at,image_name,result,confidence,risk,decision,status" in exported
    assert "fruit-1.png" in exported

    store.clear()
    assert store.list_records() == []


def test_default_history_path_can_be_overridden(monkeypatch, tmp_path):
    custom_path = tmp_path / "private-history.json"
    monkeypatch.setenv("FRESHSENSE_HISTORY_PATH", str(custom_path))

    assert default_history_path() == custom_path


def test_history_rejects_full_paths_loaded_from_disk(tmp_path):
    history_path = tmp_path / "history.json"
    payload = {
        "schema_version": 1,
        "records": [
            {
                **_record(1).to_dict(),
                "image_name": r"C:\private\fruit.png",
            }
        ],
    }
    history_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(HistoryStorageError, match="file names"):
        ScanHistoryStore(history_path).list_records()
