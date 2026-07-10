"""Validated, configuration-driven fruit and model-class metadata."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


SUPPORTED_SCHEMA_VERSION = 1
SUPPORTED_FRESHNESS_STATES = frozenset({"fresh", "rotten"})
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class FruitCatalogError(ValueError):
    """Raised when the fruit catalog is missing or internally inconsistent."""


@dataclass(frozen=True)
class FruitDefinition:
    id: str
    display_name: str
    fresh_shelf_life: str
    fresh_storage_advice: str


@dataclass(frozen=True)
class FruitClassDefinition:
    label: str
    fruit_id: str
    freshness: str


@dataclass(frozen=True)
class FruitCatalog:
    schema_version: int
    classes: tuple[FruitClassDefinition, ...]
    fruits: Mapping[str, FruitDefinition]

    @property
    def class_names(self) -> tuple[str, ...]:
        """Return model labels in the exact order used by the output tensor."""
        return tuple(item.label for item in self.classes)

    @property
    def fruit_ids(self) -> tuple[str, ...]:
        return tuple(self.fruits)

    def class_for_label(self, label: str) -> FruitClassDefinition:
        normalized = label.strip().lower()
        for item in self.classes:
            if item.label == normalized:
                return item
        raise FruitCatalogError(f"Model returned an unconfigured class label: {label!r}.")

    def fruit_for_label(self, label: str) -> FruitDefinition:
        item = self.class_for_label(label)
        return self.fruits[item.fruit_id]

    def display_name_for_label(self, label: str) -> str:
        item = self.class_for_label(label)
        fruit = self.fruits[item.fruit_id]
        return f"{item.freshness.title()} {fruit.display_name}"


@lru_cache(maxsize=16)
def load_fruit_catalog(path: str) -> FruitCatalog:
    """Load and cache a validated catalog from disk."""
    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise FruitCatalogError(f"Fruit catalog is unavailable: {catalog_path}.")

    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FruitCatalogError("Fruit catalog is not valid JSON.") from exc

    return parse_fruit_catalog(payload)


def parse_fruit_catalog(payload: object) -> FruitCatalog:
    """Validate a decoded catalog and return immutable domain objects."""
    if not isinstance(payload, dict):
        raise FruitCatalogError("Fruit catalog must be a JSON object.")

    schema_version = payload.get("schema_version")
    if schema_version != SUPPORTED_SCHEMA_VERSION:
        raise FruitCatalogError(
            f"Fruit catalog schema_version must be {SUPPORTED_SCHEMA_VERSION}."
        )

    raw_fruits = payload.get("fruits")
    if not isinstance(raw_fruits, list) or not raw_fruits:
        raise FruitCatalogError("Fruit catalog must contain a non-empty fruits list.")

    fruits: dict[str, FruitDefinition] = {}
    required_fruit_fields = {
        "id",
        "display_name",
        "fresh_shelf_life",
        "fresh_storage_advice",
    }
    for raw_fruit in raw_fruits:
        if not isinstance(raw_fruit, dict) or not required_fruit_fields.issubset(raw_fruit):
            raise FruitCatalogError(
                "Every fruit must contain id, display_name, fresh_shelf_life, "
                "and fresh_storage_advice."
            )
        values = {field: raw_fruit[field] for field in required_fruit_fields}
        if any(not isinstance(value, str) or not value.strip() for value in values.values()):
            raise FruitCatalogError("Fruit fields must be non-empty strings.")

        fruit_id = values["id"].strip().lower()
        if not IDENTIFIER_PATTERN.fullmatch(fruit_id):
            raise FruitCatalogError(f"Invalid fruit id: {fruit_id!r}.")
        if fruit_id in fruits:
            raise FruitCatalogError(f"Duplicate fruit id: {fruit_id!r}.")

        fruits[fruit_id] = FruitDefinition(
            id=fruit_id,
            display_name=values["display_name"].strip(),
            fresh_shelf_life=values["fresh_shelf_life"].strip(),
            fresh_storage_advice=values["fresh_storage_advice"].strip(),
        )

    raw_classes = payload.get("classes")
    if not isinstance(raw_classes, list) or not raw_classes:
        raise FruitCatalogError("Fruit catalog must contain a non-empty classes list.")

    classes: list[FruitClassDefinition] = []
    labels: set[str] = set()
    states_by_fruit: dict[str, set[str]] = {fruit_id: set() for fruit_id in fruits}
    for raw_class in raw_classes:
        if not isinstance(raw_class, dict) or not {"label", "fruit", "freshness"}.issubset(
            raw_class
        ):
            raise FruitCatalogError("Every class must contain label, fruit, and freshness.")

        if any(
            not isinstance(raw_class[field], str) or not raw_class[field].strip()
            for field in ("label", "fruit", "freshness")
        ):
            raise FruitCatalogError("Class fields must be non-empty strings.")

        label = raw_class["label"].strip().lower()
        fruit_id = raw_class["fruit"].strip().lower()
        freshness = raw_class["freshness"].strip().lower()
        if not IDENTIFIER_PATTERN.fullmatch(label):
            raise FruitCatalogError(f"Invalid class label: {label!r}.")
        if label in labels:
            raise FruitCatalogError(f"Duplicate class label: {label!r}.")
        if fruit_id not in fruits:
            raise FruitCatalogError(
                f"Class {label!r} references unknown fruit {fruit_id!r}."
            )
        if freshness not in SUPPORTED_FRESHNESS_STATES:
            raise FruitCatalogError(
                f"Class {label!r} has unsupported freshness state {freshness!r}."
            )
        if freshness in states_by_fruit[fruit_id]:
            raise FruitCatalogError(
                f"Fruit {fruit_id!r} has more than one {freshness!r} class."
            )

        labels.add(label)
        states_by_fruit[fruit_id].add(freshness)
        classes.append(
            FruitClassDefinition(label=label, fruit_id=fruit_id, freshness=freshness)
        )

    for fruit_id, states in states_by_fruit.items():
        if states != SUPPORTED_FRESHNESS_STATES:
            raise FruitCatalogError(
                f"Fruit {fruit_id!r} must define exactly one fresh class and one rotten class."
            )

    return FruitCatalog(
        schema_version=schema_version,
        classes=tuple(classes),
        fruits=MappingProxyType(fruits),
    )
