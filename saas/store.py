"""Privacy-preserving persistence for team inspection workflows.

The same repository contract supports local SQLite development and managed
PostgreSQL deployments. Uploaded images are never written to either backend.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import secrets
from threading import Lock
from typing import Any, Mapping
from uuid import uuid4

from saas.database import (
    Database,
    DatabaseConnection,
    DatabaseConfigurationError,
    DatabaseOperationError,
)


SCHEMA_VERSION = 2
REVIEW_STATUSES = frozenset({"pending", "confirmed", "corrected", "dismissed"})
REVIEWED_OUTCOMES = frozenset({"fresh", "rotten", "unsupported", "uncertain"})
WORKSPACE_ROLES = frozenset({"manager", "inspector", "reviewer"})


class SaaSStoreError(RuntimeError):
    """Raised when SaaS metadata cannot be validated or persisted."""


class InspectionNotFoundError(SaaSStoreError):
    """Raised when an inspection is absent from the authenticated workspace."""


class SaaSStore:
    """Store workspace-scoped metadata without retaining uploaded images."""

    def __init__(self, target: str | Path) -> None:
        try:
            self.database = Database(target)
        except DatabaseConfigurationError as exc:
            raise SaaSStoreError("The SaaS database configuration is invalid.") from exc
        self.path = self.database.path
        self.backend = self.database.backend
        self._initialize_lock = Lock()
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._initialize_lock:
            if self._initialized:
                return
            if self.path is not None:
                self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with self._connect() as connection:
                    connection.executescript(
                        """
                        CREATE TABLE IF NOT EXISTS saas_metadata (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL
                        );

                    CREATE TABLE IF NOT EXISTS workspaces (
                        workspace_id TEXT PRIMARY KEY,
                        identity_hash TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS locations (
                        location_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        name TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id),
                        UNIQUE(workspace_id, name)
                    );

                    CREATE TABLE IF NOT EXISTS inspections (
                        inspection_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        location_id TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        batch_reference TEXT NOT NULL,
                        operator_note TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        analysis_status TEXT NOT NULL,
                        predicted_class TEXT,
                        predicted_display_name TEXT,
                        fruit TEXT,
                        predicted_freshness TEXT,
                        confidence REAL,
                        risk_level TEXT,
                        recommendation TEXT NOT NULL,
                        safety_notice TEXT NOT NULL,
                        warnings_json TEXT NOT NULL,
                        model_version TEXT NOT NULL,
                        review_status TEXT NOT NULL,
                        reviewed_outcome TEXT,
                        review_note TEXT NOT NULL,
                        reviewed_at_utc TEXT,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id),
                        FOREIGN KEY(location_id) REFERENCES locations(location_id)
                    );

                    CREATE TABLE IF NOT EXISTS review_events (
                        review_id TEXT PRIMARY KEY,
                        inspection_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        review_status TEXT NOT NULL,
                        reviewed_outcome TEXT,
                        note TEXT NOT NULL,
                        FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id),
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
                    );

                    CREATE TABLE IF NOT EXISTS workspace_memberships (
                        workspace_id TEXT NOT NULL,
                        identity_hash TEXT NOT NULL UNIQUE,
                        role TEXT NOT NULL,
                        email TEXT,
                        display_name TEXT,
                        created_at_utc TEXT NOT NULL,
                        last_seen_at_utc TEXT NOT NULL,
                        PRIMARY KEY(workspace_id, identity_hash),
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
                    );

                    CREATE TABLE IF NOT EXISTS workspace_invitations (
                        invitation_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        email TEXT NOT NULL,
                        role TEXT NOT NULL,
                        token_hash TEXT NOT NULL UNIQUE,
                        created_at_utc TEXT NOT NULL,
                        expires_at_utc TEXT NOT NULL,
                        accepted_at_utc TEXT,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
                    );

                    CREATE INDEX IF NOT EXISTS idx_inspections_workspace_created
                        ON inspections(workspace_id, created_at_utc DESC);
                    CREATE INDEX IF NOT EXISTS idx_inspections_workspace_review
                        ON inspections(workspace_id, review_status);
                    CREATE INDEX IF NOT EXISTS idx_reviews_inspection_created
                        ON review_events(inspection_id, created_at_utc);
                    CREATE INDEX IF NOT EXISTS idx_members_workspace
                        ON workspace_memberships(workspace_id, role);
                    CREATE INDEX IF NOT EXISTS idx_invitations_workspace
                        ON workspace_invitations(workspace_id, created_at_utc DESC);
                        """
                    )
                    row = connection.execute(
                        "SELECT value FROM saas_metadata WHERE key = 'schema_version'"
                    ).fetchone()
                    if row is None:
                        connection.execute(
                            """
                            INSERT INTO saas_metadata(key, value)
                            VALUES('schema_version', ?)
                            ON CONFLICT DO NOTHING
                            """,
                            (str(SCHEMA_VERSION),),
                        )
                    elif int(row["value"]) == 1:
                        connection.execute(
                            "UPDATE saas_metadata SET value = ? WHERE key = 'schema_version'",
                            (str(SCHEMA_VERSION),),
                        )
                    elif int(row["value"]) != SCHEMA_VERSION:
                        raise SaaSStoreError("The SaaS database schema is not supported.")
                    legacy_workspaces = connection.execute(
                        """
                        SELECT workspace_id, identity_hash, created_at_utc
                        FROM workspaces
                        """
                    ).fetchall()
                    for legacy_workspace in legacy_workspaces:
                        connection.execute(
                            """
                            INSERT INTO workspace_memberships(
                                workspace_id, identity_hash, role, email, display_name,
                                created_at_utc, last_seen_at_utc
                            ) VALUES (?, ?, 'manager', NULL, NULL, ?, ?)
                            ON CONFLICT DO NOTHING
                            """,
                            (
                                legacy_workspace["workspace_id"],
                                legacy_workspace["identity_hash"],
                                legacy_workspace["created_at_utc"],
                                legacy_workspace["created_at_utc"],
                            ),
                        )
            except SaaSStoreError as exc:
                if exc.__cause__ is None:
                    raise
                raise SaaSStoreError("The SaaS database could not be initialized.") from exc
            self._initialized = True

    def workspace(
        self,
        identity_hash: str,
        *,
        email: str | None = None,
        display_name: str | None = None,
    ) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        self._touch_member(
            workspace_id=workspace_id,
            identity_hash=identity_hash,
            email=email,
            display_name=display_name,
        )
        with self._connect() as connection:
            workspace = connection.execute(
                """
                SELECT workspace_id, display_name, created_at_utc
                FROM workspaces WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchone()
            locations = connection.execute(
                """
                SELECT location_id, name, created_at_utc
                FROM locations WHERE workspace_id = ? ORDER BY name
                """,
                (workspace_id,),
            ).fetchall()
            current_member = connection.execute(
                """
                SELECT role, email, display_name
                FROM workspace_memberships
                WHERE workspace_id = ? AND identity_hash = ?
                """,
                (workspace_id, identity_hash),
            ).fetchone()
            members = connection.execute(
                """
                SELECT identity_hash, role, email, display_name, created_at_utc,
                       last_seen_at_utc
                FROM workspace_memberships
                WHERE workspace_id = ?
                ORDER BY role, display_name, email, identity_hash
                """,
                (workspace_id,),
            ).fetchall()
        return {
            **dict(workspace),
            "plan": "pilot",
            "image_retention": False,
            "locations": [dict(row) for row in locations],
            "current_role": current_member["role"],
            "members": [_member_record(row) for row in members],
        }

    def member_role(self, identity_hash: str) -> str:
        workspace_id = self._workspace_id(identity_hash)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT role FROM workspace_memberships
                WHERE workspace_id = ? AND identity_hash = ?
                """,
                (workspace_id, identity_hash),
            ).fetchone()
        if row is None:
            raise SaaSStoreError("Workspace membership is unavailable.")
        return str(row["role"])

    def create_invitation(
        self,
        *,
        identity_hash: str,
        email: str,
        role: str,
        expires_days: int = 7,
    ) -> dict[str, Any]:
        if self.member_role(identity_hash) != "manager":
            raise SaaSStoreError("Only a workspace manager can invite members.")
        normalized_email = _normalize_email(email)
        if role not in WORKSPACE_ROLES - {"manager"}:
            raise SaaSStoreError("Invitation role must be inspector or reviewer.")
        if not 1 <= expires_days <= 30:
            raise SaaSStoreError("Invitation expiry must be between 1 and 30 days.")
        workspace_id = self._workspace_id(identity_hash)
        raw_token = secrets.token_urlsafe(32)
        token_hash = _token_hash(raw_token)
        created = datetime.now(timezone.utc)
        invitation_id = str(uuid4())
        expires = created + timedelta(days=expires_days)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_invitations(
                    invitation_id, workspace_id, email, role, token_hash,
                    created_at_utc, expires_at_utc, accepted_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    invitation_id,
                    workspace_id,
                    normalized_email,
                    role,
                    token_hash,
                    created.isoformat(),
                    expires.isoformat(),
                ),
            )
        return {
            "invitation_id": invitation_id,
            "email": normalized_email,
            "role": role,
            "expires_at_utc": expires.isoformat(),
            "invitation_token": raw_token,
        }

    def accept_invitation(
        self,
        *,
        identity_hash: str,
        email: str | None,
        display_name: str | None,
        invitation_token: str,
    ) -> dict[str, Any]:
        normalized_email = _normalize_email(email or "")
        token_hash = _token_hash(invitation_token.strip())
        now = datetime.now(timezone.utc)
        self.initialize()
        with self._connect() as connection:
            invitation = connection.execute(
                """
                SELECT * FROM workspace_invitations WHERE token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
            if invitation is None:
                raise SaaSStoreError("The workspace invitation is invalid.")
            if invitation["accepted_at_utc"] is not None:
                raise SaaSStoreError("The workspace invitation was already accepted.")
            if datetime.fromisoformat(invitation["expires_at_utc"]) <= now:
                raise SaaSStoreError("The workspace invitation has expired.")
            if not secrets.compare_digest(invitation["email"], normalized_email):
                raise SaaSStoreError("The invitation email does not match this account.")
            existing = connection.execute(
                """
                SELECT workspace_id FROM workspace_memberships WHERE identity_hash = ?
                """,
                (identity_hash,),
            ).fetchone()
            if existing is not None and existing["workspace_id"] != invitation["workspace_id"]:
                raise SaaSStoreError("This account already belongs to another workspace.")
            accepted = connection.execute(
                """
                UPDATE workspace_invitations SET accepted_at_utc = ?
                WHERE invitation_id = ? AND accepted_at_utc IS NULL
                """,
                (now.isoformat(), invitation["invitation_id"]),
            )
            if accepted.rowcount != 1:
                raise SaaSStoreError("The workspace invitation was already accepted.")
            connection.execute(
                """
                INSERT INTO workspace_memberships(
                    workspace_id, identity_hash, role, email, display_name,
                    created_at_utc, last_seen_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    invitation["workspace_id"],
                    identity_hash,
                    invitation["role"],
                    normalized_email,
                    _optional_profile_value(display_name, 120),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )
        return self.workspace(
            identity_hash,
            email=normalized_email,
            display_name=display_name,
        )

    def record_inspection(
        self,
        *,
        identity_hash: str,
        location_name: str,
        batch_reference: str,
        operator_note: str,
        analysis: Mapping[str, Any],
        model_version: str,
    ) -> dict[str, Any]:
        location_name = _bounded_required(location_name, "location_name", 80)
        batch_reference = _bounded_optional(batch_reference, "batch_reference", 100)
        operator_note = _bounded_optional(operator_note, "operator_note", 1000)
        workspace_id = self._workspace_id(identity_hash)
        now = _utc_now()
        inspection_id = str(uuid4())
        prediction = analysis.get("prediction") or {}
        reasoning = analysis.get("reasoning") or {}
        warnings = analysis.get("warnings") or []

        with self._connect() as connection:
            location_id = self._location_id(
                connection,
                workspace_id=workspace_id,
                name=location_name,
            )
            connection.execute(
                """
                INSERT INTO inspections(
                    inspection_id, workspace_id, location_id, created_at_utc,
                    batch_reference, operator_note, decision, analysis_status,
                    predicted_class, predicted_display_name, fruit,
                    predicted_freshness, confidence, risk_level, recommendation,
                    safety_notice, warnings_json, model_version, review_status,
                    reviewed_outcome, review_note, reviewed_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          'pending', NULL, '', NULL)
                """,
                (
                    inspection_id,
                    workspace_id,
                    location_id,
                    now,
                    batch_reference,
                    operator_note,
                    str(analysis.get("decision", "unknown")),
                    str(analysis.get("status", "unknown")),
                    prediction.get("class_name"),
                    prediction.get("display_name"),
                    prediction.get("fruit"),
                    prediction.get("freshness"),
                    prediction.get("confidence"),
                    reasoning.get("risk_level"),
                    str(analysis.get("recommendation", "")),
                    str(analysis.get("safety_notice", "")),
                    json.dumps(warnings, ensure_ascii=False, separators=(",", ":")),
                    model_version,
                ),
            )
        return self.inspection(identity_hash, inspection_id)

    def inspection(self, identity_hash: str, inspection_id: str) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        with self._connect() as connection:
            row = connection.execute(
                self._inspection_select() + " WHERE i.workspace_id = ? AND i.inspection_id = ?",
                (workspace_id, inspection_id),
            ).fetchone()
        if row is None:
            raise InspectionNotFoundError("Inspection not found in this workspace.")
        return _inspection_record(row)

    def list_inspections(
        self,
        identity_hash: str,
        *,
        limit: int = 50,
        review_status: str | None = None,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 200:
            raise SaaSStoreError("limit must be between 1 and 200.")
        if review_status is not None and review_status not in REVIEW_STATUSES:
            raise SaaSStoreError("review_status is invalid.")
        workspace_id = self._workspace_id(identity_hash)
        query = self._inspection_select() + " WHERE i.workspace_id = ?"
        values: list[Any] = [workspace_id]
        if review_status is not None:
            query += " AND i.review_status = ?"
            values.append(review_status)
        query += " ORDER BY i.created_at_utc DESC, i.inspection_id DESC LIMIT ?"
        values.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [_inspection_record(row) for row in rows]

    def review_inspection(
        self,
        *,
        identity_hash: str,
        inspection_id: str,
        review_status: str,
        reviewed_outcome: str | None,
        note: str,
    ) -> dict[str, Any]:
        if review_status not in REVIEW_STATUSES - {"pending"}:
            raise SaaSStoreError("review_status must complete the pending review.")
        if reviewed_outcome is not None and reviewed_outcome not in REVIEWED_OUTCOMES:
            raise SaaSStoreError("reviewed_outcome is invalid.")
        if review_status in {"confirmed", "corrected"} and reviewed_outcome is None:
            raise SaaSStoreError("A confirmed or corrected review needs an outcome.")
        note = _bounded_optional(note, "note", 1000)
        workspace_id = self._workspace_id(identity_hash)
        now = _utc_now()
        with self._connect() as connection:
            exists = connection.execute(
                """
                SELECT 1 FROM inspections
                WHERE workspace_id = ? AND inspection_id = ?
                """,
                (workspace_id, inspection_id),
            ).fetchone()
            if exists is None:
                raise InspectionNotFoundError("Inspection not found in this workspace.")
            connection.execute(
                """
                UPDATE inspections
                SET review_status = ?, reviewed_outcome = ?, review_note = ?,
                    reviewed_at_utc = ?
                WHERE workspace_id = ? AND inspection_id = ?
                """,
                (
                    review_status,
                    reviewed_outcome,
                    note,
                    now,
                    workspace_id,
                    inspection_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO review_events(
                    review_id, inspection_id, workspace_id, created_at_utc,
                    review_status, reviewed_outcome, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    inspection_id,
                    workspace_id,
                    now,
                    review_status,
                    reviewed_outcome,
                    note,
                ),
            )
        return self.inspection(identity_hash, inspection_id)

    def dashboard(self, identity_hash: str) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT decision, fruit, predicted_freshness, review_status,
                       reviewed_outcome, created_at_utc
                FROM inspections WHERE workspace_id = ?
                """,
                (workspace_id,),
            ).fetchall()
        total = len(rows)
        review_counts = {
            status: sum(row["review_status"] == status for row in rows)
            for status in REVIEW_STATUSES
        }
        fruit_counts: dict[str, int] = {}
        decision_counts: dict[str, int] = {}
        for row in rows:
            fruit = row["fruit"] or "unclassified"
            fruit_counts[fruit] = fruit_counts.get(fruit, 0) + 1
            decision = row["decision"]
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        reviewed = total - review_counts["pending"]
        false_fresh = sum(
            row["predicted_freshness"] == "fresh"
            and row["reviewed_outcome"] == "rotten"
            for row in rows
        )
        return {
            "total_inspections": total,
            "last_7_days": sum(row["created_at_utc"] >= seven_days_ago for row in rows),
            "pending_reviews": review_counts["pending"],
            "reviewed_inspections": reviewed,
            "review_completion_rate": reviewed / total if total else None,
            "false_fresh_reviews": false_fresh,
            "review_status_counts": review_counts,
            "fruit_counts": fruit_counts,
            "decision_counts": decision_counts,
        }

    def _workspace_id(self, identity_hash: str) -> str:
        identity_hash = _bounded_required(identity_hash, "identity_hash", 128)
        self.initialize()
        with self._connect() as connection:
            membership = connection.execute(
                """
                SELECT workspace_id FROM workspace_memberships WHERE identity_hash = ?
                """,
                (identity_hash,),
            ).fetchone()
            if membership is not None:
                return str(membership["workspace_id"])
            candidate_workspace_id = str(uuid4())
            now = _utc_now()
            connection.execute(
                """
                INSERT INTO workspaces(
                    workspace_id, identity_hash, display_name, created_at_utc
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    candidate_workspace_id,
                    identity_hash,
                    "FreshSense Pilot Workspace",
                    now,
                ),
            )
            row = connection.execute(
                "SELECT workspace_id FROM workspaces WHERE identity_hash = ?",
                (identity_hash,),
            ).fetchone()
            if row is None:
                raise SaaSStoreError("The workspace could not be created.")
            workspace_id = str(row["workspace_id"])
            connection.execute(
                """
                INSERT INTO workspace_memberships(
                    workspace_id, identity_hash, role, email, display_name,
                    created_at_utc, last_seen_at_utc
                ) VALUES (?, ?, 'manager', NULL, NULL, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (workspace_id, identity_hash, now, now),
            )
            connection.execute(
                """
                INSERT INTO locations(
                    location_id, workspace_id, name, created_at_utc
                )
                VALUES (?, ?, 'Main store', ?)
                ON CONFLICT DO NOTHING
                """,
                (str(uuid4()), workspace_id, now),
            )
            return workspace_id

    def _touch_member(
        self,
        *,
        workspace_id: str,
        identity_hash: str,
        email: str | None,
        display_name: str | None,
    ) -> None:
        normalized_email = _normalize_email(email) if email else None
        normalized_name = _optional_profile_value(display_name, 120)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE workspace_memberships
                SET email = COALESCE(?, email),
                    display_name = COALESCE(?, display_name),
                    last_seen_at_utc = ?
                WHERE workspace_id = ? AND identity_hash = ?
                """,
                (
                    normalized_email,
                    normalized_name,
                    _utc_now(),
                    workspace_id,
                    identity_hash,
                ),
            )

    @staticmethod
    def _location_id(
        connection: DatabaseConnection,
        *,
        workspace_id: str,
        name: str,
    ) -> str:
        candidate_location_id = str(uuid4())
        connection.execute(
            """
            INSERT INTO locations(
                location_id, workspace_id, name, created_at_utc
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            (candidate_location_id, workspace_id, name, _utc_now()),
        )
        row = connection.execute(
            """
            SELECT location_id FROM locations
            WHERE workspace_id = ? AND name = ?
            """,
            (workspace_id, name),
        ).fetchone()
        if row is None:
            raise SaaSStoreError("The inspection location could not be created.")
        return str(row["location_id"])

    @staticmethod
    def _inspection_select() -> str:
        return """
            SELECT i.*, l.name AS location_name
            FROM inspections i
            JOIN locations l ON l.location_id = i.location_id
        """

    @contextmanager
    def _connect(self):
        try:
            with self.database.connect() as connection:
                yield connection
        except (DatabaseOperationError, DatabaseConfigurationError) as exc:
            raise SaaSStoreError("The SaaS database operation failed.") from exc


def _inspection_record(row: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(row)
    value["warnings"] = json.loads(value.pop("warnings_json"))
    value["image_retained"] = False
    value.pop("workspace_id", None)
    value.pop("location_id", None)
    return value


def _member_record(row: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(row)
    value["member_id"] = value.pop("identity_hash")[:12]
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_required(value: str, name: str, maximum: int) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise SaaSStoreError(f"{name} is required.")
    if len(normalized) > maximum:
        raise SaaSStoreError(f"{name} exceeds {maximum} characters.")
    return normalized


def _bounded_optional(value: str, name: str, maximum: int) -> str:
    normalized = str(value).strip()
    if len(normalized) > maximum:
        raise SaaSStoreError(f"{name} exceeds {maximum} characters.")
    return normalized


def _optional_profile_value(value: str | None, maximum: int) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise SaaSStoreError(f"Profile value exceeds {maximum} characters.")
    return normalized


def _normalize_email(value: str) -> str:
    normalized = value.strip().casefold()
    if not normalized or "@" not in normalized or len(normalized) > 254:
        raise SaaSStoreError("A valid invitation email is required.")
    local, _, domain = normalized.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise SaaSStoreError("A valid invitation email is required.")
    return normalized


def _token_hash(token: str) -> str:
    if len(token) < 32:
        raise SaaSStoreError("The workspace invitation is invalid.")
    return sha256(token.encode("utf-8")).hexdigest()
