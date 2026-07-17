"""Convert internal agent state into the stable public API contract."""

from __future__ import annotations

from agent.state import AgentState
from api.models import (
    AnalyzeResponse,
    ExplainabilityResponse,
    ImageQualityResponse,
    PredictionResponse,
    ReasoningResponse,
    RetrievalDocumentResponse,
    RetrievalResponse,
    SceneAnalysisResponse,
    WarningResponse,
)
from tools.explainability import gradcam_overlay_base64
from utils.config import SAFETY_NOTICE
from utils.fruit_catalog import FruitCatalog


def serialize_agent_state(
    state: AgentState,
    catalog: FruitCatalog,
    *,
    include_explanation_overlay: bool = False,
) -> AnalyzeResponse:
    """Create a response without exposing withheld or internal model details."""
    prediction = None
    confidence = None
    if state.prediction is not None and state.decision == "accept_prediction":
        class_definition = catalog.class_for_label(state.prediction.class_name)
        prediction = PredictionResponse(
            class_name=state.prediction.class_name,
            display_name=catalog.display_name_for_label(state.prediction.class_name),
            fruit=class_definition.fruit_id,
            freshness=class_definition.freshness,
            confidence=state.prediction.confidence,
        )
        confidence = state.prediction.confidence

    quality = None
    if state.quality is not None:
        quality = ImageQualityResponse(
            brightness=state.quality.brightness,
            edge_strength=state.quality.edge_strength,
            is_dark=state.quality.is_dark,
            is_blurry=state.quality.is_blurry,
            is_overexposed=state.quality.is_overexposed,
        )

    scene = None
    if state.scene is not None:
        scene = SceneAnalysisResponse(
            image_width=state.scene.image_width,
            image_height=state.scene.image_height,
            foreground_ratio=state.scene.foreground_ratio,
            fruit_is_too_small=state.scene.fruit_is_too_small,
            likely_empty_scene=state.scene.likely_empty_scene,
            needs_crop_or_closer_photo=state.scene.needs_crop_or_closer_photo,
        )

    retrieval = None
    retrieval_metadata = state.metadata.get("retrieval", {})
    if state.retrieval is not None:
        method = str(retrieval_metadata.get("method", "unknown"))
        retrieval = RetrievalResponse(
            query=state.retrieval.query,
            method=method,
            model=retrieval_metadata.get("model"),
            documents=[
                RetrievalDocumentResponse(
                    id=str(document.get("id", "")),
                    fruit=str(document.get("fruit", "")),
                    topic=str(document.get("topic", "")),
                    text=str(document.get("text", "")),
                    score=float(document.get("retrieval_score", 0.0)),
                    method=str(document.get("retrieval_method", method)),
                )
                for document in state.retrieval.documents
            ],
        )

    warnings = [
        WarningResponse(level=warning.level, message=warning.message)
        for warning in state.structured_warnings
    ]
    if not warnings:
        warnings = [
            WarningResponse(level="warning", message=message)
            for message in state.warnings
        ]

    reasoning = None
    if state.reasoning is not None:
        reasoning = ReasoningResponse(
            explanation=state.reasoning.explanation,
            shelf_life_estimate=state.reasoning.shelf_life_estimate,
            storage_advice=state.reasoning.storage_advice,
            risk_level=state.reasoning.risk_level,
            source=state.reasoning.source,
        )

    explainability = None
    explanation_metadata = state.metadata.get("explainability", {})
    if (
        state.decision == "accept_prediction"
        and state.prediction is not None
        and explanation_metadata.get("method") == "grad_cam"
    ):
        overlay = None
        if include_explanation_overlay:
            overlay = gradcam_overlay_base64(
                state.image,
                explanation_metadata["heatmap"],
            )
        explainability = ExplainabilityResponse(
            target_class=str(explanation_metadata["target_class"]),
            layer=str(explanation_metadata["layer"]),
            peak_activation=float(explanation_metadata["peak_activation"]),
            active_fraction=float(explanation_metadata["active_fraction"]),
            overlay_png_base64=overlay,
            disclaimer=str(explanation_metadata["disclaimer"]),
        )

    return AnalyzeResponse(
        decision=state.decision,
        status=state.status,
        prediction=prediction,
        confidence=confidence,
        image_quality=quality,
        scene_analysis=scene,
        retrieval=retrieval,
        warnings=warnings,
        reasoning=reasoning,
        explainability=explainability,
        recommendation=state.recommendation,
        safety_notice=SAFETY_NOTICE,
    )
