import json

import pytest

from utils.startup import StartupValidationError, validate_startup


def _write_valid_knowledge_base(path):
    path.write_text(
        json.dumps(
            [
                {
                    "id": "apple_storage",
                    "fruit": "apple",
                    "topic": "storage",
                    "text": "Keep refrigerated.",
                }
            ]
        ),
        encoding="utf-8",
    )


def _write_valid_catalog(path):
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "classes": [
                    {"label": "freshapple", "fruit": "apple", "freshness": "fresh"},
                    {"label": "rottenapple", "fruit": "apple", "freshness": "rotten"},
                ],
                "fruits": [
                    {
                        "id": "apple",
                        "display_name": "Apple",
                        "fresh_shelf_life": "5 days",
                        "fresh_storage_advice": "Keep refrigerated.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_startup_rejects_missing_model(tmp_path):
    knowledge_base = tmp_path / "knowledge.json"
    _write_valid_knowledge_base(knowledge_base)
    catalog = tmp_path / "catalog.json"
    _write_valid_catalog(catalog)

    with pytest.raises(StartupValidationError, match="model is unavailable"):
        validate_startup(str(tmp_path / "missing.h5"), str(knowledge_base), str(catalog))


def test_startup_rejects_empty_model(tmp_path):
    model = tmp_path / "model.h5"
    model.touch()
    knowledge_base = tmp_path / "knowledge.json"
    _write_valid_knowledge_base(knowledge_base)
    catalog = tmp_path / "catalog.json"
    _write_valid_catalog(catalog)

    with pytest.raises(StartupValidationError, match="model is unavailable"):
        validate_startup(str(model), str(knowledge_base), str(catalog))


def test_startup_rejects_invalid_knowledge_base(tmp_path):
    model = tmp_path / "model.keras"
    model.write_bytes(b"model")
    knowledge_base = tmp_path / "knowledge.json"
    knowledge_base.write_text("not-json", encoding="utf-8")
    catalog = tmp_path / "catalog.json"
    _write_valid_catalog(catalog)

    with pytest.raises(StartupValidationError, match="not valid JSON"):
        validate_startup(str(model), str(knowledge_base), str(catalog))


def test_startup_accepts_valid_runtime_assets(tmp_path):
    model = tmp_path / "model.keras"
    model.write_bytes(b"model")
    knowledge_base = tmp_path / "knowledge.json"
    _write_valid_knowledge_base(knowledge_base)
    catalog = tmp_path / "catalog.json"
    _write_valid_catalog(catalog)

    validate_startup(str(model), str(knowledge_base), str(catalog))


def test_startup_rejects_missing_fruit_catalog(tmp_path):
    model = tmp_path / "model.keras"
    model.write_bytes(b"model")
    knowledge_base = tmp_path / "knowledge.json"
    _write_valid_knowledge_base(knowledge_base)

    with pytest.raises(StartupValidationError, match="fruit catalog is invalid"):
        validate_startup(
            str(model),
            str(knowledge_base),
            str(tmp_path / "missing-catalog.json"),
        )


def test_startup_rejects_catalog_without_matching_knowledge(tmp_path):
    model = tmp_path / "model.keras"
    model.write_bytes(b"model")
    knowledge_base = tmp_path / "knowledge.json"
    _write_valid_knowledge_base(knowledge_base)
    catalog = tmp_path / "catalog.json"
    _write_valid_catalog(catalog)
    payload = json.loads(catalog.read_text(encoding="utf-8"))
    payload["classes"].extend(
        [
            {"label": "freshmango", "fruit": "mango", "freshness": "fresh"},
            {"label": "rottenmango", "fruit": "mango", "freshness": "rotten"},
        ]
    )
    payload["fruits"].append(
        {
            "id": "mango",
            "display_name": "Mango",
            "fresh_shelf_life": "3 days",
            "fresh_storage_advice": "Store in a cool place.",
        }
    )
    catalog.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(StartupValidationError, match="missing guidance for: mango"):
        validate_startup(str(model), str(knowledge_base), str(catalog))
