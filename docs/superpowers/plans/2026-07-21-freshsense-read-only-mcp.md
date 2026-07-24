# FreshSense Read-Only MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a small `mcp-use` server that lets an authenticated MCP client retrieve recent FreshSense inspection metadata without exposing any write capability.

**Architecture:** A standalone `freshsense_mcp` package will translate one typed MCP tool call into the existing authenticated `GET /api/v1/inspections` REST request. The REST API remains the authentication, authorization, and workspace-isolation boundary; the MCP layer validates and minimizes the returned data. The optional MCP runtime is isolated from the main API dependencies.

**Tech Stack:** Python 3.11, `mcp-use==1.7.0`, MCP Python SDK types, Python standard-library HTTP client, pytest 8.4.1, existing FastAPI test utilities.

## Global Constraints

- Expose exactly one business tool: `get_recent_inspections`.
- The tool is read-only and non-destructive; it must not call upload, analysis, review, task, approval, or notification endpoints.
- Use only `GET /api/v1/inspections` as the FreshSense data source.
- Accept `limit` from 1 through 50 and optional review status `pending`, `confirmed`, `corrected`, or `dismissed`.
- Return only the approved fields named in the design spec; omit operator notes, review notes, photos, and filenames.
- Require exactly one credential: API key or OAuth bearer token.
- Never log, return, commit, or interpolate credentials into errors.
- Disable mcp-use anonymized telemetry by default for this FreshSense process.
- Keep the MCP dependency out of `requirements.txt` and `requirements-api.txt`.
- Target `mcp-use==1.7.0` and Python 3.11 or newer.

---

### Task 1: Configuration and minimized REST client

**Files:**
- Create: `freshsense_mcp/__init__.py`
- Create: `freshsense_mcp/config.py`
- Create: `freshsense_mcp/client.py`
- Create: `tests/test_mcp_client.py`

**Interfaces:**
- Produces: `MCPConfig.from_env(environ: Mapping[str, str] | None = None) -> MCPConfig`
- Produces: `FreshSenseApiClient(config: MCPConfig, sender: RequestSender | None = None)`
- Produces: `FreshSenseApiClient.get_recent_inspections(limit: int = 10, review_status: str | None = None) -> dict[str, Any]`
- Produces: `MCPConfigurationError` and `FreshSenseMCPError`

- [ ] **Step 1: Write the failing client and configuration tests**

Create `tests/test_mcp_client.py` with tests that define the required public behavior before the package exists:

```python
import json
from urllib.request import Request

import pytest

from freshsense_mcp.client import FreshSenseApiClient, HttpResult
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
    with pytest.raises(Exception) as caught:
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
    with pytest.raises(Exception, match="unexpected response"):
        client.get_recent_inspections()
```

- [ ] **Step 2: Run the tests and verify the RED state**

Run:

```powershell
py -3.11 -m pytest tests/test_mcp_client.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'freshsense_mcp'`.

- [ ] **Step 3: Implement configuration and the REST client**

Create `freshsense_mcp/__init__.py`:

```python
"""Read-only Model Context Protocol integration for FreshSense."""

from freshsense_mcp.client import FreshSenseApiClient, FreshSenseMCPError
from freshsense_mcp.config import MCPConfig, MCPConfigurationError

__all__ = [
    "FreshSenseApiClient",
    "FreshSenseMCPError",
    "MCPConfig",
    "MCPConfigurationError",
]
```

Create `freshsense_mcp/config.py`:

```python
"""Environment configuration for the standalone FreshSense MCP gateway."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping
from urllib.parse import urlparse


class MCPConfigurationError(RuntimeError):
    """Raised when the MCP gateway configuration is unsafe or incomplete."""


@dataclass(frozen=True)
class MCPConfig:
    api_url: str
    api_key: str | None = None
    bearer_token: str | None = None
    timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "MCPConfig":
        values = os.environ if environ is None else environ
        api_url = values.get("FRESHSENSE_MCP_API_URL", "").strip().rstrip("/")
        api_key = values.get("FRESHSENSE_MCP_API_KEY", "").strip() or None
        bearer_token = values.get("FRESHSENSE_MCP_BEARER_TOKEN", "").strip() or None

        parsed = urlparse(api_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise MCPConfigurationError(
                "FRESHSENSE_MCP_API_URL must be an absolute HTTP or HTTPS URL."
            )
        if (api_key is None) == (bearer_token is None):
            raise MCPConfigurationError(
                "Configure exactly one FreshSense MCP credential."
            )
        return cls(api_url=api_url, api_key=api_key, bearer_token=bearer_token)
```

