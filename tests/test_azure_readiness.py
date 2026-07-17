import json

from deployment.azure.readiness import evaluate_azure_readiness
from pilot.store import PilotStore


def test_azure_readiness_fails_closed_when_evidence_is_missing(tmp_path):
    report = evaluate_azure_readiness(
        evaluation_report_path=tmp_path / "missing-evaluation.json",
        pilot_database_path=tmp_path / "missing-pilot.sqlite3",
        test_evidence_path=tmp_path / "missing-tests.json",
        approval_path=tmp_path / "missing-approvals.json",
    )

    assert report["ready"] is False
    assert report["decision"] == "blocked"
    assert len(report["failed_checks"]) == 4


def test_azure_readiness_passes_complete_nonproduction_evidence(tmp_path):
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(
        json.dumps(
            {
                "validity": {"independent_real_world_benchmark": True},
                "metrics": {
                    "summary": {
                        "supported_images": 500,
                        "unsupported_images": 450,
                        "rotten_to_fresh_rate": 0.01,
                        "unsupported_false_acceptance_rate": 0.03,
                        "coverage": 0.85,
                        "selective_accuracy_when_accepted": 0.95,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    pilot_path = tmp_path / "pilot.sqlite3"
    pilot = PilotStore(pilot_path)
    for index in range(100):
        pilot.add(
            sample_id=f"anon-{index:03d}",
            reviewer=f"reviewer-{index % 5}",
            app_decision="accept_prediction",
            predicted_freshness="fresh",
            reviewed_outcome="fresh",
            confidence=0.9,
            result_understood=True,
            warning_helpful=True,
            would_use_again=True,
            usability_rating=4,
        )
    tests = tmp_path / "tests.json"
    tests.write_text(json.dumps({"passed": True, "tests": 120}), encoding="utf-8")
    approvals = tmp_path / "approvals.json"
    approvals.write_text(
        json.dumps(
            {
                "business_owner_approved": True,
                "technology_owner_approved": True,
                "security_review_approved": True,
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_azure_readiness(
        evaluation_report_path=evaluation,
        pilot_database_path=pilot_path,
        test_evidence_path=tests,
        approval_path=approvals,
    )

    assert report["ready"] is True
    assert report["decision"] == "ready_for_nonproduction_review"
    assert report["failed_checks"] == []
