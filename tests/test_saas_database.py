from pathlib import Path

import pytest

from agent.autonomous import AutonomousInspectionAgent
from saas.database import (
    DatabaseConfigurationError,
    bind_parameters,
    normalize_database_target,
)
from saas.migration import migrate_saas_database
from saas.store import SaaSStore, SaaSStoreError


def test_local_path_uses_sqlite_without_changing_store_contract(tmp_path):
    target = tmp_path / "nested" / "saas.db"

    store = SaaSStore(target)
    workspace = store.workspace("identity-a")

    assert store.backend == "sqlite"
    assert store.path == target.resolve()
    assert target.is_file()
    assert workspace["current_role"] == "manager"


@pytest.mark.parametrize("scheme", ["postgres", "postgresql"])
def test_postgres_urls_select_psycopg_and_do_not_become_paths(scheme):
    url, path, backend = normalize_database_target(
        f"{scheme}://freshsense:secret@example.postgres.database.azure.com/app?sslmode=require"
    )

    assert url.startswith("postgresql+psycopg://")
    assert "sslmode=require" in url
    assert path is None
    assert backend == "postgresql"


def test_database_target_rejects_unsupported_backends():
    with pytest.raises(DatabaseConfigurationError, match="only SQLite and PostgreSQL"):
        normalize_database_target("mysql://example.test/freshsense")


def test_positional_bind_conversion_is_dialect_neutral():
    sql, values = bind_parameters(
        "SELECT * FROM inspections WHERE workspace_id = ? LIMIT ?",
        ("workspace-a", 25),
    )

    assert sql == (
        "SELECT * FROM inspections WHERE workspace_id = :p0 LIMIT :p1"
    )
    assert values == {"p0": "workspace-a", "p1": 25}


def test_positional_bind_conversion_rejects_parameter_mismatch():
    with pytest.raises(DatabaseConfigurationError, match="parameter count"):
        bind_parameters("SELECT ?", ())


def test_metadata_migration_preserves_tenant_rows_and_requires_empty_target(tmp_path):
    source = tmp_path / "source.db"
    target = tmp_path / "target.db"
    source_store = SaaSStore(source)
    inspection = source_store.record_inspection(
        identity_hash="manager-a",
        location_name="Receiving",
        batch_reference="PO-42",
        operator_note="Migration test",
        analysis={
            "decision": "accept_prediction",
            "status": "completed",
            "prediction": {
                "class_name": "freshbanana",
                "display_name": "Fresh Banana",
                "fruit": "banana",
                "freshness": "fresh",
                "confidence": 0.9,
            },
            "reasoning": {"risk_level": "low"},
            "warnings": [],
            "recommendation": "Review visually.",
            "safety_notice": "Decision support only.",
        },
        model_version="0.6.0",
    )
    agent_run = AutonomousInspectionAgent(source_store).run(
        identity_hash="manager-a",
        inspection_id=inspection["inspection_id"],
    )

    preview = migrate_saas_database(source, target)
    applied = migrate_saas_database(source, target, apply=True)

    assert preview["applied"] is False
    assert preview["source_counts"]["inspections"] == 1
    assert preview["source_counts"]["agent_runs"] == 1
    assert preview["source_counts"]["agent_steps"] == 5
    assert preview["source_counts"]["action_proposals"] == 1
    assert applied["verified_counts"] == applied["source_counts"]
    assert SaaSStore(target).list_inspections("manager-a")[0]["image_retained"] is False
    migrated_run = SaaSStore(target).agent_run("manager-a", agent_run["run_id"])
    assert migrated_run["status"] == "completed"
    assert migrated_run["action_proposals"][0]["execution_status"] == "shadow_only"
    with pytest.raises(SaaSStoreError, match="must be empty"):
        migrate_saas_database(source, target, apply=True)
