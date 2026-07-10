import json
import os

from agent.state import AgentState, ReasoningResult
from tools.reasoning import RuleBasedReasoningTool
from utils.config import FRUIT_CATALOG_PATH, LLM_MODEL, OPENAI_API_KEY_ENV, USE_LLM_REASONING
from utils.fruit_catalog import FruitCatalog, load_fruit_catalog


class LLMReasoningTool:
    """
    Generates natural-language freshness reasoning with OpenAI.

    If no API key is available or the API call fails, this tool safely falls back
    to RuleBasedReasoningTool so the application never breaks.
    """

    def __init__(
        self,
        model: str = LLM_MODEL,
        catalog: FruitCatalog | None = None,
        catalog_path: str = FRUIT_CATALOG_PATH,
    ):
        self.model = model
        self.catalog = catalog or load_fruit_catalog(catalog_path)
        self.fallback_tool = RuleBasedReasoningTool(catalog=self.catalog)

    def run(self, state: AgentState) -> AgentState:
        if not USE_LLM_REASONING:
            state.add_trace("LLMReasoningTool skipped because USE_LLM_REASONING=false.")
            return self.fallback_tool.run(state)

        if not os.getenv(OPENAI_API_KEY_ENV):
            state.add_trace("LLMReasoningTool skipped because OPENAI_API_KEY is not set.")
            return self.fallback_tool.run(state)

        if state.prediction is None:
            state.add_trace("LLMReasoningTool used fallback because prediction is missing.")
            return self.fallback_tool.run(state)

        try:
            from openai import OpenAI

            client = OpenAI()
            payload = self._build_payload(state)

            response = client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": (
                            "You are a produce freshness assistant. "
                            "Use the model prediction, image-quality metadata, and retrieved food-safety knowledge. "
                            "Do not invent facts that conflict with the retrieved knowledge. "
                            "Return only valid JSON with keys: explanation, shelf_life_estimate, storage_advice, risk_level."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload),
                    },
                ],
            )

            text = response.output_text.strip()
            data = json.loads(text)

            state.reasoning = ReasoningResult(
                explanation=data.get("explanation", ""),
                shelf_life_estimate=data.get("shelf_life_estimate", "Unknown"),
                storage_advice=data.get("storage_advice", "Store appropriately based on produce type."),
                risk_level=data.get("risk_level", "unknown"),
                source="llm_rag" if state.retrieval else "llm",
            )
            state.add_trace(f"LLMReasoningTool generated reasoning using {self.model}.")
            return state

        except Exception as exc:
            state.add_warning(
                "AI reasoning is temporarily unavailable; using reviewed rule-based guidance.",
                level="suggestion",
            )
            state.add_trace(
                "LLMReasoningTool failed and fell back to RuleBasedReasoningTool "
                f"({type(exc).__name__})."
            )
            fallback_state = self.fallback_tool.run(state)
            if fallback_state.reasoning:
                fallback_state.reasoning.source = "rule_based_fallback"
            return fallback_state

    def _build_payload(self, state: AgentState) -> dict:
        prediction = state.prediction
        class_definition = (
            self.catalog.class_for_label(prediction.class_name) if prediction else None
        )
        quality = state.quality
        scene = state.scene
        retrieved_docs = state.retrieval.documents if state.retrieval else []

        return {
            "prediction": {
                "class_name": prediction.class_name if prediction else None,
                "confidence": prediction.confidence if prediction else None,
                "fruit": class_definition.fruit_id if class_definition else None,
                "freshness": class_definition.freshness if class_definition else None,
            },
            "image_quality": {
                "brightness": quality.brightness if quality else None,
                "edge_strength": quality.edge_strength if quality else None,
                "is_dark": quality.is_dark if quality else None,
                "is_blurry": quality.is_blurry if quality else None,
                "is_overexposed": quality.is_overexposed if quality else None,
            },
            "scene_analysis": {
                "foreground_ratio": scene.foreground_ratio if scene else None,
                "fruit_is_too_small": scene.fruit_is_too_small if scene else None,
                "likely_empty_scene": scene.likely_empty_scene if scene else None,
                "needs_crop_or_closer_photo": scene.needs_crop_or_closer_photo if scene else None,
            },
            "retrieved_knowledge": retrieved_docs,
            "warnings": state.warnings,
        }
