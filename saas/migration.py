"""Explicit, metadata-only migration between FreshSense database backends."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from saas.database import Database
from saas.store import SaaSStore, SaaSStoreError


MIGRATION_TABLES: tuple[str, ...] = (
    "workspaces",
    "locations",
    "workspace_memberships",
    "inspections",
    "review_events",
    "workspace_invitations",
)


def migrate_saas_database(
    source: str | Path,
    target: str | Path,
    *,
    apply: bool = False,
) -> dict[str, Any]:
    """Copy an initialized FreshSense database into an empty target.

    The function deliberately refuses to merge into an occupied target. This
    protects tenant boundaries and makes every migration rerunnable and easy to
    audit. FreshSense schemas contain inspection metadata only; image bytes and
    image paths are not part of any migrated table.
    """

    source_store = SaaSStore(source)
    source_store.initialize()
    target_store = SaaSStore(target)
    target_store.initialize()

    source_counts = _table_counts(source_store.database)
    target_counts = _table_counts(target_store.database)
    occupied = {name: count for name, count in target_counts.items() if count}
    if occupied:
        raise SaaSStoreError(
            "The target SaaS database must be empty before migration."
        )

    report: dict[str, Any] = {
        "source_backend": source_store.backend,
        "target_backend": target_store.backend,
        "image_data_migrated": False,
        "source_counts": source_counts,
        "migrated_counts": {name: 0 for name in MIGRATION_TABLES},
        "applied": bool(apply),
    }
    if not apply:
        return report

    for table in MIGRATION_TABLES:
        rows = _read_table(source_store.database, table)
        if rows:
            _write_table(target_store.database, table, rows)
        report["migrated_counts"][table] = len(rows)

    final_counts = _table_counts(target_store.database)
    if final_counts != source_counts:
        raise SaaSStoreError(
            "The SaaS database migration did not preserve all row counts."
        )
    report["verified_counts"] = final_counts
    return report


def _table_counts(database: Database) -> dict[str, int]:
    counts: dict[str, int] = {}
    with database.connect() as connection:
        for table in MIGRATION_TABLES:
            row = connection.execute(f"SELECT COUNT(*) AS count FROM {table}").fetchone()
            counts[table] = int(row["count"] if row is not None else 0)
    return counts


def _read_table(database: Database, table: str) -> list[dict[str, Any]]:
    with database.connect() as connection:
        rows = connection.execute(f"SELECT * FROM {table}").fetchall()
    return [dict(row) for row in rows]


def _write_table(
    database: Database,
    table: str,
    rows: list[Mapping[str, Any]],
) -> None:
    columns = tuple(rows[0].keys())
    placeholders = ", ".join("?" for _ in columns)
    statement = (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    )
    with database.connect() as connection:
        for row in rows:
            connection.execute(statement, tuple(row[column] for column in columns))


__all__ = ["MIGRATION_TABLES", "migrate_saas_database"]
