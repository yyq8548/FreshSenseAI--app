"""Bounded, auditable shadow and supervised FreshSense workflow agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent.contracts import (
    AgentActionType,
    AgentIntent,
    AgentPolicyDecision,
    FinishIntent,
    PolicyDecision,
    ToolIntent,
)
from agent.tool_registry import AgentTool, AgentToolContext, AgentToolRegistry
from utils.config import KNOWLEDGE_BASE_PATH


class ShadowAgentError(RuntimeError):
    """Raised when a bounded shadow-agent run cannot finish safely."""


class _ToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GetInspectionInput(_ToolInput):
    inspection_id: str = Field(min_length=1, max_length=64)


class ListRecentInspectionsInput(_ToolInput):
    limit: int = Field(default=20, ge=1, le=50)


class RetrieveKnowledgeInput(_ToolInput):
    fruit: str | None = Field(default=None, max_length=80)
    decision: str = Field(default="", max_length=80)


class ListMemoryInput(_ToolInput):
    fruit: str | None = Field(default=None, max_length=80)
    limit: int = Field(default=20, ge=1, le=50)


class ActionPolicyGuard:
    """Keep operational authority separate from planning."""

    _POLICIES: dict[AgentActionType, tuple[AgentPolicyDecision, str]] = {
        "complete_without_action": (
            "automatic",
            "Completing a shadow assessment does not change store operations.",
        ),
        "request_retake": (
            "automatic",
            "Requesting a clearer image is a reversible workflow action.",
        ),
        "create_review_task": (
            "automatic",
            "Creating an internal review task preserves human decision authority.",
        ),
        "notify_manager": (
            "automatic",
            "An in-product manager notification is reversible and auditable.",
        ),
        "hold_batch": (
            "approval_required",
            "Changing batch availability requires a manager decision.",
        ),
        "discard_inventory": (
            "prohibited",
            "FreshSense must never discard inventory autonomously.",
        ),
        "declare_food_safe": (
            "prohibited",
            "An image model cannot establish that food is safe to sell or consume.",
        ),
    }

    def evaluate(self, action_type: AgentActionType) -> PolicyDecision:
        decision, reason = self._POLICIES[action_type]
        return PolicyDecision(
            action_type=action_type,
            decision=decision,
            reason=reason,
        )


class ShadowInspectionPlanner:
    """Select the next typed tool or finish action from current observations."""

    version = "supervised-rules-v2"

    def next_intent(
        self,
        *,
        inspection_id: str,
        observations: dict[str, Any],
    ) -> AgentIntent:
        if "inspection" not in observations:
            return ToolIntent(
                tool_name="get_inspection_context",
                arguments={"inspection_id": inspection_id},
                rationale="Load the workspace-scoped inspection before planning follow-up.",
            )
        if "recent_inspections" not in observations:
            return ToolIntent(
                tool_name="list_recent_inspections",
                arguments={"limit": 20},
                rationale="Compare this result with recent activity in the same workspace.",
            )
        if "knowledge" not in observations:
            inspection = observations["inspection"]
            return ToolIntent(
                tool_name="retrieve_operating_knowledge",
                arguments={
                    "fruit": inspection.get("fruit"),
                    "decision": inspection.get("decision") or "",
                },
                rationale="Retrieve reviewed fruit guidance and store operating rules.",
            )
        if "memory" not in observations:
            inspection = observations["inspection"]
            return ToolIntent(
                tool_name="list_review_memory",
                arguments={"fruit": inspection.get("fruit"), "limit": 20},
                rationale="Check durable human-review outcomes before choosing an action.",
            )
        return self._finish_intent(
            inspection=observations["inspection"],
            recent=observations["recent_inspections"],
            knowledge=observations["knowledge"],
            memory=observations["memory"],
        )

    def _finish_intent(
        self,
        *,
        inspection: dict[str, Any],
        recent: dict[str, Any],
        knowledge: dict[str, Any],
        memory: dict[str, Any],
    ) -> FinishIntent:
        decision = str(inspection.get("decision") or "")
        predicted_freshness = inspection.get("predicted_freshness")
        # Recent rows and durable review memory can describe the same correction.
        # Use the larger count instead of double-counting one human decision.
        matching_corrections = max(
            int(recent.get("matching_corrections", 0)),
            int(memory.get("matching_corrections", 0)),
        )

        if decision == "retake_photo":
            action_type: AgentActionType = "request_retake"
            rationale = "The inspection stopped because the image quality was not usable."
        elif decision in {"unsupported_input", "uncertain_input"}:
            action_type = "create_review_task"
            rationale = "The model withheld a supported freshness result and needs human review."
        elif predicted_freshness == "rotten":
            action_type = "hold_batch"
            rationale = (
                "The model found visible rotten-fruit patterns. A manager must inspect the "
                "physical batch before changing its availability."
            )
        elif predicted_freshness == "fresh" and matching_corrections > 0:
            action_type = "create_review_task"
            rationale = (
                "Recent corrected inspections match this fruit or location, so a human "
                "review is appropriate before relying on the fresh label."
            )
        else:
            action_type = "complete_without_action"
            rationale = (
                "No additional workflow action is justified by this result and the recent "
                "workspace history."
            )

        return FinishIntent(
            action_type=action_type,
            rationale=rationale,
            payload={
                "inspection_id": inspection.get("inspection_id"),
                "location_name": inspection.get("location_name"),
                "fruit": inspection.get("fruit"),
                "batch_reference": inspection.get("batch_reference"),
                "matching_recent_inspections": int(recent.get("matching_count", 0)),
                "matching_corrections": matching_corrections,
                "knowledge_ids": [
                    item.get("id") for item in knowledge.get("documents", [])
                ],
                "operating_rules": knowledge.get("operating_rules", []),
            },
        )


class AutonomousInspectionAgent:
    """Execute a durable observe-plan-act loop under explicit policy controls."""

    def __init__(
        self,
        store: Any,
        *,
        planner: ShadowInspectionPlanner | None = None,
        policy: ActionPolicyGuard | None = None,
        max_steps: int = 7,
        knowledge_base_path: str = KNOWLEDGE_BASE_PATH,
    ) -> None:
        if not 1 <= max_steps <= 20:
            raise ValueError("max_steps must be between 1 and 20.")
        self.store = store
        self.planner = planner or ShadowInspectionPlanner()
        self.policy = policy or ActionPolicyGuard()
        self.max_steps = max_steps
        self.knowledge_documents = self._load_knowledge(knowledge_base_path)
        self.tools = AgentToolRegistry()
        self.tools.register(
            AgentTool(
                name="get_inspection_context",
                description="Load one inspection from the authenticated workspace.",
                input_model=GetInspectionInput,
                handler=self._get_inspection,
            )
        )
        self.tools.register(
            AgentTool(
                name="list_recent_inspections",
                description="Load recent workspace inspections for trend comparison.",
                input_model=ListRecentInspectionsInput,
                handler=self._list_recent,
            )
        )
        self.tools.register(
            AgentTool(
                name="retrieve_operating_knowledge",
                description="Retrieve reviewed fruit guidance and bounded store rules.",
                input_model=RetrieveKnowledgeInput,
                handler=self._retrieve_knowledge,
            )
        )
        self.tools.register(
            AgentTool(
                name="list_review_memory",
                description="Load durable human-review outcomes from this workspace.",
                input_model=ListMemoryInput,
                handler=self._list_memory,
            )
        )

    def run(
        self,
        *,
        identity_hash: str,
        inspection_id: str,
        mode: str = "shadow",
    ) -> dict[str, Any]:
        if mode not in {"shadow", "supervised"}:
            raise ValueError("mode must be shadow or supervised.")
        objective = (
            "Review one completed fruit inspection, compare recent workspace history, and "
            "propose the safest next workflow action without executing it."
        )
        run = self.store.create_agent_run(
            identity_hash=identity_hash,
            inspection_id=inspection_id,
            objective=objective,
            planner_version=self.planner.version,
            max_steps=self.max_steps,
            mode=mode,
        )
        run_id = run["run_id"]
        observations: dict[str, Any] = {}
        context = AgentToolContext(
            identity_hash=identity_hash,
            inspection_id=inspection_id,
            store=self.store,
        )
        try:
            for step_index in range(1, self.max_steps + 1):
                intent = self.planner.next_intent(
                    inspection_id=inspection_id,
                    observations=observations,
                )
                if isinstance(intent, ToolIntent):
                    execution = self.tools.execute(
                        intent.tool_name,
                        intent.arguments,
                        context,
                    )
                    observation_key = {
                        "get_inspection_context": "inspection",
                        "list_recent_inspections": "recent_inspections",
                        "retrieve_operating_knowledge": "knowledge",
                        "list_review_memory": "memory",
                    }[intent.tool_name]
                    observations[observation_key] = execution.output
                    self.store.append_agent_step(
                        identity_hash=identity_hash,
                        run_id=run_id,
                        step_index=step_index,
                        step_kind="tool",
                        tool_name=intent.tool_name,
                        rationale=intent.rationale,
                        input_data=intent.arguments,
                        output_data=execution.output,
                        status="completed",
                    )
                    continue

                policy = self.policy.evaluate(intent.action_type)
                proposal = self.store.create_action_proposal(
                    identity_hash=identity_hash,
                    run_id=run_id,
                    inspection_id=inspection_id,
                    action_type=intent.action_type,
                    policy_decision=policy.decision,
                    rationale=intent.rationale,
                    payload=intent.payload,
                    execution_status="shadow_only" if mode == "shadow" else "pending",
                )
                action_result: dict[str, Any] = {"status": "shadow_only"}
                if mode == "supervised":
                    if policy.decision == "automatic":
                        action_result = self.store.execute_agent_action(
                            identity_hash=identity_hash,
                            run_id=run_id,
                            proposal_id=proposal["proposal_id"],
                            inspection_id=inspection_id,
                            action_type=intent.action_type,
                            rationale=intent.rationale,
                        )
                    elif policy.decision == "approval_required":
                        approval = self.store.request_agent_approval(
                            identity_hash=identity_hash,
                            run_id=run_id,
                            proposal_id=proposal["proposal_id"],
                            inspection_id=inspection_id,
                            action_type=intent.action_type,
                            rationale=intent.rationale,
                            payload=intent.payload,
                        )
                        action_result = {
                            "status": "awaiting_approval",
                            "approval_id": approval["approval_id"],
                        }
                    else:
                        self.store.set_action_proposal_status(
                            identity_hash=identity_hash,
                            proposal_id=proposal["proposal_id"],
                            execution_status="blocked",
                        )
                        action_result = {"status": "blocked"}
                summary = (
                    f"{mode.title()} agent proposed {intent.action_type}; policy decision: "
                    f"{policy.decision}; workflow status: {action_result['status']}."
                )
                self.store.append_agent_step(
                    identity_hash=identity_hash,
                    run_id=run_id,
                    step_index=step_index,
                    step_kind="finish",
                    tool_name=None,
                    rationale=intent.rationale,
                    input_data=intent.payload,
                    output_data={
                        "proposal_id": proposal["proposal_id"],
                        "policy_decision": policy.decision,
                        "policy_reason": policy.reason,
                        "action_result": action_result,
                    },
                    status="completed",
                )
                if mode == "supervised":
                    inspection = observations["inspection"]
                    label = inspection.get("predicted_display_name") or "withheld result"
                    self.store.notify_analysis_completed(
                        identity_hash=identity_hash,
                        inspection_id=inspection_id,
                        message=(
                            f"{inspection.get('location_name')}: analysis completed as "
                            f"{label}. Workflow status: {action_result['status']}."
                        ),
                    )
                self.store.complete_agent_run(
                    identity_hash=identity_hash,
                    run_id=run_id,
                    final_summary=summary,
                )
                return self.store.agent_run(identity_hash, run_id)

            raise ShadowAgentError("The workflow agent exceeded its bounded step limit.")
        except Exception as exc:
            self.store.fail_agent_run(
                identity_hash=identity_hash,
                run_id=run_id,
                error_code=type(exc).__name__,
            )
            raise

    @staticmethod
    def _get_inspection(
        value: BaseModel,
        context: AgentToolContext,
    ) -> dict[str, Any]:
        request = GetInspectionInput.model_validate(value)
        return context.store.inspection(context.identity_hash, request.inspection_id)

    @staticmethod
    def _list_recent(
        value: BaseModel,
        context: AgentToolContext,
    ) -> dict[str, Any]:
        request = ListRecentInspectionsInput.model_validate(value)
        current = context.store.inspection(context.identity_hash, context.inspection_id)
        rows = context.store.list_inspections(
            context.identity_hash,
            limit=request.limit,
        )
        matches = [
            row
            for row in rows
            if row["inspection_id"] != context.inspection_id
            and (
                (
                    current.get("batch_reference")
                    and row.get("batch_reference")
                    == current.get("batch_reference")
                )
                or (current.get("fruit") and row.get("fruit") == current.get("fruit"))
                or row.get("location_name") == current.get("location_name")
            )
        ]
        return {
            "matching_count": len(matches),
            "matching_corrections": sum(
                row.get("review_status") == "corrected" for row in matches
            ),
            "items": [
                {
                    "inspection_id": row.get("inspection_id"),
                    "created_at_utc": row.get("created_at_utc"),
                    "fruit": row.get("fruit"),
                    "decision": row.get("decision"),
                    "predicted_freshness": row.get("predicted_freshness"),
                    "review_status": row.get("review_status"),
                    "reviewed_outcome": row.get("reviewed_outcome"),
                }
                for row in matches[:10]
            ],
            "same_batch_count": sum(
                bool(current.get("batch_reference"))
                and row.get("batch_reference") == current.get("batch_reference")
                for row in rows
                if row["inspection_id"] != context.inspection_id
            ),
            "same_location_count": sum(
                row.get("location_name") == current.get("location_name")
                for row in rows
                if row["inspection_id"] != context.inspection_id
            ),
            "same_fruit_count": sum(
                bool(current.get("fruit")) and row.get("fruit") == current.get("fruit")
                for row in rows
                if row["inspection_id"] != context.inspection_id
            ),
        }

    def _retrieve_knowledge(
        self,
        value: BaseModel,
        _context: AgentToolContext,
    ) -> dict[str, Any]:
        request = RetrieveKnowledgeInput.model_validate(value)
        eligible = [
            item
            for item in self.knowledge_documents
            if item.get("fruit") in {request.fruit, "general"}
        ]
        query_terms = {request.fruit or "", request.decision, "safety", "spoilage"}
        scored = sorted(
            eligible,
            key=lambda item: sum(
                term.casefold() in str(item.get("text", "")).casefold()
                for term in query_terms
                if term
            ),
            reverse=True,
        )
        return {
            "documents": scored[:4],
            "operating_rules": [
                "Do not declare food safe from an image.",
                "Require human review for withheld or visibly rotten results.",
                "A manager must approve any batch hold.",
                "Never discard inventory automatically.",
            ],
        }

    @staticmethod
    def _list_memory(
        value: BaseModel,
        context: AgentToolContext,
    ) -> dict[str, Any]:
        request = ListMemoryInput.model_validate(value)
        items = context.store.list_agent_memory(
            context.identity_hash,
            fruit=request.fruit,
            limit=request.limit,
        )
        return {
            "count": len(items),
            "matching_corrections": sum(
                item.get("predicted_outcome") != item.get("reviewed_outcome")
                for item in items
                if item.get("reviewed_outcome") is not None
            ),
            "items": items,
        }

    @staticmethod
    def _load_knowledge(path: str) -> list[dict[str, Any]]:
        try:
            value = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return []
        return value if isinstance(value, list) else []


__all__ = [
    "ActionPolicyGuard",
    "AutonomousInspectionAgent",
    "ShadowAgentError",
    "ShadowInspectionPlanner",
]
