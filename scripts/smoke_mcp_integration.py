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
    client: MCPClient | None = None
    try:
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
        session = await asyncio.wait_for(
            client.create_session("freshsense"), timeout=15
        )
        if session is None:
            raise RuntimeError("mcp-use did not create the FreshSense session.")
        tools = await asyncio.wait_for(session.list_tools(), timeout=10)
        result = await asyncio.wait_for(
            session.call_tool("get_recent_inspections", {"limit": 3}), timeout=10
        )
        return {
            "tool_names": [tool.name for tool in tools],
            "structured_content": result.structuredContent,
        }
    finally:
        try:
            if client is not None:
                await asyncio.wait_for(client.close_all_sessions(), timeout=10)
        finally:
            api.shutdown()
            api.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    value = asyncio.run(run_smoke())
    print(json.dumps(value, indent=2))
