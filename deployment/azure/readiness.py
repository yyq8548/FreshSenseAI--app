"""Evidence-based, fail-closed gate before any FreshSense Azure deployment."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pilot.store import PilotStore, PilotStoreError


DEFAULT_THRESHOLDS = {
    "minimum_supported_test_images": 400,
    "minimum_unsupported_test_images": 400,
    "maximum_false_fresh_rate": 0.02,
    "maximum_unsupported_false_acceptance_rate": 0.05,
    "minimum_supported_coverage": 0.80,
    "minimum_selective_accuracy": 0.90,
    "minimum_pilot_records": 100,
    "minimum_pilot_reviewers": 5,
    "minimum_comprehension_rate": 0.90,
    "minimum_median_usability_rating": 4.0,
}


def evaluate_azure_readiness(
    *,
    evaluation_report_path: str | Path,
    pilot_database_path: str | Path,
    test_evidence_path: str | Path,
    approval_path: str | Path,
    thresholds: dict[str, float | int] | None = None,
) -> dict[str, object]:
    active_thresholds = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    checks: list[dict[str, object]] = []

    evaluation = _read_json(evaluation_report_path, "independent evaluation", checks)
    if evaluation is not None:
        validity = evaluation.get("validity", {})
        metrics = evaluation.get("metrics", {}).get("summary", {})
        _check(
            checks,
            "independent_real_world_benchmark",
            validity.get("independent_real_world_benchmark") is True,
            validity.get("independent_real_world_benchmark"),
            True,
        )
        _minimum(checks, "supported_test_images", metrics.get("supported_images"), active_thresholds["minimum_supported_test_images"])
        _minimum(checks, "unsupported_test_images", metrics.get("unsupported_images"), active_thresholds["minimum_unsupported_test_images"])
        _maximum(checks, "false_fresh_rate", metrics.get("rotten_to_fresh_rate"), active_thresholds["maximum_false_fresh_rate"])
        _maximum(
            checks,
            "unsupported_false_acceptance_rate",
            metrics.get("unsupported_false_acceptance_rate"),
            active_thresholds["maximum_unsupported_false_acceptance_rate"],
        )
        _minimum(checks, "supported_coverage", metrics.get("coverage"), active_thresholds["minimum_supported_coverage"])
        _minimum(
            checks,
            "selective_accuracy",
            metrics.get("selective_accuracy_when_accepted"),
            active_thresholds["minimum_selective_accuracy"],
        )

    pilot_path = Path(pilot_database_path)
    if not pilot_path.is_file():
        _check(checks, "pilot_database_available", False, None, "SQLite pilot database")
    else:
        try:
            pilot = PilotStore(pilot_path).summary()
        except PilotStoreError:
            _check(checks, "pilot_database_valid", False, "invalid", "valid SQLite pilot database")
        else:
            _minimum(checks, "pilot_records", pilot.get("records"), active_thresholds["minimum_pilot_records"])
            _minimum(checks, "pilot_reviewers", pilot.get("reviewers"), active_thresholds["minimum_pilot_reviewers"])
            _maximum(checks, "pilot_false_fresh_rate", pilot.get("false_fresh_rate"), active_thresholds["maximum_false_fresh_rate"])
            _minimum(
                checks,
                "pilot_result_comprehension_rate",
                pilot.get("result_comprehension_rate"),
                active_thresholds["minimum_comprehension_rate"],
            )
            _minimum(
                checks,
                "pilot_median_usability_rating",
                pilot.get("median_usability_rating"),
                active_thresholds["minimum_median_usability_rating"],
            )

    test_evidence = _read_json(test_evidence_path, "automated test evidence", checks)
    if test_evidence is not None:
        _check(
            checks,
            "automated_tests_passed",
            test_evidence.get("passed") is True and int(test_evidence.get("tests", 0)) >= 100,
            {"passed": test_evidence.get("passed"), "tests": test_evidence.get("tests")},
            {"passed": True, "minimum_tests": 100},
        )

    approvals = _read_json(approval_path, "manual approval evidence", checks)
    if approvals is not None:
        for name in (
            "business_owner_approved",
            "technology_owner_approved",
            "security_review_approved",
        ):
            _check(checks, name, approvals.get(name) is True, approvals.get(name), True)

    ready = bool(checks) and all(bool(check["passed"]) for check in checks)
    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "decision": "ready_for_nonproduction_review" if ready else "blocked",
        "ready": ready,
        "thresholds": active_thresholds,
        "checks": checks,
        "failed_checks": [str(check["name"]) for check in checks if not check["passed"]],
        "note": (
            "Passing this gate permits a Technology-team non-production review only; "
            "it is not approval for autonomous food-safety use."
        ),
    }


def _read_json(path: str | Path, label: str, checks: list[dict[str, object]]) -> dict[str, Any] | None:
    source = Path(path)
    if not source.is_file():
        _check(checks, f"{label.replace(' ', '_')}_available", False, None, str(source))
        return None
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        _check(checks, f"{label.replace(' ', '_')}_valid", False, "invalid", "valid JSON")
        return None
    if not isinstance(value, dict):
        _check(checks, f"{label.replace(' ', '_')}_valid", False, type(value).__name__, "JSON object")
        return None
    return value


def _minimum(checks, name, observed, required):
    passed = observed is not None and float(observed) >= float(required)
    _check(checks, name, passed, observed, {"minimum": required})


def _maximum(checks, name, observed, required):
    passed = observed is not None and float(observed) <= float(required)
    _check(checks, name, passed, observed, {"maximum": required})


def _check(checks, name, passed, observed, required):
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "observed": observed,
            "required": required,
        }
    )
