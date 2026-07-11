"""Dependency-free structured logging, request IDs, and operational metrics."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
import sys
import time
from uuid import uuid4

from api.models import MetricsResponse


REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
LOG_FIELDS = (
    "event",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "retrieval_mode",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_json_logging(logger: logging.Logger) -> None:
    if any(getattr(handler, "_freshsense_json", False) for handler in logger.handlers):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler._freshsense_json = True  # type: ignore[attr-defined]
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def request_id_from_header(value: str | None) -> str:
    candidate = (value or "").strip()
    if candidate and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid4().hex


class MetricsRegistry:
    def __init__(self, *, clock=time.monotonic) -> None:
        self._clock = clock
        self._started = clock()
        self._lock = asyncio.Lock()
        self._request_count = 0
        self._active_requests = 0
        self._status_counts: dict[str, int] = {}
        self._analysis_count = 0
        self._analysis_failures = 0
        self._analysis_total_seconds = 0.0
        self._last_analysis_seconds: float | None = None

    async def request_started(self) -> None:
        async with self._lock:
            self._active_requests += 1

    async def request_finished(self, status_code: int) -> None:
        async with self._lock:
            self._active_requests = max(0, self._active_requests - 1)
            self._request_count += 1
            family = f"{status_code // 100}xx"
            self._status_counts[family] = self._status_counts.get(family, 0) + 1

    async def analysis_finished(self, *, success: bool, duration_seconds: float) -> None:
        async with self._lock:
            self._analysis_count += 1
            if not success:
                self._analysis_failures += 1
            self._analysis_total_seconds += duration_seconds
            self._last_analysis_seconds = duration_seconds

    async def snapshot(self) -> MetricsResponse:
        async with self._lock:
            average = (
                self._analysis_total_seconds / self._analysis_count
                if self._analysis_count
                else None
            )
            return MetricsResponse(
                uptime_seconds=round(self._clock() - self._started, 3),
                request_count=self._request_count,
                active_requests=self._active_requests,
                response_status_counts=dict(self._status_counts),
                analysis_count=self._analysis_count,
                analysis_failures=self._analysis_failures,
                average_analysis_seconds=(round(average, 6) if average is not None else None),
                last_analysis_seconds=(
                    round(self._last_analysis_seconds, 6)
                    if self._last_analysis_seconds is not None
                    else None
                ),
            )
