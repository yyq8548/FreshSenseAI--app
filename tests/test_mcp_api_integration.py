import json
from urllib.parse import urlsplit

from fastapi.testclient import TestClient

from api.app import create_app
from freshsense_mcp.client import FreshSenseApiClient, HttpResult
from freshsense_mcp.config import MCPConfig
from tests.test_api import _FakeAgent, _image_bytes, _upload


FIRST_KEY = "first-mcp-workspace-key-with-32-characters"
SECOND_KEY = "second-mcp-workspace-key-with-32-characters"


def test_mcp_client_preserves_api_workspace_isolation(tmp_path):
    database = tmp_path / "mcp-workspaces.db"
    first_app = create_app(
        agent_factory=lambda: _FakeAgent(),
        api_key=FIRST_KEY,
        api_key_file=None,
        saas_database_path=database,
    )
    second_app = create_app(
        agent_factory=lambda: _FakeAgent(),
        api_key=SECOND_KEY,
        api_key_file=None,
        saas_database_path=database,
    )

    with TestClient(first_app) as first, TestClient(second_app) as second:
        first_response = first.post(
            "/api/v1/inspections/analyze",
            headers={"X-API-Key": FIRST_KEY},
            data={"batch_reference": "FIRST-WORKSPACE"},
            files=_upload(_image_bytes()),
        )
        second_response = second.post(
            "/api/v1/inspections/analyze",
            headers={"X-API-Key": SECOND_KEY},
            data={"batch_reference": "SECOND-WORKSPACE"},
            files=_upload(_image_bytes()),
        )
        assert first_response.status_code == 200
        assert second_response.status_code == 200

        def sender(request, timeout_seconds):
            parsed = urlsplit(request.full_url)
            response = first.get(
                f"{parsed.path}?{parsed.query}",
                headers=dict(request.header_items()),
            )
            return HttpResult(
                status_code=response.status_code,
                body=json.dumps(response.json()).encode("utf-8"),
            )

        mcp_client = FreshSenseApiClient(
            MCPConfig(api_url="https://freshsense.test", api_key=FIRST_KEY),
            sender=sender,
        )
        result = mcp_client.get_recent_inspections(limit=10)

    assert result["count"] == 1
    assert result["inspections"][0]["batch_reference"] == "FIRST-WORKSPACE"
    assert "SECOND-WORKSPACE" not in json.dumps(result)
