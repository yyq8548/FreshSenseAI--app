"""Fail-fast startup validation for FreshSense runtime assets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


class StartupValidationError(RuntimeError):
    """Raised when required production assets are missing or invalid."""


def validate_startup(model_path: str, knowledge_base_path: str) -> None:
    """Validate required runtime files before constructing the application."""
    model = Path(model_path)
    if not model.is_file() or model.stat().st_size == 0:
        raise StartupValidationError(
            "The FreshSense model is unavailable. Configure FRESHSENSE_MODEL_PATH "
            "to a non-empty .h5 or .keras model file."
        )
    if model.suffix.lower() not in {".h5", ".keras"}:
        raise StartupValidationError("The configured model must be an .h5 or .keras file.")

    knowledge_base = Path(knowledge_base_path)
    if not knowledge_base.is_file():
        raise StartupValidationError("The configured food knowledge base is unavailable.")

    try:
        documents = json.loads(knowledge_base.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StartupValidationError("The food knowledge base is not valid JSON.") from exc

    _validate_documents(documents)


def _validate_documents(documents: object) -> None:
    if not isinstance(documents, list) or not documents:
        raise StartupValidationError("The food knowledge base must be a non-empty list.")

    required_fields = {"id", "fruit", "topic", "text"}
    ids: list[str] = []
    for document in documents:
        if not isinstance(document, dict) or not required_fields.issubset(document):
            raise StartupValidationError(
                "Every knowledge document must contain id, fruit, topic, and text."
            )
        values: Iterable[object] = (document[field] for field in required_fields)
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise StartupValidationError("Knowledge document fields must be non-empty strings.")
        ids.append(document["id"])

    if len(ids) != len(set(ids)):
        raise StartupValidationError("Knowledge document ids must be unique.")
