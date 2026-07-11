from io import BytesIO
from types import SimpleNamespace

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from agent.state import (
    AgentState,
    ImageQualityResult,
    PredictionResult,
    ReasoningResult,
    RetrievalResult,
    SceneAnalysisResult,
)
from api.app import create_app
from utils.fruit_catalog import load_fruit_catalog
from utils.config import FRUIT_CATALOG_PATH


class _FakeAgent:
    def __init__(self, *, semantic_ready: bool = True) -> None:
        self.catalog = load_fruit_catalog(FRUIT_CATALOG_PATH)
        self.retriever_tool = SimpleNamespace(
            semantic_ready=semantic_ready,
            embedder=(
                SimpleNamespace(model_name="test/semantic-model")
                if semantic_ready
                else None
            ),
        )
        self.run_count = 0
        self.last_image = None

    def run(self, image: Image.Image) -> AgentState:
        self.run_count += 1
        self.last_image = image
        state = AgentState(image=image)
        state.quality = ImageQualityResult(
            brightness=125.0,
            edge_strength=90.0,
            is_dark=False,
            is_blurry=False,
            is_overexposed=False,
        )
        state.scene = SceneAnalysisResult(
            image_width=image.width,
            image_height=image.height,
            foreground_ratio=0.45,
            fruit_is_too_small=False,
            likely_empty_scene=False,
            needs_crop_or_closer_photo=False,
        )
        state.prediction = PredictionResult(
            class_name="freshbanana",
            confidence=0.97,
            raw_probabilities=[0.01, 0.97, 0.01, 0.0, 0.005, 0.005],
        )
        state.retrieval = RetrievalResult(
            query="Banana fresh produce storage guidance",
            documents=[
                {
                    "id": "banana_storage",
                    "fruit": "banana",
                    "topic": "storage",
                    "text": "Keep at room temperature until ripe.",
                    "retrieval_score": 0.812345,
                    "retrieval_method": "semantic",
                }
            ],
        )
        state.metadata["retrieval"] = {
            "method": "semantic",
            "model": "test/semantic-model",
            "documents": 1,
        }
        state.reasoning = ReasoningResult(
            explanation="The visible features are consistent with fresh banana.",
            shelf_life_estimate="2-5 days",
            storage_advice="Store at room temperature.",
            risk_level="low",
            source="rule_based",
        )
        state.decision = "accept_prediction"
        state.status = "completed"
        state.recommendation = "Inspect the fruit before eating."
        state.add_warning("Visual assessment cannot detect internal spoilage.")
        return state


class _UncertainAgent(_FakeAgent):
    def run(self, image: Image.Image) -> AgentState:
        state = super().run(image)
        state.decision = "uncertain_input"
        state.status = "unsupported_or_uncertain"
        state.retrieval = None
        state.reasoning = None
        state.recommendation = "Try another supported photo."
        return state


class _FailingAgent(_FakeAgent):
    def run(self, image: Image.Image) -> AgentState:
        self.last_image = image
        raise RuntimeError("sensitive internal failure")


def _image_bytes(
    *,
    size: tuple[int, int] = (16, 16),
    image_format: str = "PNG",
) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, "yellow").save(buffer, format=image_format)
    return buffer.getvalue()


def _upload(data: bytes, content_type: str = "image/png", name: str = "banana.png"):
    return {"file": (name, data, content_type)}


def test_api_loads_one_shared_agent_and_reports_health():
    fake_agent = _FakeAgent()
    factory_calls = []

    def factory():
        factory_calls.append(True)
        return fake_agent

    app = create_app(agent_factory=factory)
    with TestClient(app) as client:
        first = client.get("/api/v1/health")
        second = client.get("/api/v1/health")

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(factory_calls) == 1
    assert first.json() == {
        "service": "FreshSense AI",
        "api_version": "v1",
        "status": "ok",
        "model_loaded": True,
        "semantic_retrieval_ready": True,
        "retrieval_mode": "semantic",
        "semantic_model": "test/semantic-model",
        "supported_fruits": ["Apple", "Banana", "Orange"],
        "image_retention": False,
        "authentication_required": False,
        "rate_limit_per_minute": 30,
    }


def test_api_health_reports_keyword_fallback():
    app = create_app(agent_factory=lambda: _FakeAgent(semantic_ready=False))
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["retrieval_mode"] == "keyword_fallback"
    assert response.json()["semantic_model"] is None


