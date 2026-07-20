"""Fail-closed validation for a non-production Azure SaaS configuration."""

from __future__ import annotations

from collections.abc import Mapping
import re
from urllib.parse import parse_qs, urlsplit

from saas.database import DatabaseConfigurationError, normalize_database_target


def validate_staging_configuration(values: Mapping[str, str]) -> dict[str, object]:
    checks: list[dict[str, object]] = []

    _equal(checks, "entra_authentication", values, "FRESHSENSE_AUTH_MODE", "entra")
    _present(checks, "entra_tenant", values, "FRESHSENSE_ENTRA_TENANT_ID")
    _present(checks, "entra_api_client", values, "FRESHSENSE_ENTRA_API_CLIENT_ID")
    _present(checks, "entra_allowed_spa", values, "FRESHSENSE_ENTRA_ALLOWED_CLIENT_IDS")
    authority = values.get("FRESHSENSE_ENTRA_AUTHORITY", "").strip()
    _check(
        checks,
        "external_id_https_authority",
        authority.startswith("https://") and ".ciamlogin.com/" in authority,
        "configured" if authority else "missing",
        "HTTPS ciamlogin.com authority",
    )

    origins = _csv(values.get("FRESHSENSE_CORS_ORIGINS", ""))
    _check(
        checks,
        "https_cors_origin",
        bool(origins)
        and all(origin.startswith("https://") for origin in origins)
        and all("localhost" not in origin for origin in origins),
        len(origins),
        "one or more hosted HTTPS origins without localhost",
    )
    hosts = _csv(values.get("FRESHSENSE_ALLOWED_HOSTS", ""))
    _check(
        checks,
        "restricted_hosts",
        bool(hosts) and "*" not in hosts and all("/" not in host for host in hosts),
        len(hosts),
        "explicit hostnames without wildcard",
    )

    database_url = values.get("FRESHSENSE_SAAS_DATABASE_URL", "").strip()
    database_backend = "invalid"
    sslmode = None
    try:
        normalized_url, _, database_backend = normalize_database_target(database_url)
        sslmode = parse_qs(urlsplit(normalized_url).query).get("sslmode", [None])[0]
    except DatabaseConfigurationError:
        pass
    _check(
        checks,
        "managed_postgresql",
        database_backend == "postgresql",
        database_backend,
        "postgresql",
    )
    _check(
        checks,
        "postgresql_tls",
        sslmode in {"require", "verify-ca", "verify-full"},
        sslmode or "missing",
        "require, verify-ca, or verify-full",
    )

    runtime_url = values.get("FRESHSENSE_RUNTIME_BUNDLE_URL", "").strip()
    runtime_hash = values.get("FRESHSENSE_RUNTIME_BUNDLE_SHA256", "").strip().lower()
    _check(
        checks,
        "https_runtime_bundle",
        runtime_url.startswith("https://"),
        "configured" if runtime_url else "missing",
        "immutable HTTPS artifact URL",
    )
    _check(
        checks,
        "runtime_bundle_checksum",
        bool(re.fullmatch(r"[0-9a-f]{64}", runtime_hash)),
        "configured" if runtime_hash else "missing",
        "lowercase SHA-256",
    )

    for name, key in (
        ("json_logging", "FRESHSENSE_JSON_LOGS"),
        ("open_set_gate_required", "FRESHSENSE_REQUIRE_OPEN_SET_GATE"),
        ("semantic_rag_required", "FRESHSENSE_REQUIRE_SEMANTIC_RAG"),
        ("local_embedding_artifact", "FRESHSENSE_EMBEDDING_LOCAL_ONLY"),
    ):
        _equal(checks, name, values, key, "true")

    failed = [str(check["name"]) for check in checks if not check["passed"]]
    return {
        "ready": not failed,
        "decision": "ready_for_staging_configuration" if not failed else "blocked",
        "checks": checks,
        "failed_checks": failed,
        "note": (
            "This validates configuration only. It does not override the model, "
            "pilot, security, cost, or production approval gates."
        ),
    }


def _csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _present(checks, name, values, key):
    value = values.get(key, "").strip()
    _check(checks, name, bool(value), "configured" if value else "missing", "configured")


def _equal(checks, name, values, key, required):
    observed = values.get(key, "").strip().lower()
    _check(checks, name, observed == required, observed or "missing", required)


def _check(checks, name, passed, observed, required):
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "observed": observed,
            "required": required,
        }
    )


__all__ = ["validate_staging_configuration"]