Create `freshsense_mcp/client.py`:

```python
"""Minimal, credential-safe client for FreshSense inspection metadata."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from freshsense_mcp.config import MCPConfig


REVIEW_STATUSES = frozenset({"pending", "confirmed", "corrected", "dismissed"})
INSPECTION_FIELDS = (
    "inspection_id",
    "created_at_utc",
    "location_name",
    "batch_reference",
    "decision",
    "analysis_status",
    "predicted_display_name",
    "fruit",
    "predicted_freshness",
    "confidence",
    "risk_level",
    "review_status",
    "reviewed_outcome",
)


class FreshSenseMCPError(RuntimeError):
    """Raised for safe-to-display MCP integration failures."""


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    body: bytes


RequestSender = Callable[[Request, float], HttpResult]


def _send(request: Request, timeout_seconds: float) -> HttpResult:
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return HttpResult(status_code=response.status, body=response.read())
    except HTTPError as exc:
        return HttpResult(status_code=exc.code, body=b"")
    except (URLError, TimeoutError, OSError) as exc:
        raise FreshSenseMCPError("FreshSense API is unavailable.") from exc


class FreshSenseApiClient:
    def __init__(
        self,
        config: MCPConfig,
        *,
        sender: RequestSender | None = None,
    ) -> None:
        self._config = config
        self._sender = sender or _send

    def get_recent_inspections(
        self,
        *,
        limit: int = 10,
        review_status: str | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50.")
        if review_status is not None and review_status not in REVIEW_STATUSES:
            raise ValueError("review_status is invalid.")

        params: dict[str, str | int] = {"limit": limit}
        if review_status is not None:
            params["review_status"] = review_status
        url = f"{self._config.api_url}/api/v1/inspections?{urlencode(params)}"
        headers = {"Accept": "application/json"}
        if self._config.api_key is not None:
            headers["X-API-Key"] = self._config.api_key
        else:
            headers["Authorization"] = f"Bearer {self._config.bearer_token}"

        result = self._sender(Request(url, headers=headers, method="GET"), self._config.timeout_seconds)
        if result.status_code in {401, 403}:
            raise FreshSenseMCPError(
                "FreshSense authentication or authorization failed."
            )
        if result.status_code >= 400:
            raise FreshSenseMCPError(
                f"FreshSense API returned HTTP {result.status_code}."
            )
        try:
            payload = json.loads(result.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FreshSenseMCPError("FreshSense API returned an unexpected response.") from exc
        if not isinstance(payload, dict) or not isinstance(payload.get("inspections"), list):
            raise FreshSenseMCPError("FreshSense API returned an unexpected response.")

        minimized = []
        for value in payload["inspections"]:
            if not isinstance(value, dict):
                raise FreshSenseMCPError("FreshSense API returned an unexpected response.")
            minimized.append({field: value.get(field) for field in INSPECTION_FIELDS})
        return {"count": len(minimized), "inspections": minimized}
```

- [ ] **Step 4: Run the focused tests and verify GREEN**

Run:

```powershell
py -3.11 -m pytest tests/test_mcp_client.py -q
```

Expected: all tests in `test_mcp_client.py` pass.

- [ ] **Step 5: Commit the client boundary**

```powershell
git add freshsense_mcp tests/test_mcp_client.py
git commit -m "feat: add read-only FreshSense MCP API client"
```

---

### Task 2: Prove existing API workspace isolation through the MCP client

**Files:**
- Create: `tests/test_mcp_api_integration.py`

**Interfaces:**
- Consumes: `FreshSenseApiClient`, `MCPConfig`, and the existing `create_app` factory.
- Proves: one MCP credential can observe only the workspace already selected by the FreshSense API.

- [ ] **Step 1: Write the integration test before changing the adapter**

Create `tests/test_mcp_api_integration.py`:

```python
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
        first.post(
            "/api/v1/inspections/analyze",
            headers={"X-API-Key": FIRST_KEY},
            data={"batch_reference": "FIRST-WORKSPACE"},
            files=_upload(_image_bytes()),
        )
        second.post(
            "/api/v1/inspections/analyze",
            headers={"X-API-Key": SECOND_KEY},
            data={"batch_reference": "SECOND-WORKSPACE"},
            files=_upload(_image_bytes()),
        )

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
```

