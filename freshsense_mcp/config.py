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
