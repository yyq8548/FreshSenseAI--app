from agent.state import AgentState


class Planner:
    """Planner decides the next action from the current AgentState."""

    def plan_after_quality_check(self, state: AgentState) -> str:
        if state.quality is None:
            return "run_quality_check"

        if state.quality.is_dark or state.quality.is_blurry or state.quality.is_overexposed:
            return "request_retake"

        return "run_scene_analysis"

    def plan_after_scene_analysis(self, state: AgentState) -> str:
        # Scene analysis is advisory only. It can add warnings, but it should not
        # block DenseNet inference because lightweight heuristics can over-reject
        # valid fruit images such as smooth bananas on simple backgrounds.
        return "run_vision"

    def plan_after_inference(self, state: AgentState) -> str:
        if state.prediction is None:
            return "request_retake"

        if state.decision == "uncertain_input":
            return "return_uncertain_result"

        if state.decision != "accept_prediction":
            return "request_retake"

        return "generate_recommendation"