- [ ] **Step 2: Run the integration test**

Run:

```powershell
py -3.11 -m pytest tests/test_mcp_api_integration.py -q
```

Expected: PASS. If header normalization reveals an adapter defect, first confirm the failure is caused by the MCP HTTP boundary, then make the smallest client correction and rerun.

- [ ] **Step 3: Commit the workspace-isolation proof**

```powershell
git add tests/test_mcp_api_integration.py freshsense_mcp/client.py
git commit -m "test: prove MCP inspection workspace isolation"
```

---

### Task 3: Register the typed read-only mcp-use tool

**Files:**
- Create: `requirements-mcp.txt`
- Create: `requirements-mcp-dev.txt`
- Create: `freshsense_mcp/server.py`
- Create: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `FreshSenseApiClient.get_recent_inspections` and `MCPConfig.from_env`.
- Produces: `create_server(api_client: FreshSenseApiClient | None = None) -> MCPServer`
- Produces: CLI entry point `python -m freshsense_mcp.server`.

- [ ] **Step 1: Add isolated MCP dependency manifests**

Create `requirements-mcp.txt`:

```text
# Optional standalone MCP gateway runtime. Keep separate from the API runtime.
mcp-use==1.7.0
```

Create `requirements-mcp-dev.txt`:

```text
-r requirements-mcp.txt
pytest==8.4.1
```

Create an isolated development environment and install it:

```powershell
py -3.11 -m venv .mcp-venv
& .\.mcp-venv\Scripts\python.exe -m pip install -r requirements-mcp-dev.txt
```

- [ ] **Step 2: Write the failing server registration tests**

Create `tests/test_mcp_server.py`:

```python
import asyncio

from freshsense_mcp.server import create_server


class FakeApiClient:
    def __init__(self):
        self.calls = []

    def get_recent_inspections(self, *, limit=10, review_status=None):
        self.calls.append((limit, review_status))
        return {
            "count": 1,
            "inspections": [{"inspection_id": "inspection-1"}],
        }


def test_server_exposes_one_typed_read_only_tool():
    server = create_server(api_client=FakeApiClient())
    tools = asyncio.run(server.list_tools())

    assert [tool.name for tool in tools] == ["get_recent_inspections"]
    tool = tools[0]
    assert "recent FreshSense inspection" in tool.description
    assert tool.inputSchema["properties"]["limit"]["minimum"] == 1
    assert tool.inputSchema["properties"]["limit"]["maximum"] == 50
    assert tool.annotations.readOnlyHint is True
    assert tool.annotations.destructiveHint is False
    assert tool.annotations.openWorldHint is True


def test_tool_delegates_to_the_minimized_api_client():
    api_client = FakeApiClient()
    server = create_server(api_client=api_client)

    result = asyncio.run(
        server.call_tool(
            "get_recent_inspections",
            {"limit": 4, "review_status": "pending"},
        )
    )

    assert api_client.calls == [(4, "pending")]
    assert result["count"] == 1
    assert result["inspections"][0]["inspection_id"] == "inspection-1"
```

- [ ] **Step 3: Run the tests and verify the RED state**

Run:

```powershell
$env:MCP_USE_ANONYMIZED_TELEMETRY='false'
& .\.mcp-venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -q
```

Expected: collection fails because `freshsense_mcp.server` does not exist.

- [ ] **Step 4: Implement the server factory and CLI**

Create `freshsense_mcp/server.py`:

