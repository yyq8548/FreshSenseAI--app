from PIL import Image

from agent.state import AgentState
from agent.planner import Planner
from tools.image_quality import ImageQualityTool
from tools.scene_analysis import SceneAnalysisTool
from tools.vision import DenseNetVisionTool
from tools.confidence import ConfidenceTool
from tools.rag import FoodKnowledgeRetriever
from tools.llm_reasoning import LLMReasoningTool
from tools.recommendation import RecommendationTool
from utils.config import (
    FRUIT_CATALOG_PATH,
    KNOWLEDGE_BASE_PATH,
    MIN_CONFIDENCE,
    OPEN_SET_GATE_PATH,
    REQUIRE_OPEN_SET_GATE,
)
from utils.fruit_catalog import load_fruit_catalog


class FruitScannerAgent:
    """Tool-orchestrating agent for fruit freshness analysis."""

    def __init__(
        self,
        model_path: str,
        min_confidence: float = MIN_CONFIDENCE,
        catalog_path: str = FRUIT_CATALOG_PATH,
        knowledge_base_path: str = KNOWLEDGE_BASE_PATH,
        open_set_gate_path: str | None = OPEN_SET_GATE_PATH,
        require_open_set_gate: bool = REQUIRE_OPEN_SET_GATE,
    ):
        self.catalog = load_fruit_catalog(catalog_path)
        self.planner = Planner()
        self.quality_tool = ImageQualityTool()
        self.scene_tool = SceneAnalysisTool()
        self.vision_tool = DenseNetVisionTool(
            model_path=model_path,
            catalog=self.catalog,
            open_set_gate_path=open_set_gate_path,
            require_open_set_gate=require_open_set_gate,
        )
        self.confidence_tool = ConfidenceTool(min_confidence=min_confidence)
        self.retriever_tool = FoodKnowledgeRetriever(
            knowledge_base_path=knowledge_base_path,
            catalog=self.catalog,
        )
        self.reasoning_tool = LLMReasoningTool(catalog=self.catalog)
        self.recommendation_tool = RecommendationTool(catalog=self.catalog)

    def run(self, image: Image.Image) -> AgentState:
        state = AgentState(image=image)
        state.add_trace("Agent initialized.")

        state = self.quality_tool.run(state)
        next_action = self.planner.plan_after_quality_check(state)
        state.add_trace(f"Planner selected next action after quality check: {next_action}.")

        if next_action == "request_retake":
            state.decision = "retake_photo"
            state.status = "stopped_due_to_image_quality"
            state = self.retriever_tool.run(state)
            state = self.reasoning_tool.run(state)
            state = self.recommendation_tool.run(state)
            return state

        state = self.scene_tool.run(state)
        next_action = self.planner.plan_after_scene_analysis(state)
        state.add_trace(f"Planner selected next action after scene analysis: {next_action}.")

        state = self.vision_tool.run(state)
        if state.decision == "unsupported_input":
            state = self.retriever_tool.run(state)
            state = self.recommendation_tool.run(state)
            state.add_trace("Agent returned an unsupported-input result without freshness guidance.")
            return state
        state = self.confidence_tool.run(state)

        next_action = self.planner.plan_after_inference(state)
        state.add_trace(f"Planner selected next action after inference: {next_action}.")

        if next_action == "return_uncertain_result":
            state = self.recommendation_tool.run(state)
            state.add_trace("Agent returned an uncertainty result without fruit guidance.")
            return state

        state = self.retriever_tool.run(state)
        state = self.reasoning_tool.run(state)
        state = self.recommendation_tool.run(state)
        state.add_trace("Agent workflow completed.")
        return state
