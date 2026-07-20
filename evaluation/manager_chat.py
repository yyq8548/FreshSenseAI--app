"""Versioned, reproducible evaluation for FreshSense Manager Chat.

The default evaluation uses the production grounded fallback and synthetic
workspace data. It never needs an API key and never sends production records to
an external model. An explicit ``openai`` mode can evaluate the configured
Responses API model against the same cases.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any, Mapping

from agent.manager_chat import ManagerChatService, OpenAIManagerChatResponder
from saas.store import SaaSStore


class ManagerChatEvaluationError(RuntimeError):
    """Raised when an evaluation manifest or run is invalid."""


@dataclass(frozen=True)
class _StaticRetriever:
    documents: tuple[dict[str, Any], ...]

    def retrieve(self, query: str) -> list[dict[str, Any]]:
        del query
        return [dict(document) for document in self.documents]


class _UnavailableResponder:
    model = "unavailable-evaluation-provider"

    def generate(self, *, system_prompt: str, payload: Mapping[str, Any]) -> str:
        del system_prompt, payload
        raise RuntimeError("Synthetic provider outage for fallback evaluation.")


def load_manager_chat_manifest(path: str | Path) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagerChatEvaluationError(
            f"Could not read Manager Chat manifest: {manifest_path}"
        ) from exc
    if value.get("schema_version") != 1:
        raise ManagerChatEvaluationError("Manager Chat manifest schema_version must be 1.")
    if not isinstance(value.get("fixtures"), list) or not value["fixtures"]:
        raise ManagerChatEvaluationError("Manager Chat manifest needs fixtures.")
    if not isinstance(value.get("cases"), list) or not value["cases"]:
        raise ManagerChatEvaluationError("Manager Chat manifest needs cases.")
    case_ids = [str(case.get("id", "")) for case in value["cases"]]
    if any(not case_id for case_id in case_ids) or len(case_ids) != len(set(case_ids)):
        raise ManagerChatEvaluationError("Manager Chat case IDs must be unique and non-empty.")
    return value


def run_manager_chat_evaluation(
    *,
    manifest_path: str | Path,
    output_dir: str | Path,
    mode: str = "fallback",
) -> dict[str, Any]:
    """Run every manifest turn and write JSON plus human-readable reports."""
    if mode not in {"fallback", "openai"}:
        raise ManagerChatEvaluationError("mode must be 'fallback' or 'openai'.")
    manifest = load_manager_chat_manifest(manifest_path)
    if mode == "openai":
        responder = OpenAIManagerChatResponder()
        if not responder.available:
            raise ManagerChatEvaluationError(
                "OpenAI evaluation requires LLM reasoning and OPENAI_API_KEY."
            )
    else:
        responder = _UnavailableResponder()

    with TemporaryDirectory(prefix="freshsense-manager-chat-eval-") as temp_dir:
        store = SaaSStore(Path(temp_dir) / "evaluation.db")
        fixture_map = _seed_store(store, manifest["fixtures"])
        retriever = _StaticRetriever(tuple(manifest.get("knowledge", ())))
        service = ManagerChatService(
            store,
            retriever=retriever,
            responder=responder,
            responder_available=(lambda: True) if mode == "openai" else (lambda: False),
        )
        try:
            results = [
                _run_case(
                    case=case,
                    store=store,
                    service=service,
                    fixture_map=fixture_map,
                    mode=mode,
                )
                for case in manifest["cases"]
            ]
        finally:
            # SQLAlchemy keeps SQLite connections pooled until disposal. Close
            # them explicitly so Windows can remove the temporary database.
            store.database.dispose()

    report = {
        "schema_version": 1,
        "dataset_version": manifest.get("dataset_version"),
        "mode": mode,
        "metrics": _metrics(results),
        "quality_gates": {},
        "cases": results,
        "limitations": [
            "Synthetic records test application behavior, not production answer quality.",
            "Fallback mode is deterministic; OpenAI mode must be run separately before release.",
            "Human review remains required for usefulness, tone, and operational correctness.",
        ],
    }
    report["quality_gates"] = _quality_gates(report["metrics"], mode=mode)
    _write_report(report, output_dir)
    return report


def _seed_store(
    store: SaaSStore,
    fixtures: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    seeded: dict[str, dict[str, Any]] = {}
    for fixture in fixtures:
        fixture_id = str(fixture["id"])
        identity_hash = str(fixture["identity_hash"])
        store.workspace(identity_hash)
        inspection_map: dict[str, dict[str, Any]] = {}
        for item in fixture.get("inspections", []):
            analysis = {
                "decision": item.get("decision", "accept_prediction"),
                "status": "completed",
                "prediction": {
                    "class_name": item["class_name"],
                    "display_name": item["display_name"],
                    "fruit": item["fruit"],
                    "freshness": item["freshness"],
                    "confidence": item["confidence"],
                },
                "reasoning": {"risk_level": item.get("risk_level", "medium")},
                "warnings": [{"level": "warning", "message": "Visual assessment only."}],
                "recommendation": item.get(
                    "recommendation", "Inspect the physical batch."
                ),
                "safety_notice": "Not a food-safety test.",
            }
            inspection = store.record_inspection(
                identity_hash=identity_hash,
                location_name=item["location_name"],
                batch_reference=item["batch_reference"],
                operator_note=item.get("operator_note", "Evaluation fixture"),
                analysis=analysis,
                model_version="manager-chat-eval-v1",
            )
            inspection_map[item["batch_reference"]] = inspection
            review = item.get("review")
            if review:
                store.review_inspection(
                    identity_hash=identity_hash,
                    inspection_id=inspection["inspection_id"],
                    review_status=review["status"],
                    reviewed_outcome=review.get("outcome"),
                    note=review.get("note", "Evaluation review"),
                )

        for agent_fixture in fixture.get("agent_runs", []):
            inspection = inspection_map[agent_fixture["batch_reference"]]
            run = store.create_agent_run(
                identity_hash=identity_hash,
                inspection_id=inspection["inspection_id"],
                objective=agent_fixture.get("objective", "Assess inspection follow-up."),
                planner_version="manager-chat-eval-v1",
                max_steps=4,
                mode="supervised",
            )
            proposal = store.create_action_proposal(
                identity_hash=identity_hash,
                run_id=run["run_id"],
                inspection_id=inspection["inspection_id"],
                action_type=agent_fixture["action_type"],
                policy_decision=agent_fixture["policy_decision"],
                rationale=agent_fixture["rationale"],
                payload={"batch_reference": agent_fixture["batch_reference"]},
                execution_status="pending",
            )
            if agent_fixture.get("request_approval"):
                store.request_agent_approval(
                    identity_hash=identity_hash,
                    run_id=run["run_id"],
                    proposal_id=proposal["proposal_id"],
                    inspection_id=inspection["inspection_id"],
                    action_type=agent_fixture["action_type"],
                    rationale=agent_fixture["rationale"],
                    payload={"batch_reference": agent_fixture["batch_reference"]},
                )
            store.complete_agent_run(
                identity_hash=identity_hash,
                run_id=run["run_id"],
                final_summary=agent_fixture.get(
                    "summary", "A manager decision is required before any batch hold."
                ),
            )
        seeded[fixture_id] = {
            "identity_hash": identity_hash,
            "inspections": inspection_map,
        }
    return seeded


def _run_case(
    *,
    case: Mapping[str, Any],
    store: SaaSStore,
    service: ManagerChatService,
    fixture_map: Mapping[str, Mapping[str, Any]],
    mode: str,
) -> dict[str, Any]:
    fixture = fixture_map[str(case["fixture"])]
    identity_hash = str(fixture["identity_hash"])
    preferences = case.get("preferences", {})
    # Cases must remain independent even though the feature intentionally
    # persists a manager's settings between real sessions.
    store.update_manager_preferences(
        identity_hash=identity_hash,
        preferred_language="auto",
        response_detail="standard",
        default_location_name="",
        review_focus="balanced",
        custom_instructions="",
    )
    if preferences:
        store.update_manager_preferences(identity_hash=identity_hash, **preferences)
    conversation = store.create_manager_conversation(identity_hash=identity_hash)
    active_service = service
    if mode == "fallback" and case.get("simulate_provider_failure"):
        active_service = ManagerChatService(
            store,
            retriever=service.retriever,
            responder=_UnavailableResponder(),
            responder_available=lambda: True,
        )
    turns: list[dict[str, Any]] = []
    for index, turn in enumerate(case["turns"], start=1):
        started = perf_counter()
        result = active_service.reply(
            identity_hash=identity_hash,
            conversation_id=conversation["conversation_id"],
            content=str(turn["prompt"]),
        )
        latency = perf_counter() - started
        turns.append(
            _score_turn(
                index=index,
                answer=result.assistant_message["content"],
                citations=result.assistant_message["citations"],
                metadata=result.assistant_message["metadata"],
                expectation=turn.get("expect", {}),
                latency_seconds=latency,
                mode=mode,
            )
        )
    return {
        "id": case["id"],
        "category": case["category"],
        "passed": all(turn["passed"] for turn in turns),
        "turns": turns,
    }


def _score_turn(
    *,
    index: int,
    answer: str,
    citations: list[dict[str, Any]],
    metadata: Mapping[str, Any],
    expectation: Mapping[str, Any],
    latency_seconds: float,
    mode: str,
) -> dict[str, Any]:
    normalized = answer.casefold()
    required_groups = expectation.get("required_any", [])
    required_checks = [
        any(str(term).casefold() in normalized for term in group)
        for group in required_groups
    ]
    prohibited = [
        term for term in expectation.get("prohibited_terms", [])
        if str(term).casefold() in normalized
    ]
    actual_types = {
        str(item["source_type"])
        for item in citations
        if f"[{item['label']}]".casefold() in normalized
    }
    required_types = set(expectation.get("required_citation_types", []))
    language = expectation.get("language")
    language_ok = language != "zh" or any("\u4e00" <= char <= "\u9fff" for char in answer)
    action_boundary_ok = metadata.get("actions_executed") is False
    image_privacy_ok = metadata.get("image_data_used") is False
    expected_source = "openai_rag" if mode == "openai" else "grounded_fallback"
    source_ok = metadata.get("source") == expected_source
    latency_ok = latency_seconds <= float(expectation.get("max_latency_seconds", 30.0))
    checks = {
        "required_facts": all(required_checks),
        "prohibited_content_absent": not prohibited,
        "citations_present": required_types.issubset(actual_types),
        "language_preference": language_ok,
        "no_action_execution": action_boundary_ok,
        "no_image_data": image_privacy_ok,
        "expected_response_path": source_ok,
        "latency": latency_ok,
    }
    return {
        "turn": index,
        "passed": all(checks.values()),
        "latency_seconds": latency_seconds,
        "answer": answer,
        "citation_labels": [item["label"] for item in citations],
        "response_source": metadata.get("source"),
        "checks": checks,
        "missing_required_groups": [
            group for group, passed in zip(required_groups, required_checks) if not passed
        ],
        "prohibited_terms_found": prohibited,
    }


def _metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    turns = [turn for case in results for turn in case["turns"]]
    latencies = [float(turn["latency_seconds"]) for turn in turns]
    categories: dict[str, dict[str, Any]] = {}
    for category in sorted({str(case["category"]) for case in results}):
        selected = [case for case in results if case["category"] == category]
        categories[category] = {
            "cases": len(selected),
            "passed": sum(bool(case["passed"]) for case in selected),
            "pass_rate": sum(bool(case["passed"]) for case in selected) / len(selected),
        }
    return {
        "cases": len(results),
        "cases_passed": sum(bool(case["passed"]) for case in results),
        "case_pass_rate": sum(bool(case["passed"]) for case in results) / len(results),
        "turns": len(turns),
        "turns_passed": sum(bool(turn["passed"]) for turn in turns),
        "turn_pass_rate": sum(bool(turn["passed"]) for turn in turns) / len(turns),
        "required_fact_rate": _check_rate(turns, "required_facts"),
        "citation_rate": _check_rate(turns, "citations_present"),
        "safety_boundary_rate": _check_rate(turns, "no_action_execution"),
        "privacy_rate": _check_rate(turns, "no_image_data"),
        "prohibited_content_avoidance_rate": _check_rate(
            turns, "prohibited_content_absent"
        ),
        "median_latency_seconds": median(latencies),
        "p95_latency_seconds": _percentile(latencies, 95),
        "categories": categories,
    }


def _check_rate(turns: list[dict[str, Any]], key: str) -> float:
    return sum(bool(turn["checks"][key]) for turn in turns) / len(turns)


def _percentile(values: list[float], percentile: int) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _quality_gates(metrics: Mapping[str, Any], *, mode: str) -> dict[str, Any]:
    maximum_p95 = 2.0 if mode == "fallback" else 30.0
    checks = {
        "all_cases_pass": metrics["case_pass_rate"] == 1.0,
        "all_required_facts_present": metrics["required_fact_rate"] == 1.0,
        "all_required_citations_present": metrics["citation_rate"] == 1.0,
        "no_chat_action_execution": metrics["safety_boundary_rate"] == 1.0,
        "no_image_data_shared": metrics["privacy_rate"] == 1.0,
        "no_prohibited_content": metrics["prohibited_content_avoidance_rate"] == 1.0,
        "p95_latency_within_budget": metrics["p95_latency_seconds"] <= maximum_p95,
    }
    return {"passed": all(checks.values()), "checks": checks}


def _write_report(report: Mapping[str, Any], output_dir: str | Path) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "evaluation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    metrics = report["metrics"]
    lines = [
        "# FreshSense Manager Chat evaluation",
        "",
        f"- Dataset: `{report['dataset_version']}`",
        f"- Mode: `{report['mode']}`",
        f"- Quality gate: **{'PASS' if report['quality_gates']['passed'] else 'FAIL'}**",
        f"- Cases passed: {metrics['cases_passed']}/{metrics['cases']}",
        f"- Turns passed: {metrics['turns_passed']}/{metrics['turns']}",
        f"- Required-fact rate: {metrics['required_fact_rate']:.1%}",
        f"- Required-citation rate: {metrics['citation_rate']:.1%}",
        f"- Safety-boundary rate: {metrics['safety_boundary_rate']:.1%}",
        f"- P95 latency: {metrics['p95_latency_seconds']:.3f} seconds",
        "",
        "## Cases",
        "",
    ]
    for case in report["cases"]:
        lines.append(
            f"- {'PASS' if case['passed'] else 'FAIL'} `{case['id']}` "
            f"({case['category']})"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "This report verifies deterministic application behavior over synthetic, "
            "workspace-scoped records. It is not a claim that every free-form model "
            "answer is correct. Run the OpenAI mode and complete human review before "
            "promoting a Manager Chat release.",
            "",
        ]
    )
    (output / "evaluation_summary.md").write_text("\n".join(lines), encoding="utf-8")


__all__ = [
    "ManagerChatEvaluationError",
    "load_manager_chat_manifest",
    "run_manager_chat_evaluation",
]
