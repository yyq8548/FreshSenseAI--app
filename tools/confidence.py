from agent.state import AgentState
from utils.config import MIN_CONFIDENCE


class ConfidenceTool:
    """Makes an autonomous decision based on model confidence."""

    def __init__(self, min_confidence: float = MIN_CONFIDENCE):
        self.min_confidence = min_confidence

    def run(self, state: AgentState) -> AgentState:
        if state.prediction is None:
            state.decision = "no_prediction"
            state.status = "failed"
            state.add_trace("ConfidenceTool could not run because prediction is missing.")
            return state

        confidence = state.prediction.confidence

        if confidence < self.min_confidence:
            state.decision = "retake_photo"
            state.status = "low_confidence"
            state.add_warning(
                f"Model confidence is low ({confidence:.2%}). Try another angle or clearer lighting."
            )
            state.add_trace("ConfidenceTool requested another image due to low confidence.")
        else:
            state.decision = "accept_prediction"
            state.status = "prediction_accepted"
            state.add_trace("ConfidenceTool accepted the prediction.")

        return state
