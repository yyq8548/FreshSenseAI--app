from pathlib import Path

from deployment.azure.staging import validate_staging_configuration


ROOT = Path(__file__).resolve().parents[1]


def _valid_config():
    return {
        "FRESHSENSE_AUTH_MODE": "entra",
        "FRESHSENSE_ENTRA_TENANT_ID": "tenant-id",
        "FRESHSENSE_ENTRA_API_CLIENT_ID": "api-id",
        "FRESHSENSE_ENTRA_AUTHORITY": "https://freshsenseai.ciamlogin.com/tenant-id",
        "FRESHSENSE_ENTRA_ALLOWED_CLIENT_IDS": "spa-id",
        "FRESHSENSE_CORS_ORIGINS": "https://freshsense.azurestaticapps.net",
        "FRESHSENSE_ALLOWED_HOSTS": "freshsense-api.azurewebsites.net",
        "FRESHSENSE_SAAS_DATABASE_URL": (
            "postgresql+psycopg://user:secret@server.postgres.database.azure.com/"
            "freshsense?sslmode=verify-full"
        ),
        "FRESHSENSE_RUNTIME_BUNDLE_URL": "https://artifacts.example.test/runtime.zip",
        "FRESHSENSE_RUNTIME_BUNDLE_SHA256": "a" * 64,
        "FRESHSENSE_JSON_LOGS": "true",
        "FRESHSENSE_REQUIRE_OPEN_SET_GATE": "true",
        "FRESHSENSE_REQUIRE_SEMANTIC_RAG": "true",
        "FRESHSENSE_EMBEDDING_LOCAL_ONLY": "true",
    }


def test_staging_configuration_accepts_secure_nonproduction_settings():
    report = validate_staging_configuration(_valid_config())

    assert report["ready"] is True
    assert report["decision"] == "ready_for_staging_configuration"


def test_staging_configuration_rejects_local_sqlite_and_insecure_origins():
    config = _valid_config()
    config["FRESHSENSE_SAAS_DATABASE_URL"] = "runtime/freshsense.db"
    config["FRESHSENSE_CORS_ORIGINS"] = "http://localhost:5173"
    config["FRESHSENSE_RUNTIME_BUNDLE_SHA256"] = "not-a-checksum"

    report = validate_staging_configuration(config)

    assert report["ready"] is False
    assert {
        "https_cors_origin",
        "managed_postgresql",
        "postgresql_tls",
        "runtime_bundle_checksum",
    }.issubset(set(report["failed_checks"]))


def test_linux_startup_script_is_forced_to_lf_line_endings():
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    startup = (ROOT / "deployment" / "azure" / "startup.sh").read_bytes()

    assert "*.sh text eol=lf" in attributes
    assert startup.startswith(b"#!/usr/bin/env bash\n")
    assert b"\r\n" not in startup
