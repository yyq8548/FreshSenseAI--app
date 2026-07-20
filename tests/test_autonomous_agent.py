import pytest

from agent.autonomous import (
    ActionPolicyGuard,
    AutonomousInspectionAgent,
    ShadowAgentError,
)
from saas.store import InspectionNotFoundError, SaaSStore


def _analysis(
    *,
    decision: str = "accept_prediction",
    freshness: str | None = "fresh",
) -> dict[str, object]:
    prediction = (
        {
            "class_name": f"{freshness}banana",
            "display_name": f"{freshness.title()} Banana",
            "fruit": "banana",
            "freshness": freshness,
            "confidence": 0.92,
        }
        if freshness is not None
        else None
    )
    return {
        "decision": decision,
        "status": "completed",
        "prediction": prediction,
        "reasoning": {"risk_level": "high" if freshness == "rotten" else "low"},
        "warnings": [],
        "recommendation": "A staff member must inspect the physical fruit.",
        "safety_notice": "Decision support only.",
    }


def _inspection(
    store: SaaSStore,
    *,
    identity: str = "manager-a",
    decision: str = "accept_prediction",
    freshness: str | None = "fresh",
) -> dict[str, object]:
    return store.record_inspection(
        identity_hash=identity,
        location_name="Produce receiving",
        batch_reference="PO-42",
        operator_note="Agent runtime test",
        analysis=_analysis(decision=decision, freshness=freshness),
        model_version="0.7.0",
    )


def test_shadow_agent_persists_tool_trace_and_never_executes_batch_hold(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    inspection = _inspection(store, freshness="rotten")

    run = AutonomousInspectionAgent(store).run(
        identity_hash="manager-a",
        inspection_id=str(inspection["inspection_id"]),
    )

    assert run["status"] == "completed"
    assert run["mode"] == "shadow"
    assert run["steps_completed"] == 5
    assert [step["tool_name"] for step in run["steps"][:2]] == [
        "get_inspection_context",
        "list_recent_inspections",
    ]
    proposal = run["action_proposals"][0]
    assert proposal["action_type"] == "hold_batch"
    assert proposal["policy_decision"] == "approval_required"
    assert proposal["execution_status"] == "shadow_only"
    assert "workflow status: shadow_only" in run["final_summary"]


def test_shadow_agent_routes_uncertain_result_to_human_review(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    inspection = _inspection(
        store,
        decision="uncertain_input",
        freshness=None,
    )

    run = AutonomousInspectionAgent(store).run(
        identity_hash="manager-a",
        inspection_id=str(inspection["inspection_id"]),
    )

    proposal = run["action_proposals"][0]
    assert proposal["action_type"] == "create_review_task"
    assert proposal["policy_decision"] == "automatic"
    assert proposal["execution_status"] == "shadow_only"


def test_shadow_agent_uses_reviewed_history_to_escalate_fresh_result(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    earlier = _inspection(store, freshness="fresh")
    store.review_inspection(
        identity_hash="manager-a",
        inspection_id=str(earlier["inspection_id"]),
        review_status="corrected",
        reviewed_outcome="rotten",
        note="Staff found visible spoilage.",
    )
    current = _inspection(store, freshness="fresh")

    run = AutonomousInspectionAgent(store).run(
        identity_hash="manager-a",
        inspection_id=str(current["inspection_id"]),
    )

    proposal = run["action_proposals"][0]
    assert proposal["action_type"] == "create_review_task"
    assert proposal["payload"]["matching_corrections"] == 1


def test_supervised_agent_creates_review_task_notification_and_memory(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    inspection = _inspection(
        store,
        decision="uncertain_input",
        freshness=None,
    )

    run = AutonomousInspectionAgent(store).run(
        identity_hash="manager-a",
        inspection_id=str(inspection["inspection_id"]),
        mode="supervised",
    )

    assert run["mode"] == "supervised"
    assert run["action_proposals"][0]["execution_status"] == "executed"
    assert store.list_workflow_tasks("manager-a", status="open")[0][
        "task_type"
    ] == "create_review_task"
    assert len(store.list_notifications("manager-a")) == 1

    store.review_inspection(
        identity_hash="manager-a",
        inspection_id=str(inspection["inspection_id"]),
        review_status="confirmed",
        reviewed_outcome="uncertain",
        note="Staff could not verify the fruit from this photo.",
    )

    assert store.list_workflow_tasks("manager-a", status="open") == []
    memory = store.list_agent_memory("manager-a")
    assert memory[0]["reviewed_outcome"] == "uncertain"


def test_supervised_rotten_result_waits_for_manager_approval(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    inspection = _inspection(store, freshness="rotten")

    run = AutonomousInspectionAgent(store).run(
        identity_hash="manager-a",
        inspection_id=str(inspection["inspection_id"]),
        mode="supervised",
    )

    proposal = run["action_proposals"][0]
    assert proposal["execution_status"] == "awaiting_approval"
    approval = store.list_approvals("manager-a", status="pending")[0]
    resolved = store.resolve_approval(
        identity_hash="manager-a",
        approval_id=approval["approval_id"],
        decision="approved",
        note="Manager inspected the physical batch.",
    )
    assert resolved["status"] == "approved"
    assert store.list_workflow_tasks("manager-a", status="open")[0][
        "task_type"
    ] == "approved_hold_batch"


def test_agent_runs_are_workspace_scoped(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    inspection = _inspection(store, identity="manager-a")

    with pytest.raises(InspectionNotFoundError):
        AutonomousInspectionAgent(store).run(
            identity_hash="manager-b",
            inspection_id=str(inspection["inspection_id"]),
        )


def test_step_limit_fails_closed_and_preserves_the_audit_run(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    inspection = _inspection(store)
    agent = AutonomousInspectionAgent(store, max_steps=1)

    with pytest.raises(ShadowAgentError, match="step limit"):
        agent.run(
            identity_hash="manager-a",
            inspection_id=str(inspection["inspection_id"]),
        )

    runs = store.list_agent_runs("manager-a")
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert runs[0]["error_code"] == "ShadowAgentError"
    assert runs[0]["steps_completed"] == 1
    assert runs[0]["action_proposals"] == []


def test_policy_guard_prohibits_food_safety_and_disposal_actions():
    policy = ActionPolicyGuard()

    assert policy.evaluate("declare_food_safe").decision == "prohibited"
    assert policy.evaluate("discard_inventory").decision == "prohibited"
    assert policy.evaluate("hold_batch").decision == "approval_required"
