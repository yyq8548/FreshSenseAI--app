"""Privacy-conscious GitHub feedback links for public beta users."""

from __future__ import annotations

from urllib.parse import urlencode

from agent.state import AgentState
from utils.version import APP_VERSION


FEEDBACK_ISSUE_URL = "https://github.com/yyq8548/FreshSenseAI--app/issues/new"


def build_feedback_url(state: AgentState | None = None) -> str:
    """Create a prefilled issue without including a photo name, path, or bytes."""
    prediction = "withheld"
    confidence = "not exposed"
    decision = "not analyzed"
    status = "unknown"
    if state is not None:
        decision = state.decision
        status = state.status
        if state.decision == "accept_prediction" and state.prediction is not None:
            prediction = state.prediction.class_name
            confidence = f"{state.prediction.confidence:.4f}"

    body = "\n".join(
        (
            "## What happened?",
            "Describe what looked incorrect or confusing.",
            "",
            "## Expected result",
            "Describe what you expected after manually inspecting the fruit.",
            "",
            "## Optional photo",
            "Attach a test photo only if you choose to share it. Remove personal details first.",
            "",
            "## App metadata",
            f"- FreshSense version: {APP_VERSION}",
            f"- Decision: {decision}",
            f"- Status: {status}",
            f"- Exposed prediction: {prediction}",
            f"- Exposed confidence: {confidence}",
            "",
            "FreshSense did not attach or upload the analyzed photo to this issue.",
        )
    )
    query = urlencode(
        {
            "template": "incorrect-result.md",
            "title": "[Beta] Incorrect result",
            "body": body,
        }
    )
    return f"{FEEDBACK_ISSUE_URL}?{query}"