```python
"""Standalone read-only MCP server for FreshSense inspection metadata."""

from __future__ import annotations

import argparse
import os
from typing import Annotated, Any, Literal

os.environ.setdefault("MCP_USE_ANONYMIZED_TELEMETRY", "false")

from mcp.types import ToolAnnotations
from mcp_use import MCPServer
from pydantic import Field

from freshsense_mcp.client import FreshSenseApiClient
from freshsense_mcp.config import MCPConfig
from utils.version import APP_VERSION


ReviewStatus = Literal["pending", "confirmed", "corrected", "dismissed"]


def create_server(
    api_client: FreshSenseApiClient | None = None,
) -> MCPServer:
    active_client = api_client or FreshSenseApiClient(MCPConfig.from_env())
    server = MCPServer(
        name="FreshSense Read-Only Inspections",
        version=APP_VERSION,
        instructions=(
            "Retrieve recent FreshSense inspection metadata. This server is "
            "read-only and cannot analyze images or change inspection records."
        ),
        debug=False,
        dns_rebinding_protection=True,
    )

    @server.tool(
        name="get_recent_inspections",
        title="Get recent FreshSense inspections",
        description=(
            "Retrieve recent FreshSense inspection metadata from the authenticated "
            "workspace without returning photos or free-form staff notes."
        ),
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        ),
        structured_output=True,
    )
    def get_recent_inspections(
        limit: Annotated[
            int,
            Field(
                ge=1,
                le=50,
                description="Maximum number of newest inspections to return.",
            ),
        ] = 10,
        review_status: Annotated[
            ReviewStatus | None,
            Field(description="Optional human-review status filter."),
        ] = None,
    ) -> dict[str, Any]:
        return active_client.get_recent_inspections(
            limit=limit,
            review_status=review_status,
        )

    return server


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="stdio",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument("--debug", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    create_server().run(
        transport=args.transport,
        host=args.host,
        port=args.port,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run:

```powershell
$env:MCP_USE_ANONYMIZED_TELEMETRY='false'
& .\.mcp-venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -q
```

Expected: both tests pass and no telemetry network warning appears.

- [ ] **Step 6: Commit the mcp-use server**

```powershell
git add requirements-mcp.txt requirements-mcp-dev.txt freshsense_mcp/server.py tests/test_mcp_server.py
git commit -m "feat: expose recent inspections through mcp-use"
```

---

### Task 4: Add an end-to-end mcp-use client smoke test

**Files:**
- Create: `scripts/smoke_mcp_integration.py`
- Create: `tests/test_mcp_smoke.py`

**Interfaces:**
- Consumes: `python -m freshsense_mcp.server --transport stdio`.
- Produces: `run_smoke() -> dict[str, Any]`, which discovers and calls the tool through `mcp_use.MCPClient`.

- [ ] **Step 1: Write the failing smoke contract**

Create `tests/test_mcp_smoke.py`:

```python
import asyncio

from scripts.smoke_mcp_integration import run_smoke


def test_mcp_use_client_discovers_and_calls_freshsense_tool():
    result = asyncio.run(run_smoke())

    assert result["tool_names"] == ["get_recent_inspections"]
    assert result["structured_content"]["count"] == 1
    assert result["structured_content"]["inspections"][0]["inspection_id"] == "smoke-1"
    assert "operator_note" not in result["structured_content"]["inspections"][0]
```

- [ ] **Step 2: Run the smoke test and verify the RED state**

Run:

```powershell
$env:MCP_USE_ANONYMIZED_TELEMETRY='false'
& .\.mcp-venv\Scripts\python.exe -m pytest tests/test_mcp_smoke.py -q
```

Expected: collection fails because `scripts.smoke_mcp_integration` does not exist.

- [ ] **Step 3: Implement a self-contained MCP protocol smoke**

Create `scripts/smoke_mcp_integration.py` with a localhost-only stub FreshSense API, an MCP stdio subprocess, tool discovery, and tool invocation:

```python
"""Exercise the FreshSense MCP server through the mcp-use client."""

from __future__ import annotations

import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from threading import Thread
from typing import Any
import sys

os.environ.setdefault("MCP_USE_ANONYMIZED_TELEMETRY", "false")

from mcp_use import MCPClient


SMOKE_KEY = "freshsense-mcp-smoke-key"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if not self.path.startswith("/api/v1/inspections?"):
            self.send_error(404)
            return
        if self.headers.get("X-API-Key") != SMOKE_KEY:
            self.send_error(401)
            return
        payload = {
            "count": 1,
            "inspections": [
                {
                    "inspection_id": "smoke-1",
                    "created_at_utc": "2026-07-21T12:00:00+00:00",
                    "location_name": "Smoke store",
                    "batch_reference": "SMOKE-BATCH",
                    "operator_note": "must be omitted",
                    "decision": "accepted",
                    "analysis_status": "complete",
                    "predicted_display_name": "Fresh Apple",
                    "fruit": "apple",
                    "predicted_freshness": "fresh",
                    "confidence": 0.99,
                    "risk_level": "low",
                    "review_status": "pending",
                    "reviewed_outcome": None,
                }
            ],
        }
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


