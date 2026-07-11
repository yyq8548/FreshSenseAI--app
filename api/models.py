"""Typed public response contracts for the FreshSense REST API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    service: Literal["FreshSense AI"] = "FreshSense AI"
    api_version: Literal["v1"] = "v1"
    status: Literal["ok"] = "ok"
    model_loaded: bool
    semantic_retrieval_ready: bool
    retrieval_mode: Literal["semantic", "keyword_fallback"]
    semantic_model: str | None = None
    supported_fruits: list[str]
    image_retention: Literal[False] = False
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
    recommendation: str
    safety_notice: str
    privacy: PrivacyResponse = Field(default_factory=PrivacyResponse)


class ErrorDetail(ApiModel):
    code: str
    message: str


class ErrorResponse(ApiModel):
    error: ErrorDetail