def test_analyze_returns_prediction_retrieval_warnings_and_privacy_contract():
    fake_agent = _FakeAgent()
    app = create_app(agent_factory=lambda: fake_agent)
    with TestClient(app) as client:
        response = client.post("/api/v1/analyze", files=_upload(_image_bytes()))

    assert response.status_code == 200
    body = response.json()
    assert body["prediction"]["class_name"] == "freshbanana"
    assert body["prediction"]["display_name"] == "Fresh Banana"
    assert body["prediction"]["fruit"] == "banana"
    assert body["confidence"] == 0.97
    assert body["retrieval"]["method"] == "semantic"
    assert body["retrieval"]["model"] == "test/semantic-model"
    assert body["retrieval"]["documents"][0]["id"] == "banana_storage"
    assert body["retrieval"]["documents"][0]["score"] == 0.812345
    assert body["warnings"][0]["level"] == "warning"
    assert body["recommendation"] == "Inspect the fruit before eating."
    assert body["privacy"] == {
        "image_retained": False,
        "filename_retained": False,
    }
    assert "banana.png" not in response.text
    assert fake_agent.run_count == 1
    assert response.headers["x-ratelimit-limit"] == "30"
    assert response.headers["x-ratelimit-remaining"] == "29"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]
    with pytest.raises(ValueError, match="closed image"):
        fake_agent.last_image.getpixel((0, 0))


def test_analyze_withholds_tentative_uncertain_prediction():
    app = create_app(agent_factory=lambda: _UncertainAgent())
    with TestClient(app) as client:
        response = client.post("/api/v1/analyze", files=_upload(_image_bytes()))

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "uncertain_input"
    assert body["prediction"] is None
    assert body["confidence"] is None
    assert body["retrieval"] is None


@pytest.mark.parametrize(
    ("data", "content_type", "status_code", "error_code"),
    [
        (b"", "image/png", 400, "EMPTY_FILE"),
        (b"not-an-image", "image/png", 400, "INVALID_IMAGE"),
        (b"not-an-image", "text/plain", 415, "UNSUPPORTED_MEDIA_TYPE"),
    ],
)
def test_analyze_rejects_empty_invalid_and_unsupported_uploads(
    data,
    content_type,
    status_code,
    error_code,
):
    fake_agent = _FakeAgent()
    app = create_app(agent_factory=lambda: fake_agent)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyze",
            files=_upload(data, content_type=content_type),
        )

    assert response.status_code == status_code
    assert response.json()["error"]["code"] == error_code
    assert fake_agent.run_count == 0


def test_analyze_rejects_upload_above_byte_limit():
    fake_agent = _FakeAgent()
    app = create_app(agent_factory=lambda: fake_agent, max_upload_bytes=16)
    with TestClient(app) as client:
        response = client.post("/api/v1/analyze", files=_upload(_image_bytes()))

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert fake_agent.run_count == 0


def test_analyze_rejects_decoded_image_above_pixel_limit():
    fake_agent = _FakeAgent()
    app = create_app(agent_factory=lambda: fake_agent, max_image_pixels=8)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyze",
            files=_upload(_image_bytes(size=(3, 3))),
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"
    assert fake_agent.run_count == 0


def test_analyze_rejects_mismatched_declared_media_type():
    fake_agent = _FakeAgent()
    app = create_app(agent_factory=lambda: fake_agent)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyze",
            files=_upload(_image_bytes(image_format="JPEG"), content_type="image/png"),
        )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "MEDIA_TYPE_MISMATCH"
    assert fake_agent.run_count == 0


def test_analyze_returns_safe_error_without_internal_exception_details():
    failing_agent = _FailingAgent()
    app = create_app(agent_factory=lambda: failing_agent)
    with TestClient(app) as client:
        response = client.post("/api/v1/analyze", files=_upload(_image_bytes()))

    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "ANALYSIS_FAILED",
        "message": "FreshSense could not complete this analysis.",
    }
    assert "sensitive internal failure" not in response.text


def test_openapi_documents_versioned_endpoints_and_typed_contracts():
    app = create_app(agent_factory=lambda: _FakeAgent())
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    schema = response.json()
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/analyze" in schema["paths"]
    assert "/api/v1/metrics" in schema["paths"]
    analyze = schema["paths"]["/api/v1/analyze"]["post"]
    assert "multipart/form-data" in analyze["requestBody"]["content"]
    assert analyze["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/AnalyzeResponse"
    }
    assert analyze["responses"]["413"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse"
    }
