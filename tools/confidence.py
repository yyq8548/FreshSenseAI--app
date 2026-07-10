from agent.state import AgentState
from utils.config import MIN_CONFIDENCE, MIN_PREDICTION_MARGIN


class ConfidenceTool:
    """Accepts clear model results and routes ambiguous results to uncertainty."""

    def __init__(
        self,
        min_confidence: float = MIN_CONFIDENCE,
        min_prediction_margin: float = MIN_PREDICTION_MARGIN,
    ):
        self.min_confidence = min_confidence
        self.min_prediction_margin = min_prediction_margin

    def run(self, state: AgentState) -> AgentState:
        if state.prediction is None:
            state.decision = "no_prediction"
            state.status = "failed"
            state.add_trace("ConfidenceTool could not run because prediction is missing.")
            return state

        confidence = state.prediction.confidence
        probabilities = sorted(
            (float(value) for value in state.prediction.raw_probabilities),
            reverse=True,
        )
        prediction_margin = (
            probabilities[0] - probabilities[1] if len(probabilities) >= 2 else None
        )
        state.metadata["confidence_gate"] = {
            "confidence": confidence,
            "prediction_margin": prediction_margin,
            "min_confidence": self.min_confidence,
            "min_prediction_margin": self.min_prediction_margin,
        }

        uncertainty_reasons = []
        if confidence < self.min_confidence:
            uncertainty_reasons.append(f"confidence {confidence:.2%} is below the threshold")
        if (
            prediction_margin is not None
            and prediction_margin < self.min_prediction_margin
        ):
            uncertainty_reasons.append(
                f"the top-two prediction margin {prediction_margin:.2%} is too small"
            )

        if uncertainty_reasons:
            state.decision = "uncertain_input"
            state.status = "unsupported_or_uncertain"
            state.add_warning(
                "FreshSense could not confirm a supported result because "
                + " and ".join(uncertainty_reasons)
                + "."
            )
            state.add_trace("ConfidenceTool withheld the tentative class as uncertain.")
        else:
            state.decision = "accept_prediction"
            state.status = "prediction_accepted"
            state.add_trace("ConfidenceTool accepted the prediction.")

        return state
