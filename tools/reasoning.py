from agent.state import AgentState, ReasoningResult
from utils.config import FRUIT_CATALOG_PATH
from utils.fruit_catalog import FruitCatalog, load_fruit_catalog


class RuleBasedReasoningTool:
    """
    Generates structured reasoning without requiring an LLM API.

    This tool can later be replaced by an LLMReasoningTool while keeping
    the same AgentState interface.
    """

    def __init__(
        self,
        catalog: FruitCatalog | None = None,
        catalog_path: str = FRUIT_CATALOG_PATH,
    ) -> None:
        self.catalog = catalog or load_fruit_catalog(catalog_path)

    def run(self, state: AgentState) -> AgentState:
        if state.prediction is None:
            state.reasoning = ReasoningResult(
                explanation="The agent did not generate a model prediction.",
                shelf_life_estimate="Unknown",
                storage_advice="Please retake the photo before making a decision.",
                risk_level="unknown",
            )
            state.add_trace("RuleBasedReasoningTool generated fallback reasoning.")
            return state

        label = state.prediction.class_name.lower()
        confidence = state.prediction.confidence
        class_definition = self.catalog.class_for_label(label)
        fruit = self.catalog.fruits[class_definition.fruit_id]
        is_rotten = class_definition.freshness == "rotten"
        fruit_type = fruit.display_name.lower()

        if is_rotten:
            explanation = (
                f"The model classified this image as rotten {fruit_type} with "
                f"{confidence:.2%} confidence. This suggests visible spoilage patterns "
                "such as discoloration, texture degradation, or other freshness-related defects."
            )
            shelf_life = "Not recommended for storage or consumption"
            storage = "Do not store with fresh produce. Discard or avoid purchasing."
            risk = "high"
        else:
            explanation = (
                f"The model classified this image as fresh {fruit_type} with "
                f"{confidence:.2%} confidence. The visible features are more consistent "
                "with fresh produce than spoiled produce."
            )
            shelf_life = fruit.fresh_shelf_life
            storage = fruit.fresh_storage_advice
            risk = "low" if confidence >= 0.90 else "medium"

        if state.quality:
            if state.quality.brightness < 90:
                explanation += " However, lighting is somewhat low, so confidence should be interpreted carefully."
            if state.quality.edge_strength < 120:
                explanation += " The image may contain limited edge detail, which can reduce prediction reliability."

        state.reasoning = ReasoningResult(
            explanation=explanation,
            shelf_life_estimate=shelf_life,
            storage_advice=storage,
            risk_level=risk,
        )
        state.add_trace("RuleBasedReasoningTool generated structured reasoning.")
        return state
