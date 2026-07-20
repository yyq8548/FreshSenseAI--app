"""Typed public response contracts for the FreshSense REST API."""

from __future__ import annotations

from typing import Literal

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
