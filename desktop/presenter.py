"""Presentation helpers kept independent from the Qt runtime."""

from agent.state import AgentState
from utils.config import FRUIT_CATALOG_PATH
from utils.fruit_catalog import FruitCatalog, FruitCatalogError, load_fruit_catalog


def humanize_class_name(
    class_name: str,
    catalog: FruitCatalog | None = None,
) -> str:
    active_catalog = catalog or load_fruit_catalog(FRUIT_CATALOG_PATH)
    return active_catalog.display_name_for_label(class_name)


def supported_scope_text(catalog: FruitCatalog | None = None) -> str:
    try:
        active_catalog = catalog or load_fruit_catalog(FRUIT_CATALOG_PATH)
    except FruitCatalogError:
        return "Supported fruit list unavailable until startup validation completes."
    names = ", ".join(fruit.display_name for fruit in active_catalog.fruits.values())
    return f"Supported fruits: {names}. Use one fruit type per photo."


def result_summary(
    state: AgentState,
    catalog: FruitCatalog | None = None,
) -> dict[str, str]:
    if state.decision == "unsupported_input":
        warnings = _warning_text(state)
        return {
            "title": "Unsupported photo",
            "confidence": "No fruit result",
            "risk": "Unknown",
            "recommendation": state.recommendation,
            "details": (
                "The supported-input gate did not confirm one supported fruit type. "
                "The freshness classifier was withheld."
                + (f"\n\nPhoto guidance:\n{warnings}" if warnings else "")
            ),
        }

    if state.decision == "uncertain_input":
        warnings = _warning_text(state)
        details = (
            "The tentative model class was withheld because the result did not pass "
            "FreshSense's confidence checks. This can happen with an unsupported image "
            "or an unclear photo."
        )
        if warnings:
            details = f"{details}\n\nPhoto guidance:\n{warnings}"
        return {
            "title": "Unsupported or uncertain photo",
            "confidence": "No supported result",
            "risk": "Unknown",
            "recommendation": state.recommendation,
            "details": details,
        }

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
    retrieval_method = state.metadata.get("retrieval", {}).get("method")
    if retrieval_method == "semantic":
        details = f"{details}\n\nKnowledge retrieval: Local semantic embeddings.".strip()
    elif retrieval_method == "keyword_fallback":
        details = f"{details}\n\nKnowledge retrieval: Keyword fallback.".strip()

    return {
        "title": humanize_class_name(state.prediction.class_name, catalog=catalog),
        "confidence": f"{state.prediction.confidence:.1%} model confidence",
        "risk": (reasoning.risk_level.title() if reasoning else "Unknown"),
        "recommendation": state.recommendation,
        "details": details,
    }


def _warning_text(state: AgentState) -> str:
    return "\n".join(f"• {warning.message}" for warning in state.structured_warnings)
