import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.request import Request

import pytest

from freshsense_mcp.client import FreshSenseApiClient, FreshSenseMCPError, HttpResult
from freshsense_mcp.config import MCPConfig, MCPConfigurationError


def _payload():
    return {
        "count": 1,
        "inspections": [
            {
                "inspection_id": "inspection-1",
                "created_at_utc": "2026-07-21T12:00:00+00:00",
                "location_name": "Main store",
                "batch_reference": "PO-42",
                "operator_note": "must not leave API boundary",
                "decision": "accepted",
                "analysis_status": "complete",
                "predicted_display_name": "Fresh Apple",
                "fruit": "apple",
                "predicted_freshness": "fresh",
                "confidence": 0.991,
                "risk_level": "low",
                "review_status": "pending",
                "reviewed_outcome": None,
                "review_note": "must not leave API boundary",
                "image_retained": False,
            }
        ],
    }


def test_config_requires_one_credential():
    with pytest.raises(MCPConfigurationError):
        MCPConfig.from_env({"FRESHSENSE_MCP_API_URL": "https://api.example"})
    with pytest.raises(MCPConfigurationError):
        MCPConfig.from_env(
            {
                "FRESHSENSE_MCP_API_URL": "https://api.example",
                "FRESHSENSE_MCP_API_KEY": "key",
                "FRESHSENSE_MCP_BEARER_TOKEN": "token",
            }
        )


def test_config_rejects_non_http_api_url():
    with pytest.raises(MCPConfigurationError):
        MCPConfig.from_env(
            {
                "FRESHSENSE_MCP_API_URL": "file:///tmp/data",
                "FRESHSENSE_MCP_API_KEY": "key",
            }
        )


@pytest.mark.parametrize(
    "credentials",
    [
        {},
        {"api_key": "key", "bearer_token": "token"},
    ],
)
def test_config_constructor_requires_exactly_one_credential(credentials):
    with pytest.raises(MCPConfigurationError, match="exactly one"):
        MCPConfig(api_url="https://api.example", **credentials)


def test_recent_inspections_uses_get_auth_and_minimizes_fields():
    captured: list[Request] = []

    def sender(request: Request, timeout_seconds: float) -> HttpResult:
        captured.append(request)
        assert timeout_seconds == 10.0
        return HttpResult(status_code=200, body=json.dumps(_payload()).encode("utf-8"))

    client = FreshSenseApiClient(
        MCPConfig(api_url="https://api.example", api_key="secret"),
        sender=sender,
    )
    result = client.get_recent_inspections(limit=7, review_status="pending")

    assert len(captured) == 1
    request = captured[0]
    assert request.method == "GET"
    assert request.full_url == (
        "https://api.example/api/v1/inspections?limit=7&review_status=pending"
    )
    assert request.get_header("X-api-key") == "secret"
    assert request.get_header("Authorization") is None
    assert result["count"] == 1
    assert result["inspections"][0]["inspection_id"] == "inspection-1"
    assert "operator_note" not in result["inspections"][0]
    assert "review_note" not in result["inspections"][0]
    assert "image_retained" not in result["inspections"][0]


def test_recent_inspections_uses_bearer_auth_without_api_key():
    captured: list[Request] = []

    def sender(request: Request, timeout_seconds: float) -> HttpResult:
        captured.append(request)
        return HttpResult(status_code=200, body=json.dumps(_payload()).encode("utf-8"))

    client = FreshSenseApiClient(
        MCPConfig(api_url="https://api.example", bearer_token="bearer-secret"),
        sender=sender,
    )
    client.get_recent_inspections()

    assert captured[0].get_header("Authorization") == "Bearer bearer-secret"
    assert captured[0].get_header("X-api-key") is None


@pytest.mark.parametrize("limit", [0, 51])
def test_recent_inspections_rejects_invalid_limit_before_request(limit):
    called = False

    def sender(request: Request, timeout_seconds: float) -> HttpResult:
        nonlocal called
        called = True
        raise AssertionError("network must not be called")

    client = FreshSenseApiClient(
        MCPConfig(api_url="https://api.example", api_key="secret"),
        sender=sender,
    )
    with pytest.raises(ValueError, match="between 1 and 50"):
        client.get_recent_inspections(limit=limit)
    assert called is False


def test_recent_inspections_rejects_invalid_review_status_before_request():
    client = FreshSenseApiClient(
        MCPConfig(api_url="https://api.example", api_key="secret"),
        sender=lambda request, timeout: (_ for _ in ()).throw(
            AssertionError("network must not be called")
        ),
    )
    with pytest.raises(ValueError, match="review_status"):
        client.get_recent_inspections(review_status="open")


@pytest.mark.parametrize("status_code", [401, 403])
def test_recent_inspections_redacts_credentials_from_auth_errors(status_code):
    secret = "credential-that-must-not-appear"
    client = FreshSenseApiClient(
        MCPConfig(api_url="https://api.example", bearer_token=secret),
        sender=lambda request, timeout: HttpResult(status_code=status_code, body=b"denied"),
    )
    with pytest.raises(FreshSenseMCPError) as caught:
        client.get_recent_inspections()
    assert "authentication or authorization failed" in str(caught.value).lower()
    assert secret not in str(caught.value)


def test_recent_inspections_rejects_malformed_api_envelope():
    client = FreshSenseApiClient(
        MCPConfig(api_url="https://api.example", api_key="secret"),
        sender=lambda request, timeout: HttpResult(
            status_code=200,
            body=b'{"inspections": "not-a-list"}',
        ),
    )
    with pytest.raises(FreshSenseMCPError, match="unexpected response"):
        client.get_recent_inspections()


def test_default_sender_rejects_redirect_without_forwarding_credentials():
    secret = "redirect-secret-that-must-not-leave-origin"
    captured_credentials: list[str | None] = []

    class TargetHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            captured_credentials.append(self.headers.get("X-API-Key"))
            body = json.dumps(_payload()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    target = ThreadingHTTPServer(("127.0.0.1", 0), TargetHandler)

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302)
            self.send_header(
                "Location",
                f"http://127.0.0.1:{target.server_port}/credential-target",
            )
            self.end_headers()

        def log_message(self, format, *args):
            return

    source = ThreadingHTTPServer(("127.0.0.1", 0), RedirectHandler)
    target_thread = Thread(target=target.serve_forever, daemon=True)
    source_thread = Thread(target=source.serve_forever, daemon=True)
    target_thread.start()
    source_thread.start()
    try:
        client = FreshSenseApiClient(
            MCPConfig(
                api_url=f"http://127.0.0.1:{source.server_port}",
                api_key=secret,
            )
        )
        with pytest.raises(FreshSenseMCPError, match="redirect"):
            client.get_recent_inspections()
        assert captured_credentials == []
    finally:
        source.shutdown()
        target.shutdown()
        source.server_close()
        target.server_close()
        source_thread.join(timeout=5)
        target_thread.join(timeout=5)
