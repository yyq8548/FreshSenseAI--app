"""Typed contracts for bounded FreshSense agent runs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


AgentActionType = Literal[
    "complete_without_action",
    "request_retake",
    "create_review_task",
    "notify_manager",
    "hold_batch",
    "discard_inventory",
    "declare_food_safe",
]
AgentPolicyDecision = Literal["automatic", "approval_required", "prohibited"]


class AgentContract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolIntent(AgentContract):
    kind: Literal["tool"] = "tool"
    tool_name: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)
    rationale: str = Field(min_length=1, max_length=1000)


class FinishIntent(AgentContract):
    kind: Literal["finish"] = "finish"
    action_type: AgentActionType
    rationale: str = Field(min_length=1, max_length=2000)
    payload: dict[str, Any] = Field(default_factory=dict)


AgentIntent = ToolIntent | FinishIntent


class PolicyDecision(AgentContract):
    action_type: AgentActionType
    decision: AgentPolicyDecision
    reason: str


class ToolExecution(AgentContract):
    tool_name: str
    output: dict[str, Any]


__all__ = [
    "AgentActionType",
    "AgentIntent",
    "AgentPolicyDecision",
    "FinishIntent",
    "PolicyDecision",
    "ToolExecution",
    "ToolIntent",
]
