"""Minimal, credential-safe client for FreshSense inspection metadata."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import build_opener, HTTPRedirectHandler, Request

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


class _RejectRedirects(HTTPRedirectHandler):
    """Prevent credential-bearing requests from leaving the configured origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _send(request: Request, timeout_seconds: float) -> HttpResult:
    try:
        opener = build_opener(_RejectRedirects())
        with opener.open(request, timeout=timeout_seconds) as response:
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

        request = Request(url, headers=headers, method="GET")
        result = self._sender(request, self._config.timeout_seconds)
        if 300 <= result.status_code < 400:
            raise FreshSenseMCPError("FreshSense API redirect was rejected.")
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
            raise FreshSenseMCPError(
                "FreshSense API returned an unexpected response."
            ) from exc
        if not isinstance(payload, dict) or not isinstance(
            payload.get("inspections"), list
        ):
            raise FreshSenseMCPError("FreshSense API returned an unexpected response.")

        minimized = []
        for value in payload["inspections"]:
            if not isinstance(value, dict):
                raise FreshSenseMCPError(
                    "FreshSense API returned an unexpected response."
                )
            minimized.append({field: value.get(field) for field in INSPECTION_FIELDS})
        return {"count": len(minimized), "inspections": minimized}
