"""Authentication, secret loading, and bounded in-process rate limiting."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from hashlib import sha256
import math
from pathlib import Path
import secrets
import time

from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from api.errors import ApiProblem
from api.identity import AuthContext, TokenValidationError
from utils.startup import StartupValidationError


API_KEY_HEADER = APIKeyHeader(
    name="X-API-Key",
    scheme_name="FreshSenseApiKey",
    description="FreshSense API key supplied through the X-API-Key header.",
    auto_error=False,
)
BEARER_HEADER = HTTPBearer(
    scheme_name="FreshSenseEntraBearer",
    description="Microsoft Entra access token issued for the FreshSense API.",
    auto_error=False,
)


def resolve_api_key(
    *,
    explicit_value: str | None,
    environment_value: str | None,
    secret_file: str | None,
) -> str | None:
    """Resolve a key, preferring a local secret file over environment data."""
    if explicit_value is not None:
        value = explicit_value.strip()
    elif secret_file:
        path = Path(secret_file)
        try:
            value = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise StartupValidationError(
                "The configured FreshSense API-key secret file is unavailable."
            ) from exc
    else:
        value = (environment_value or "").strip()
    return value or None


def validate_api_key_configuration(api_key: str | None, *, required: bool) -> None:
    if required and api_key is None:
        raise StartupValidationError(
            "API-key authentication is required but no key was configured."
        )
    if api_key is not None and len(api_key) < 32:
        raise StartupValidationError(
            "The FreshSense API key must contain at least 32 characters."
        )


async def authenticate_request(
    request: Request,
    supplied_key: str | None = Depends(API_KEY_HEADER),
    bearer: HTTPAuthorizationCredentials | None = Depends(BEARER_HEADER),
) -> str:
    """Authenticate protected routes and return a non-secret rate-limit identity."""
    context = authenticate_for_request(
        request,
        supplied_key=supplied_key,
        bearer_token=(bearer.credentials if bearer else None),
    )
    return context.identity


async def authenticated_context(
    request: Request,
    supplied_key: str | None = Depends(API_KEY_HEADER),
    bearer: HTTPAuthorizationCredentials | None = Depends(BEARER_HEADER),
) -> AuthContext:
    return authenticate_for_request(
        request,
        supplied_key=supplied_key,
        bearer_token=(bearer.credentials if bearer else None),
    )


def authenticate_for_request(
    request: Request,
    *,
    supplied_key: str | None,
    bearer_token: str | None,
) -> AuthContext:
    existing = getattr(request.state, "auth_context", None)
    if existing is not None:
        return existing
    if request.app.state.auth_mode == "entra":
        return authenticate_entra_token(request, bearer_token)
    authenticate_api_key(request, supplied_key)
    return request.state.auth_context


def authenticate_api_key(request: Request, supplied_key: str | None) -> str:
    """Authenticate before request-body parsing and return a hashed identity."""
    expected_key = request.app.state.api_key
    authentication_enabled = request.app.state.authentication_enabled
    if authentication_enabled:
        if (
            supplied_key is None
            or expected_key is None
            or not secrets.compare_digest(supplied_key, expected_key)
        ):
            raise ApiProblem(
                401,
                "INVALID_API_KEY",
                "A valid X-API-Key header is required.",
                headers={"WWW-Authenticate": "APIKey"},
            )

    client_host = request.client.host if request.client else "unknown"
    identity_material = (
        f"api-key:{supplied_key}"
        if supplied_key
        else f"anonymous-client:{client_host}"
    )
    identity = sha256(identity_material.encode("utf-8")).hexdigest()
    request.state.auth_identity = identity
    request.state.auth_context = AuthContext(
        identity=identity,
        subject=identity,
        tenant_id=None,
        display_name="Local API user" if supplied_key else "Local development user",
        email=None,
        scheme="api_key" if supplied_key else "local",
        scopes=frozenset(),
    )
    return identity


def authenticate_entra_token(request: Request, bearer_token: str | None) -> AuthContext:
    if not bearer_token:
        raise ApiProblem(
            401,
            "INVALID_ACCESS_TOKEN",
            "A valid Microsoft Entra bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    validator = getattr(request.app.state, "entra_token_validator", None)
    if validator is None:
        raise ApiProblem(
            503,
            "IDENTITY_PROVIDER_UNAVAILABLE",
            "Microsoft Entra authentication is not ready.",
        )
    try:
        claims = validator.validate(bearer_token)
    except TokenValidationError as exc:
        raise ApiProblem(
            401,
            "INVALID_ACCESS_TOKEN",
            "A valid Microsoft Entra bearer token is required.",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc

    subject = str(claims.get("sub", "")).strip()
    tenant_id = str(claims.get("tid", "")).strip()
    if not subject or not tenant_id:
        raise ApiProblem(
            401,
            "INVALID_ACCESS_TOKEN",
            "A valid Microsoft Entra bearer token is required.",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    emails = claims.get("emails")
    email = (
        str(emails[0]).strip()
        if isinstance(emails, list) and emails
        else str(claims.get("email") or claims.get("preferred_username") or "").strip()
    )
    identity = sha256(f"entra:{tenant_id}:{subject}".encode("utf-8")).hexdigest()
    context = AuthContext(
        identity=identity,
        subject=subject,
        tenant_id=tenant_id,
        display_name=str(claims.get("name") or "").strip() or None,
        email=email or None,
        scheme="entra",
        scopes=frozenset(str(claims.get("scp", "")).split()),
    )
    request.state.auth_identity = identity
    request.state.auth_context = context
    return context


@dataclass(frozen=True)
class RateLimitDecision:
    limit: int
    remaining: int
    reset_seconds: int

    @property
    def headers(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.reset_seconds),
        }


class InMemoryRateLimiter:
    """Fixed-window limiter for a single local API worker."""

    def __init__(
        self,
        limit: int,
        *,
        window_seconds: int = 60,
        clock=time.monotonic,
    ) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("Rate-limit values must be positive.")
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._buckets: dict[str, tuple[float, int]] = {}
        self._lock = asyncio.Lock()
        self._checks = 0

    async def check(self, identity: str) -> RateLimitDecision:
        now = self._clock()
        async with self._lock:
            started, count = self._buckets.get(identity, (now, 0))
            if now - started >= self.window_seconds:
                started, count = now, 0

            self._checks += 1
            if self._checks % 100 == 0:
                cutoff = now - (self.window_seconds * 2)
                self._buckets = {
                    key: value
                    for key, value in self._buckets.items()
                    if value[0] >= cutoff
                }

            reset_seconds = max(1, math.ceil(self.window_seconds - (now - started)))
            if count >= self.limit:
                decision = RateLimitDecision(
                    limit=self.limit,
                    remaining=0,
                    reset_seconds=reset_seconds,
                )
                raise ApiProblem(
                    429,
                    "RATE_LIMIT_EXCEEDED",
                    "Too many analysis requests. Try again later.",
                    headers={
                        **decision.headers,
                        "Retry-After": str(reset_seconds),
                    },
                )

            count += 1
            self._buckets[identity] = (started, count)
            return RateLimitDecision(
                limit=self.limit,
                remaining=self.limit - count,
                reset_seconds=reset_seconds,
            )


async def enforce_rate_limit(
    request: Request,
    identity: str = Depends(authenticate_request),
) -> RateLimitDecision:
    return await request.app.state.rate_limiter.check(identity)
