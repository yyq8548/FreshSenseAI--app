"""Typed public response contracts for the FreshSense REST API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    service: Literal["FreshSense AI"] = "FreshSense AI"
    api_version: Literal["v1"] = "v1"
    status: Literal["ok", "starting", "failed"] = "ok"
    model_loaded: bool
    semantic_retrieval_ready: bool
    retrieval_mode: Literal["semantic", "keyword_fallback"]
    semantic_model: str | None = None
    supported_fruits: list[str]
    image_retention: Literal[False] = False
    database_backend: Literal["sqlite", "postgresql"]
    authentication_required: bool
    rate_limit_per_minute: int = Field(gt=0)


class MetricsResponse(ApiModel):
    service: Literal["FreshSense AI"] = "FreshSense AI"
    api_version: Literal["v1"] = "v1"
    uptime_seconds: float = Field(ge=0.0)
    request_count: int = Field(ge=0)
    active_requests: int = Field(ge=0)
    response_status_counts: dict[str, int]
    analysis_count: int = Field(ge=0)
    analysis_failures: int = Field(ge=0)
    average_analysis_seconds: float | None = Field(default=None, ge=0.0)
    last_analysis_seconds: float | None = Field(default=None, ge=0.0)


class PredictionResponse(ApiModel):
    class_name: str
    display_name: str
    fruit: str
    freshness: Literal["fresh", "rotten"]
    confidence: float = Field(ge=0.0, le=1.0)


class RetrievalDocumentResponse(ApiModel):
    id: str
    fruit: str
    topic: str
    text: str
    score: float
    method: str


class RetrievalResponse(ApiModel):
    query: str
    method: str
    model: str | None = None
    documents: list[RetrievalDocumentResponse]


class WarningResponse(ApiModel):
    level: str
    message: str


class ReasoningResponse(ApiModel):
    explanation: str
    shelf_life_estimate: str
    storage_advice: str
    risk_level: str
    source: str


class ImageQualityResponse(ApiModel):
    brightness: float
    edge_strength: float
    is_dark: bool
    is_blurry: bool
    is_overexposed: bool


class SceneAnalysisResponse(ApiModel):
    image_width: int
    image_height: int
    foreground_ratio: float
    fruit_is_too_small: bool
    likely_empty_scene: bool
    needs_crop_or_closer_photo: bool


class PrivacyResponse(ApiModel):
    image_retained: Literal[False] = False
    filename_retained: Literal[False] = False


class ExplainabilityResponse(ApiModel):
    method: Literal["grad_cam"] = "grad_cam"
    target_class: str
    layer: str
    peak_activation: float = Field(ge=0.0, le=1.0)
    active_fraction: float = Field(ge=0.0, le=1.0)
    overlay_png_base64: str | None = None
    disclaimer: str


class AnalyzeResponse(ApiModel):
    api_version: Literal["v1"] = "v1"
    decision: str
    status: str
    prediction: PredictionResponse | None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    image_quality: ImageQualityResponse | None
    scene_analysis: SceneAnalysisResponse | None
    retrieval: RetrievalResponse | None
    warnings: list[WarningResponse]
    reasoning: ReasoningResponse | None
    explainability: ExplainabilityResponse | None = None
    recommendation: str
    safety_notice: str
    privacy: PrivacyResponse = Field(default_factory=PrivacyResponse)


class ErrorDetail(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    error: ErrorDetail


class WorkspaceLocationResponse(ApiModel):
    location_id: str
    name: str
    created_at_utc: str


class WorkspaceMemberResponse(ApiModel):
    member_id: str
    role: Literal["manager", "inspector", "reviewer"]
    email: str | None
    display_name: str | None
    created_at_utc: str
    last_seen_at_utc: str


class WorkspaceResponse(ApiModel):
    workspace_id: str
    display_name: str
    created_at_utc: str
    plan: Literal["pilot"] = "pilot"
    image_retention: Literal[False] = False
    locations: list[WorkspaceLocationResponse]
    current_role: Literal["manager", "inspector", "reviewer"]
    members: list[WorkspaceMemberResponse]


class AuthenticatedUserResponse(ApiModel):
    account_id: str
    display_name: str | None
    email: str | None
    authentication_scheme: Literal["local", "api_key", "entra"]
    scopes: list[str]
    workspace_id: str
    workspace_role: Literal["manager", "inspector", "reviewer"]


class WorkspaceInvitationCreateRequest(ApiModel):
    email: str = Field(min_length=3, max_length=254)
    role: Literal["inspector", "reviewer"]
    expires_days: int = Field(default=7, ge=1, le=30)


class WorkspaceInvitationResponse(ApiModel):
    invitation_id: str
    email: str
    role: Literal["inspector", "reviewer"]
    expires_at_utc: str
    invitation_token: str


class WorkspaceInvitationAcceptRequest(ApiModel):
    invitation_token: str = Field(min_length=32, max_length=512)


class InspectionResponse(ApiModel):
    inspection_id: str
    created_at_utc: str
    location_name: str
    batch_reference: str
    operator_note: str
    decision: str
    analysis_status: str
    predicted_class: str | None
    predicted_display_name: str | None
    fruit: str | None
    predicted_freshness: Literal["fresh", "rotten"] | None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    risk_level: str | None
    recommendation: str
    safety_notice: str
    warnings: list[WarningResponse]
    model_version: str
    review_status: Literal["pending", "confirmed", "corrected", "dismissed"]
    reviewed_outcome: Literal["fresh", "rotten", "unsupported", "uncertain"] | None
    review_note: str
    reviewed_at_utc: str | None
    image_retained: Literal[False] = False


class InspectionAnalyzeResponse(ApiModel):
    inspection: InspectionResponse
    analysis: AnalyzeResponse
    workflow_status: Literal["completed", "failed"] = "completed"
    agent_run_id: str | None = None


class InspectionListResponse(ApiModel):
    inspections: list[InspectionResponse]
    count: int = Field(ge=0)


class InspectionReviewRequest(ApiModel):
    review_status: Literal["confirmed", "corrected", "dismissed"]
    reviewed_outcome: Literal["fresh", "rotten", "unsupported", "uncertain"] | None = None
    note: str = Field(default="", max_length=1000)


class DashboardResponse(ApiModel):
    total_inspections: int = Field(ge=0)
    last_7_days: int = Field(ge=0)
    pending_reviews: int = Field(ge=0)
    reviewed_inspections: int = Field(ge=0)
    review_completion_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    false_fresh_reviews: int = Field(ge=0)
    review_status_counts: dict[str, int]
    fruit_counts: dict[str, int]
    decision_counts: dict[str, int]


class AgentRunCreateRequest(ApiModel):
    inspection_id: str = Field(min_length=1, max_length=64)


class AgentStepResponse(ApiModel):
    step_id: str
    run_id: str
    step_index: int = Field(ge=1, le=20)
    step_kind: Literal["tool", "finish"]
    tool_name: str | None
    rationale: str
    input: dict[str, Any]
    output: dict[str, Any]
    status: Literal["completed", "failed"]
    created_at_utc: str


class AgentActionProposalResponse(ApiModel):
    proposal_id: str
    run_id: str
    inspection_id: str
    action_type: Literal[
        "complete_without_action",
        "request_retake",
        "create_review_task",
        "notify_manager",
        "hold_batch",
        "discard_inventory",
        "declare_food_safe",
    ]
    policy_decision: Literal["automatic", "approval_required", "prohibited"]
    execution_status: Literal[
        "pending",
        "shadow_only",
        "executed",
        "awaiting_approval",
        "blocked",
        "failed",
    ]
    rationale: str
    payload: dict[str, Any]
    created_at_utc: str
    resolved_at_utc: str | None


class AgentRunResponse(ApiModel):
    run_id: str
    inspection_id: str
    mode: Literal["shadow", "supervised"]
    objective: str
    planner_version: str
    status: Literal["running", "completed", "failed", "cancelled"]
    max_steps: int = Field(ge=1, le=20)
    steps_completed: int = Field(ge=0, le=20)
    final_summary: str
    error_code: str | None
    created_at_utc: str
    completed_at_utc: str | None
    steps: list[AgentStepResponse]
    action_proposals: list[AgentActionProposalResponse]


class AgentRunListResponse(ApiModel):
    runs: list[AgentRunResponse]
    count: int = Field(ge=0)


class WorkflowTaskResponse(ApiModel):
    task_id: str
    inspection_id: str
    run_id: str
    task_type: str
    status: Literal["open", "completed", "cancelled"]
    priority: Literal["normal", "high", "urgent"]
    title: str
    instructions: str
    assigned_role: Literal["manager", "inspector", "reviewer"]
    created_at_utc: str
    completed_at_utc: str | None


class WorkflowTaskListResponse(ApiModel):
    tasks: list[WorkflowTaskResponse]
    count: int = Field(ge=0)


class NotificationResponse(ApiModel):
    notification_id: str
    recipient_role: Literal["manager", "inspector", "reviewer", "all"]
    kind: str
    title: str
    message: str
    related_type: str
    related_id: str
    created_at_utc: str
    read_at_utc: str | None


class NotificationListResponse(ApiModel):
    notifications: list[NotificationResponse]
    unread_count: int = Field(ge=0)


class ApprovalResponse(ApiModel):
    approval_id: str
    inspection_id: str
    run_id: str
    action_type: Literal["hold_batch"]
    status: Literal["pending", "approved", "rejected"]
    rationale: str
    payload: dict[str, Any]
    requested_at_utc: str
    resolved_at_utc: str | None
    resolution_note: str


class ApprovalListResponse(ApiModel):
    approvals: list[ApprovalResponse]
    count: int = Field(ge=0)


class ApprovalResolveRequest(ApiModel):
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=1000)


class AgentMemoryResponse(ApiModel):
    memory_id: str
    inspection_id: str
    memory_kind: Literal["human_review"]
    fruit: str | None
    location_name: str
    batch_reference: str
    predicted_outcome: str | None
    reviewed_outcome: str | None
    content: dict[str, Any]
    created_at_utc: str


class AgentMemoryListResponse(ApiModel):
    memories: list[AgentMemoryResponse]
    count: int = Field(ge=0)


class DailyQualityReportResponse(ApiModel):
    report_date: str
    total_inspections: int = Field(ge=0)
    rotten_flags: int = Field(ge=0)
    uncertain_or_retake: int = Field(ge=0)
    reviewed: int = Field(ge=0)
    corrections: int = Field(ge=0)
    open_tasks: int = Field(ge=0)
    pending_approvals: int = Field(ge=0)
    fruit_counts: dict[str, int]
    summary: str
    generated_at_utc: str


class ManagerPreferenceResponse(ApiModel):
    preferred_language: Literal["auto", "en", "zh"]
    response_detail: Literal["concise", "standard", "detailed"]
    default_location_name: str
    review_focus: Literal["balanced", "freshness_risk", "operations"]
    custom_instructions: str
    updated_at_utc: str


class ManagerPreferenceUpdateRequest(ApiModel):
    preferred_language: Literal["auto", "en", "zh"] | None = None
    response_detail: Literal["concise", "standard", "detailed"] | None = None
    default_location_name: str | None = Field(default=None, max_length=80)
    review_focus: Literal["balanced", "freshness_risk", "operations"] | None = None
    custom_instructions: str | None = Field(default=None, max_length=600)


class ManagerChatCitationResponse(ApiModel):
    source_type: Literal["inspection", "agent_run", "knowledge"]
    source_id: str
    label: str


class ManagerChatMessageResponse(ApiModel):
    message_id: str
    conversation_id: str
    role: Literal["user", "assistant"]
    content: str
    citations: list[ManagerChatCitationResponse]
    metadata: dict[str, Any]
    created_at_utc: str


class ManagerConversationSummaryResponse(ApiModel):
    conversation_id: str
    title: str
    status: Literal["active", "archived"]
    created_at_utc: str
    updated_at_utc: str
    message_count: int = Field(ge=0)
    last_message: str | None


class ManagerConversationResponse(ApiModel):
    conversation_id: str
    title: str
    status: Literal["active", "archived"]
    created_at_utc: str
    updated_at_utc: str
    messages: list[ManagerChatMessageResponse]


class ManagerConversationListResponse(ApiModel):
    conversations: list[ManagerConversationSummaryResponse]
    count: int = Field(ge=0)


class ManagerConversationCreateRequest(ApiModel):
    title: str = Field(default="New conversation", min_length=1, max_length=120)


class ManagerChatMessageCreateRequest(ApiModel):
    content: str = Field(min_length=1, max_length=4000)


class ManagerChatReplyResponse(ApiModel):
    conversation: ManagerConversationResponse
    assistant_message: ManagerChatMessageResponse
