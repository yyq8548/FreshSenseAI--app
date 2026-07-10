"""Presentation helpers kept independent from the Qt runtime."""

from agent.state import AgentState


def humanize_class_name(class_name: str) -> str:
    normalized = class_name.lower()
    freshness = "Rotten" if normalized.startswith("rotten") else "Fresh"
    fruit = normalized.removeprefix("rotten").removeprefix("fresh")
    names = {"apples": "Apple", "banana": "Banana", "oranges": "Orange"}
    return f"{freshness} {names.get(fruit, fruit.title())}"


def result_summary(state: AgentState) -> dict[str, str]:
    if state.prediction is None:
        return {
            "title": "Photo retake needed",
            "confidence": "No reliable prediction",
            "risk": "Unknown",
            "recommendation": state.recommendation,
            "details": _warning_text(state),
        }

    reasoning = state.reasoning
    details = reasoning.explanation if reasoning else ""
    warnings = _warning_text(state)
    if warnings:
        details = f"{details}\n\nPhoto guidance:\n{warnings}".strip()

    return {
        "title": humanize_class_name(state.prediction.class_name),
        "confidence": f"{state.prediction.confidence:.1%} model confidence",
        "risk": (reasoning.risk_level.title() if reasoning else "Unknown"),
        "recommendation": state.recommendation,
        "details": details,
    }


def _warning_text(state: AgentState) -> str:
    return "\n".join(f"• {warning.message}" for warning in state.structured_warnings)
