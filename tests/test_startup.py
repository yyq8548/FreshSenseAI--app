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


def test_startup_rejects_missing_model(tmp_path):
    knowledge_base = tmp_path / "knowledge.json"
    _write_valid_knowledge_base(knowledge_base)

    with pytest.raises(StartupValidationError, match="model is unavailable"):
        validate_startup(str(tmp_path / "missing.h5"), str(knowledge_base))


def test_startup_rejects_empty_model(tmp_path):
    model = tmp_path / "model.h5"
    model.touch()
    knowledge_base = tmp_path / "knowledge.json"
    _write_valid_knowledge_base(knowledge_base)

    with pytest.raises(StartupValidationError, match="model is unavailable"):
        validate_startup(str(model), str(knowledge_base))


def test_startup_rejects_invalid_knowledge_base(tmp_path):
    model = tmp_path / "model.keras"
    model.write_bytes(b"model")
    knowledge_base = tmp_path / "knowledge.json"
    knowledge_base.write_text("not-json", encoding="utf-8")

    with pytest.raises(StartupValidationError, match="not valid JSON"):
        validate_startup(str(model), str(knowledge_base))


def test_startup_accepts_valid_runtime_assets(tmp_path):
    model = tmp_path / "model.keras"
    model.write_bytes(b"model")
    knowledge_base = tmp_path / "knowledge.json"
    _write_valid_knowledge_base(knowledge_base)

    validate_startup(str(model), str(knowledge_base))
