"""Microsoft Entra access-token validation for the FreshSense API."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Any
from urllib.request import Request, urlopen

import jwt


class TokenValidationError(ValueError):
    """Raised when an access token fails any required validation."""


@dataclass(frozen=True)
class AuthContext:
    identity: str
    subject: str
    tenant_id: str | None
    display_name: str | None
    email: str | None
    scheme: str
    scopes: frozenset[str]


def _load_json(url: str, *, timeout: float) -> Mapping[str, Any]:
    request = Request(url, headers={"User-Agent": "FreshSenseAI/0.6"})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        value = json.loads(response.read().decode("utf-8"))
    if not isinstance(value, dict):
        raise TokenValidationError("Identity metadata is not a JSON object.")
    return value


class EntraTokenValidator:
    """Validate v2 Microsoft Entra access tokens using OIDC discovery."""

    def __init__(
        self,
        *,
        authority: str,
        tenant_id: str,
        audience: str,
        required_scopes: Sequence[str],
        allowed_client_ids: Sequence[str] = (),
        timeout_seconds: float = 5.0,
        metadata_loader: Callable[..., Mapping[str, Any]] = _load_json,
        jwk_client_factory: Callable[..., Any] = jwt.PyJWKClient,
    ) -> None:
        self.authority = authority.rstrip("/")
        self.tenant_id = tenant_id.strip()
        self.audience = audience.strip()
        self.required_scopes = frozenset(scope.strip() for scope in required_scopes if scope.strip())
        self.allowed_client_ids = frozenset(
            client_id.strip() for client_id in allowed_client_ids if client_id.strip()
        )
        self.timeout_seconds = timeout_seconds
        self._metadata_loader = metadata_loader
        self._jwk_client_factory = jwk_client_factory
        self._issuer: str | None = None
        self._jwk_client: Any = None
        self._validate_configuration()

    def initialize(self) -> None:
        metadata_url = f"{self.authority}/v2.0/.well-known/openid-configuration"
        try:
            metadata = self._metadata_loader(metadata_url, timeout=self.timeout_seconds)
            issuer = str(metadata["issuer"]).strip()
            jwks_uri = str(metadata["jwks_uri"]).strip()
        except (KeyError, OSError, ValueError, json.JSONDecodeError) as exc:
            raise TokenValidationError(
                "Microsoft Entra discovery metadata could not be loaded."
            ) from exc
        if not issuer.startswith("https://") or not jwks_uri.startswith("https://"):
            raise TokenValidationError("Microsoft Entra discovery endpoints must use HTTPS.")
        self._issuer = issuer
        self._jwk_client = self._jwk_client_factory(
            jwks_uri,
            cache_keys=True,
            cache_jwk_set=True,
            lifespan=3600,
            timeout=self.timeout_seconds,
        )
        try:
            self._jwk_client.get_jwk_set()
        except Exception as exc:
            raise TokenValidationError(
                "Microsoft Entra signing keys could not be loaded."
            ) from exc

    def validate(self, token: str) -> Mapping[str, Any]:
        if self._issuer is None or self._jwk_client is None:
            raise TokenValidationError("Microsoft Entra validation is not initialized.")
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "tid"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenValidationError("The Microsoft Entra access token is invalid.") from exc
        self._validate_claims(claims)
        return claims

    def _validate_claims(self, claims: Mapping[str, Any]) -> None:
        if str(claims.get("tid", "")) != self.tenant_id:
            raise TokenValidationError("The access token belongs to another tenant.")
        scopes = frozenset(str(claims.get("scp", "")).split())
        missing = self.required_scopes - scopes
        if missing:
            raise TokenValidationError("The access token is missing a required API scope.")
        if self.allowed_client_ids:
            authorized_party = str(claims.get("azp") or claims.get("appid") or "")
            if authorized_party not in self.allowed_client_ids:
                raise TokenValidationError("The calling client application is not allowed.")

    def _validate_configuration(self) -> None:
        if not self.authority.startswith("https://"):
            raise TokenValidationError("The Microsoft Entra authority must use HTTPS.")
        if not self.tenant_id or not self.audience:
            raise TokenValidationError("Microsoft Entra tenant and API client IDs are required.")
        if not self.required_scopes:
            raise TokenValidationError("At least one Microsoft Entra API scope is required.")
