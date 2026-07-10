from agent.state import AgentState, ReasoningResult


class RuleBasedReasoningTool:
    """
    Generates structured reasoning without requiring an LLM API.

    This tool can later be replaced by an LLMReasoningTool while keeping
    the same AgentState interface.
    """

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
        is_rotten = "rotten" in label

        fruit_type = self._extract_fruit_type(label)

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
            shelf_life = self._estimate_shelf_life(fruit_type)
            storage = self._storage_advice(fruit_type)
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

    def _extract_fruit_type(self, label: str) -> str:
        if "apple" in label:
            return "apple"
        if "banana" in label:
            return "banana"
        if "orange" in label:
            return "orange"
        return "fruit"

    def _estimate_shelf_life(self, fruit_type: str) -> str:
        if fruit_type == "banana":
            return "2-5 days at room temperature"
        if fruit_type == "apple":
            return "5-7 days at room temperature, longer if refrigerated"
        if fruit_type == "orange":
            return "5-10 days at room temperature, longer if refrigerated"
        return "Several days depending on storage conditions"

    def _storage_advice(self, fruit_type: str) -> str:
        if fruit_type == "banana":
            return "Store at room temperature and away from direct sunlight."
        if fruit_type == "apple":
            return "Store in a cool place or refrigerate to extend freshness."
        if fruit_type == "orange":
            return "Store in a cool, dry place or refrigerate for longer shelf life."
        return "Store in a cool, dry environment."
