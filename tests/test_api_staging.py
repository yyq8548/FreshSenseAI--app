import json
import logging

from fastapi.testclient import TestClient
import pytest
from starlette.requests import Request as StarletteRequest

from api.app import create_app
from api.observability import JsonFormatter, request_id_from_header
from api.security import resolve_api_key
from tests.test_api import _FailingAgent, _FakeAgent, _image_bytes, _upload
from utils.startup import StartupValidationError


API_KEY = "staging-test-key-with-at-least-32-characters"


def test_required_api_key_fails_closed_when_missing(monkeypatch):
    monkeypatch.delenv("FRESHSENSE_API_KEY", raising=False)
    app = create_app(
        agent_factory=lambda: _FakeAgent(),
        require_api_key=True,
        api_key_file=None,
    )

    with pytest.raises(StartupValidationError, match="no key was configured"):
        with TestClient(app):
            pass


def test_weak_api_key_fails_closed():
    app = create_app(
        agent_factory=lambda: _FakeAgent(),
        require_api_key=True,
        api_key="too-short",
        api_key_file=None,
    )

    with pytest.raises(StartupValidationError, match="at least 32"):
        with TestClient(app):
            pass


def test_protected_routes_require_valid_api_key_but_health_remains_available():
    app = create_app(
        agent_factory=lambda: _FakeAgent(),
        require_api_key=True,
        api_key=API_KEY,
        api_key_file=None,
    )
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        missing = client.post("/api/v1/analyze", files=_upload(_image_bytes()))
        invalid = client.post(
            "/api/v1/analyze",
            files=_upload(_image_bytes()),
            headers={"X-API-Key": "x" * 40},
        )
        accepted = client.post(
            "/api/v1/analyze",
            files=_upload(_image_bytes()),
            headers={"X-API-Key": API_KEY},
        )
        metrics_missing = client.get("/api/v1/metrics")
        metrics = client.get(
            "/api/v1/metrics",
            headers={"X-API-Key": API_KEY},
        )

    assert health.status_code == 200
    assert health.json()["authentication_required"] is True
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert missing.json()["error"]["code"] == "INVALID_API_KEY"
    assert missing.headers["www-authenticate"] == "APIKey"
    assert accepted.status_code == 200
    assert metrics_missing.status_code == 401
    assert metrics.status_code == 200


def test_unauthenticated_analysis_is_rejected_before_multipart_parsing(monkeypatch):
    async def fail_if_parsed(_request):
        raise AssertionError("multipart parsing should not run before authentication")

    monkeypatch.setattr(StarletteRequest, "_get_form", fail_if_parsed)
    app = create_app(
        agent_factory=lambda: _FakeAgent(),
        require_api_key=True,
        api_key=API_KEY,
        api_key_file=None,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyze",
            files=_upload(_image_bytes()),
        )

    assert response.status_code == 401


def test_oversized_declared_request_is_rejected_before_multipart_parsing(monkeypatch):
    async def fail_if_parsed(_request):
        raise AssertionError("oversized request should not be parsed")

    monkeypatch.setattr(StarletteRequest, "_get_form", fail_if_parsed)
    app = create_app(
        agent_factory=lambda: _FakeAgent(),
        api_key=API_KEY,
        api_key_file=None,
        max_upload_bytes=100,
    )
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/analyze",
            content=b"x",
            headers={
                "X-API-Key": API_KEY,
                "Content-Type": "multipart/form-data; boundary=test",
                "Content-Length": str(100 + 64 * 1024 + 1),
            },
        )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "REQUEST_TOO_LARGE"


def test_rate_limiter_returns_headers_and_rejects_excess_analysis():
    app = create_app(
        agent_factory=lambda: _FakeAgent(),
        rate_limit_per_minute=2,
    )
    with TestClient(app) as client:
        first = client.post("/api/v1/analyze", files=_upload(_image_bytes()))
        second = client.post("/api/v1/analyze", files=_upload(_image_bytes()))
        third = client.post("/api/v1/analyze", files=_upload(_image_bytes()))

    assert first.status_code == 200
    assert first.headers["x-ratelimit-remaining"] == "1"
    assert second.status_code == 200
    assert second.headers["x-ratelimit-remaining"] == "0"
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert third.headers["retry-after"]
    assert third.headers["x-ratelimit-limit"] == "2"


