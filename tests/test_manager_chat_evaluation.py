from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.manager_chat import _match_inspections
from evaluation.manager_chat import (
    ManagerChatEvaluationError,
    load_manager_chat_manifest,
    run_manager_chat_evaluation,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PROJECT_ROOT / "evaluation" / "manifests" / "manager_chat_v1.json"


def test_explicit_unknown_batch_fails_closed_instead_of_using_recent_records():
    inspections = [
        {
            "inspection_id": "one",
            "batch_reference": "OR-42",
            "location_name": "Main store",
            "fruit": "orange",
            "predicted_display_name": "Rotten Orange",
        }
    ]

    assert _match_inspections("Show batch SECRET-77", inspections) == []
    assert _match_inspections("总结批次编号 SECRET-77", inspections) == []
    assert _match_inspections("Show pear inspections", inspections) == []
    assert _match_inspections("Show recent inspections", inspections) == inspections


def test_manager_chat_fallback_evaluation_passes_and_writes_reports(tmp_path):
    report = run_manager_chat_evaluation(
        manifest_path=MANIFEST,
        output_dir=tmp_path / "report",
        mode="fallback",
    )

    assert report["quality_gates"]["passed"] is True
    assert report["metrics"]["case_pass_rate"] == 1.0
    assert report["metrics"]["safety_boundary_rate"] == 1.0
    assert report["metrics"]["categories"]["workspace_isolation"]["pass_rate"] == 1.0
    written = json.loads(
        (tmp_path / "report" / "evaluation_report.json").read_text(encoding="utf-8")
    )
    assert written["dataset_version"] == "manager_chat_v1"
    assert (tmp_path / "report" / "evaluation_summary.md").exists()


def test_manager_chat_manifest_rejects_an_unknown_schema(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"schema_version": 2, "fixtures": [], "cases": []}', encoding="utf-8")

    with pytest.raises(ManagerChatEvaluationError, match="schema_version"):
        load_manager_chat_manifest(path)