async def run_smoke() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    api = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = Thread(target=api.serve_forever, daemon=True)
    thread.start()

    child_env = dict(os.environ)
    child_env.update(
        {
            "FRESHSENSE_MCP_API_URL": f"http://127.0.0.1:{api.server_port}",
            "FRESHSENSE_MCP_API_KEY": SMOKE_KEY,
            "FRESHSENSE_MCP_BEARER_TOKEN": "",
            "MCP_USE_ANONYMIZED_TELEMETRY": "false",
            "PYTHONPATH": str(root),
        }
    )
    client = MCPClient.from_dict(
        {
            "mcpServers": {
                "freshsense": {
                    "command": sys.executable,
                    "args": [
                        "-m",
                        "freshsense_mcp.server",
                        "--transport",
                        "stdio",
                    ],
                    "env": child_env,
                }
            }
        }
    )
    try:
        session = await client.create_session("freshsense")
        if session is None:
            raise RuntimeError("mcp-use did not create the FreshSense session.")
        tools = await session.list_tools()
        result = await session.call_tool("get_recent_inspections", {"limit": 3})
        return {
            "tool_names": [tool.name for tool in tools],
            "structured_content": result.structuredContent,
        }
    finally:
        await client.close_all_sessions()
        api.shutdown()
        api.server_close()
        thread.join(timeout=5)


if __name__ == "__main__":
    value = asyncio.run(run_smoke())
    print(json.dumps(value, indent=2))
```

- [ ] **Step 4: Run the protocol test and verify GREEN**

Run:

```powershell
$env:MCP_USE_ANONYMIZED_TELEMETRY='false'
& .\.mcp-venv\Scripts\python.exe -m pytest tests/test_mcp_smoke.py -q
& .\.mcp-venv\Scripts\python.exe scripts/smoke_mcp_integration.py
```

Expected: pytest passes; the script prints one discovered tool and one minimized `smoke-1` inspection.

- [ ] **Step 5: Commit the protocol smoke**

```powershell
git add scripts/smoke_mcp_integration.py tests/test_mcp_smoke.py
git commit -m "test: exercise FreshSense through mcp-use client"
```

---

### Task 5: Documentation, README, and Manufact application wording

**Files:**
- Create: `docs/MCP_INTEGRATION.md`
- Modify: `README.md`

**Interfaces:**
- Documents: installation, credentials, stdio, streamable HTTP, Inspector, client smoke, output fields, and security boundaries.
- Delivers: a copy-ready Manufact application paragraph in the final handoff, not in the public repository.

- [ ] **Step 1: Write the documentation acceptance test**

Add `tests/test_mcp_documentation.py`:

```python
from pathlib import Path


def test_mcp_guide_documents_reproducible_read_only_usage():
    text = Path("docs/MCP_INTEGRATION.md").read_text(encoding="utf-8")
    required = (
        "mcp-use==1.7.0",
        "get_recent_inspections",
        "FRESHSENSE_MCP_API_URL",
        "FRESHSENSE_MCP_API_KEY",
        "FRESHSENSE_MCP_BEARER_TOKEN",
        "MCP_USE_ANONYMIZED_TELEMETRY",
        "--transport stdio",
        "--transport streamable-http",
        "/inspector",
        "does not replace API authorization",
    )
    assert all(value in text for value in required)


def test_readme_links_the_optional_mcp_guide():
    text = Path("README.md").read_text(encoding="utf-8")
    assert "[read-only MCP integration](docs/MCP_INTEGRATION.md)" in text
```

- [ ] **Step 2: Run the documentation tests and verify RED**

Run:

```powershell
py -3.11 -m pytest tests/test_mcp_documentation.py -q
```

Expected: collection or assertions fail because the guide and README link do not exist.

- [ ] **Step 3: Write the guide and README paragraph**

`docs/MCP_INTEGRATION.md` must include these exact runnable commands:

```powershell
py -3.11 -m venv .mcp-venv
& .\.mcp-venv\Scripts\python.exe -m pip install -r requirements-mcp.txt
$env:FRESHSENSE_MCP_API_URL='http://127.0.0.1:8000'
$env:FRESHSENSE_MCP_API_KEY='<local-development-key>'
$env:MCP_USE_ANONYMIZED_TELEMETRY='false'
& .\.mcp-venv\Scripts\python.exe -m freshsense_mcp.server --transport stdio
```

It must also document the HTTP Inspector workflow:

```powershell
& .\.mcp-venv\Scripts\python.exe -m freshsense_mcp.server `
  --transport streamable-http --host 127.0.0.1 --port 8010 --debug
```

