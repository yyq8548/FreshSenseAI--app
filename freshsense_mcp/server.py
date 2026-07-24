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
