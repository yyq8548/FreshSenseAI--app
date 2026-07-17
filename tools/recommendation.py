from agent.state import AgentState
from utils.config import FRUIT_CATALOG_PATH
from utils.fruit_catalog import FruitCatalog, load_fruit_catalog


class RecommendationTool:
    """Generates the final user-facing recommendation from the agent state."""

    def __init__(
        self,
        catalog: FruitCatalog | None = None,
        catalog_path: str = FRUIT_CATALOG_PATH,
    ) -> None:
        self.catalog = catalog or load_fruit_catalog(catalog_path)

    def run(self, state: AgentState) -> AgentState:
        if state.decision == "unsupported_input":
            supported_names = [
                fruit.display_name.lower() for fruit in self.catalog.fruits.values()
            ]
            supported = ", ".join(supported_names[:-1]) + f", or {supported_names[-1]}"
            state.recommendation = (
                "FreshSense could not confirm a supported fruit in this image. "
                f"Use one clear {supported} photo at a time. No freshness guidance "
                "was generated for this image."
            )
            state.add_trace("RecommendationTool generated unsupported-input guidance.")
            return state

        if state.decision == "uncertain_input":
            supported_names = [
                fruit.display_name.lower() for fruit in self.catalog.fruits.values()
            ]
            if len(supported_names) == 1:
                supported = supported_names[0]
            elif len(supported_names) == 2:
                supported = f"{supported_names[0]} or {supported_names[1]}"
            else:
                supported = f"{', '.join(supported_names[:-1])}, or {supported_names[-1]}"
            state.recommendation = (
                "FreshSense could not produce a supported freshness result. "
                f"It currently analyzes one clear {supported} photo at a time. "
                "Try a closer, well-lit photo of a supported fruit."
            )
            state.add_trace("RecommendationTool generated uncertainty guidance.")
            return state

        if state.decision == "retake_photo":
            state.recommendation = (
                "Please retake the photo with brighter lighting, less blur, "
                "and the fruit clearly centered."
            )
            state.add_trace("RecommendationTool generated retake recommendation.")
            return state

        if state.prediction is None:
            state.recommendation = "No reliable prediction was generated."
            state.add_trace("RecommendationTool generated fallback recommendation.")
            return state

        label = state.prediction.class_name.lower()
        confidence = state.prediction.confidence
        freshness = self.catalog.class_for_label(label).freshness

        if freshness == "rotten":
            state.recommendation = (
                f"The image shows visible patterns associated with rotten or low-quality fruit "
                f"with {confidence:.2%} model confidence. Do not consume it when there are signs "
                "such as mold, leaking liquid, sliminess, collapse, or an off odor."
            )
        else:
            state.recommendation = (
                f"The image shows visible patterns associated with fresh fruit with "
                f"{confidence:.2%} model confidence. This visual result does not establish that "
                "the fruit is safe to eat; inspect it for mold, odor, leaking, and texture changes."
            )

        if state.reasoning:
            state.recommendation += (
                f" Shelf-life estimate: {state.reasoning.shelf_life_estimate}. "
                f"Storage advice: {state.reasoning.storage_advice}"
            )

        state.add_trace("RecommendationTool generated final freshness recommendation.")
        return state