The guide must explain that `/inspector` and `/mcp` are local development endpoints, only one credential variable may be configured, the MCP tool returns minimized metadata, `readOnlyHint` communicates intent to clients but does not replace API authorization, and the feature is not a public unauthenticated endpoint.

Add this paragraph under `README.md` section `Technology and AI`:

```markdown
An optional [read-only MCP integration](docs/MCP_INTEGRATION.md) uses
`mcp-use` to expose recent workspace inspection metadata through one typed
tool. It calls the existing authenticated REST API, preserves workspace
isolation, omits photos and free-form staff notes, and provides no mutation
capability. The MCP server is a developer integration, not a public
unauthenticated endpoint.
```

- [ ] **Step 4: Run the documentation tests and verify GREEN**

Run:

```powershell
py -3.11 -m pytest tests/test_mcp_documentation.py -q
```

Expected: both tests pass.

- [ ] **Step 5: Prepare the updated Manufact application wording**

Use this copy after the protocol smoke has passed:

```text
Hi Manufact team,

The part of this role that caught my attention is that your Developer Advocate is expected to build, not just talk about the product. I am an early-career AI software engineer. I built FreshSense, a human-reviewed AI product now used by a local shop, and a cloud-connected fish feeder that I delivered to 10 other reef hobbyists and still support.

MCP interests me because it gives AI products a reusable way to work with outside tools. To try the SDK, I built a read-only FreshSense MCP server with mcp-use that retrieves recent workspace inspections through the existing authenticated API; I learned that typed Python functions become discoverable tool schemas quickly, while the read-only annotation complements rather than replaces server-side authorization. I would enjoy working directly with developers and partners, building the integration myself, then turning what I learned into an example or demo that saves the next developer time.

I am looking for a small team where I can own work through launch, and I am open to relocating to San Francisco.
```

Do not claim that the MCP server is publicly deployed unless that deployment is completed and authenticated separately.

- [ ] **Step 6: Commit the documentation**

```powershell
git add README.md docs/MCP_INTEGRATION.md tests/test_mcp_documentation.py
git commit -m "docs: explain the FreshSense read-only MCP integration"
```

---

### Task 6: Full verification and review handoff

**Files:**
- Review all files changed since commit `d901971`.

**Interfaces:**
- Verifies: isolated MCP tests, standard FreshSense regression tests, diff quality, and credential hygiene.

- [ ] **Step 1: Run the standard FreshSense regression suite**

```powershell
py -3.11 -m pytest tests/test_mcp_client.py tests/test_mcp_api_integration.py tests/test_mcp_documentation.py -q
py -3.11 -m pytest -q
```

Expected: all standard tests pass. The standard suite must not require `mcp-use` because `freshsense_mcp/__init__.py` does not import the server module.

- [ ] **Step 2: Run the isolated MCP suite and protocol smoke**

```powershell
$env:MCP_USE_ANONYMIZED_TELEMETRY='false'
& .\.mcp-venv\Scripts\python.exe -m pytest tests/test_mcp_server.py tests/test_mcp_smoke.py -q
& .\.mcp-venv\Scripts\python.exe scripts/smoke_mcp_integration.py
```

Expected: all MCP tests pass, the client discovers exactly one tool, and the structured response contains one minimized inspection.

- [ ] **Step 3: Check for accidental credentials and prohibited operations**

```powershell
rg -n "freshsense-mcp-smoke-key|FRESHSENSE_MCP_API_KEY=.*[^<]$|Bearer [A-Za-z0-9]" `
  freshsense_mcp docs README.md requirements-mcp*.txt
rg -n "POST|PATCH|PUT|DELETE|inspections/analyze|/review|/approvals" freshsense_mcp
```

Expected: the first command finds no committed real credential; the second finds no mutation request in production MCP code.

- [ ] **Step 4: Review the final diff**

```powershell
git diff --check d901971..HEAD
git diff --stat d901971..HEAD
git log --oneline d901971..HEAD
git status --short
```

Expected: no whitespace errors; only the known user-owned `.superpowers/` directory remains untracked.

- [ ] **Step 5: Request code review before publishing**

Use `superpowers:requesting-code-review` against the completed branch. Address any correctness, security, or documentation issue, rerun the focused and full tests, then present the commits and the updated Manufact note to the user. Do not push or deploy until the user requests publication.

