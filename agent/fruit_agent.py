import time

from PIL import Image

from agent.state import AgentState
from agent.planner import Planner
from tools.image_quality import ImageQualityTool
from tools.scene_analysis import SceneAnalysisTool
from tools.vision import DenseNetVisionTool
from tools.confidence import ConfidenceTool
from tools.rag import FoodKnowledgeRetriever
from tools.llm_reasoning import LLMReasoningTool
from tools.reasoning import RuleBasedReasoningTool
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
        self.fast_reasoning_tool = RuleBasedReasoningTool(catalog=self.catalog)
        self.recommendation_tool = RecommendationTool(catalog=self.catalog)

    def run(self, image: Image.Image) -> AgentState:
        """Run the full desktop workflow, including configured explanations."""
        return self._run(image, fast_mode=False, generate_explanation=None)

    def run_for_api(
        self,
        image: Image.Image,
        *,
        include_explanation: bool = False,
    ) -> AgentState:
        """Run the low-latency API path unless detailed explanation is requested."""
        return self._run(
            image,
            fast_mode=not include_explanation,
            generate_explanation=include_explanation,
        )

    def warm_up(self) -> None:
        """Prepare TensorFlow kernels before the service accepts customer traffic."""
        self.vision_tool.warm_up()

    def _run(
        self,
        image: Image.Image,
        *,
        fast_mode: bool,
        generate_explanation: bool | None,
    ) -> AgentState:
        started = time.perf_counter()
        state = AgentState(image=image)
        state.add_trace("Agent initialized.")
        state.metadata["execution_mode"] = "fast" if fast_mode else "detailed"

        state = self.quality_tool.run(state)
        next_action = self.planner.plan_after_quality_check(state)
        state.add_trace(f"Planner selected next action after quality check: {next_action}.")

        if next_action == "request_retake":
            state.decision = "retake_photo"
            state.status = "stopped_due_to_image_quality"
            state = self.retriever_tool.run(state)
            reasoning_tool = self.fast_reasoning_tool if fast_mode else self.reasoning_tool
            state = reasoning_tool.run(state)
            state = self.recommendation_tool.run(state)
            state.metadata["performance_ms"] = round(
                (time.perf_counter() - started) * 1000, 1
            )
            return state

        state = self.scene_tool.run(state)
        next_action = self.planner.plan_after_scene_analysis(state)
        state.add_trace(f"Planner selected next action after scene analysis: {next_action}.")

        state = self.vision_tool.run(
            state,
            generate_explanation=generate_explanation,
        )
        if state.decision == "unsupported_input":
            state = self.retriever_tool.run(state)
            state = self.recommendation_tool.run(state)
            state.add_trace("Agent returned an unsupported-input result without freshness guidance.")
            state.metadata["performance_ms"] = round(
                (time.perf_counter() - started) * 1000, 1
            )
            return state
        state = self.confidence_tool.run(state)

        next_action = self.planner.plan_after_inference(state)
        state.add_trace(f"Planner selected next action after inference: {next_action}.")

        if next_action == "return_uncertain_result":
            state = self.recommendation_tool.run(state)
            state.add_trace("Agent returned an uncertainty result without fruit guidance.")
            state.metadata["performance_ms"] = round(
                (time.perf_counter() - started) * 1000, 1
            )
            return state

        state = self.retriever_tool.run(state)
        reasoning_tool = self.fast_reasoning_tool if fast_mode else self.reasoning_tool
        state = reasoning_tool.run(state)
        state = self.recommendation_tool.run(state)
        state.add_trace("Agent workflow completed.")
        state.metadata["performance_ms"] = round(
            (time.perf_counter() - started) * 1000, 1
        )
        return state