def test_request_id_security_headers_and_trusted_hosts():
    app = create_app(agent_factory=lambda: _FakeAgent())
    with TestClient(app) as client:
        accepted_id = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "stage-request-123"},
        )
        replaced_id = client.get(
            "/api/v1/health",
            headers={"X-Request-ID": "x" * 80},
        )
        bad_host = client.get(
            "/api/v1/health",
            headers={"Host": "attacker.example"},
        )

    assert accepted_id.headers["x-request-id"] == "stage-request-123"
    assert replaced_id.headers["x-request-id"] != "x" * 80
    assert len(replaced_id.headers["x-request-id"]) == 32
    assert accepted_id.headers["content-security-policy"].startswith("default-src")
    assert accepted_id.headers["referrer-policy"] == "no-referrer"
    assert bad_host.status_code == 400


def test_cors_allows_only_configured_origin():
    app = create_app(
        agent_factory=lambda: _FakeAgent(),
        cors_origins=("https://staging.example",),
    )
    with TestClient(app) as client:
        allowed = client.options(
            "/api/v1/analyze",
            headers={
                "Origin": "https://staging.example",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-API-Key,Content-Type",
            },
        )
        denied = client.get(
            "/api/v1/health",
            headers={"Origin": "https://attacker.example"},
        )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://staging.example"
    assert "access-control-allow-origin" not in denied.headers


def test_wildcard_host_and_cors_configuration_are_rejected():
    with pytest.raises(ValueError, match="explicit hostnames"):
        create_app(agent_factory=lambda: _FakeAgent(), allowed_hosts=("*",))
    with pytest.raises(ValueError, match="Wildcard CORS"):
        create_app(agent_factory=lambda: _FakeAgent(), cors_origins=("*",))


def test_metrics_report_success_and_failure_without_exposing_secrets():
    app = create_app(
        agent_factory=lambda: _FakeAgent(),
        api_key=API_KEY,
        api_key_file=None,
    )
    with TestClient(app) as client:
        client.post(
            "/api/v1/analyze",
            files=_upload(_image_bytes()),
            headers={"X-API-Key": API_KEY},
        )
        metrics = client.get(
            "/api/v1/metrics",
            headers={"X-API-Key": API_KEY},
        )

    body = metrics.json()
    assert metrics.status_code == 200
    assert body["request_count"] >= 1
    assert body["analysis_count"] == 1
    assert body["analysis_failures"] == 0
    assert body["average_analysis_seconds"] is not None
    assert API_KEY not in metrics.text

    failing_app = create_app(
        agent_factory=lambda: _FailingAgent(),
        api_key=API_KEY,
        api_key_file=None,
    )
    with TestClient(failing_app) as client:
        failure = client.post(
            "/api/v1/analyze",
            files=_upload(_image_bytes()),
            headers={"X-API-Key": API_KEY},
        )
        failed_metrics = client.get(
            "/api/v1/metrics",
            headers={"X-API-Key": API_KEY},
        )

    assert failure.status_code == 500
    assert failed_metrics.json()["analysis_failures"] == 1


def test_api_key_secret_file_takes_precedence(tmp_path):
    secret_file = tmp_path / "api_key"
    secret_file.write_text(API_KEY, encoding="utf-8")

    resolved = resolve_api_key(
        explicit_value=None,
        environment_value="environment-key-that-is-long-enough-12345",
        secret_file=str(secret_file),
    )

    assert resolved == API_KEY


def test_json_formatter_is_structured_and_request_ids_are_sanitized():
    record = logging.LogRecord(
        name="freshsense.api",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request complete",
        args=(),
        exc_info=None,
    )
    record.event = "request_completed"
    record.request_id = "request-42"
    record.status_code = 200

    payload = json.loads(JsonFormatter().format(record))

    assert payload["event"] == "request_completed"
    assert payload["request_id"] == "request-42"
    assert payload["status_code"] == 200
    assert request_id_from_header("safe.id-1") == "safe.id-1"
    assert request_id_from_header("not safe") != "not safe"


def test_openapi_declares_api_key_security_and_operational_errors():
    app = create_app(
        agent_factory=lambda: _FakeAgent(),
        api_key=API_KEY,
        api_key_file=None,
    )
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["FreshSenseApiKey"] == {
        "type": "apiKey",
        "description": "FreshSense API key supplied through the X-API-Key header.",
        "in": "header",
        "name": "X-API-Key",
    }
    analyze = schema["paths"]["/api/v1/analyze"]["post"]
    assert {"FreshSenseApiKey": []} in analyze["security"]
    assert "401" in analyze["responses"]
    assert "429" in analyze["responses"]
