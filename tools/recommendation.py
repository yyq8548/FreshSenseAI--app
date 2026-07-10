from agent.state import AgentState


class RecommendationTool:
    """Generates the final user-facing recommendation from the agent state."""

    def run(self, state: AgentState) -> AgentState:
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

        if "rotten" in label:
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
