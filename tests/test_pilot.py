import pytest

from pilot.store import PilotStore, PilotStoreError


def test_pilot_tracks_false_fresh_and_exports_metadata_only(tmp_path):
    store = PilotStore(tmp_path / "pilot.sqlite3")
    store.add(
        sample_id="anon-001",
        reviewer="reviewer-a",
        app_decision="accept_prediction",
        predicted_freshness="fresh",
        reviewed_outcome="rotten",
        confidence=0.98,
        task_seconds=12.5,
        result_understood=True,
        warning_helpful=True,
        would_use_again=False,
        usability_rating=4,
    )
    store.add(
        sample_id="anon-002",
        reviewer="reviewer-a",
        app_decision="unsupported_input",
        predicted_freshness=None,
        reviewed_outcome="unsupported",
        confidence=None,
    )

    summary = store.summary()
    assert summary["categories"]["false_fresh"] == 1
    assert summary["categories"]["unsupported"] == 1
    assert summary["false_fresh_rate"] == 1.0
    assert summary["reviewers"] == 1
    assert summary["median_task_seconds"] == 12.5
    assert summary["result_comprehension_rate"] == 1.0
    assert summary["mean_usability_rating"] == 4

    output = tmp_path / "pilot.csv"
    store.export_csv(output)
    assert "photo_path" not in output.read_text(encoding="utf-8")


def test_pilot_rejects_photo_paths_as_sample_ids(tmp_path):
    store = PilotStore(tmp_path / "pilot.sqlite3")
    with pytest.raises(PilotStoreError, match="not a photo path"):
        store.add(
            sample_id=r"C:\photos\apple.jpg",
            reviewer="reviewer-a",
            app_decision="retake_photo",
            predicted_freshness=None,
            reviewed_outcome="uncertain",
            confidence=None,
        )


def test_pilot_database_contains_no_photo_or_filename_columns(tmp_path):
    import sqlite3

    store = PilotStore(tmp_path / "pilot.sqlite3")
    store.initialize()
    with sqlite3.connect(store.path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(pilot_records)")
        }

    assert "photo" not in columns
    assert "photo_path" not in columns
    assert "filename" not in columns
