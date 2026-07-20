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


SCHEMA_VERSION = 5
REVIEW_STATUSES = frozenset({"pending", "confirmed", "corrected", "dismissed"})
REVIEWED_OUTCOMES = frozenset({"fresh", "rotten", "unsupported", "uncertain"})
WORKSPACE_ROLES = frozenset({"manager", "inspector", "reviewer"})
AGENT_RUN_STATUSES = frozenset({"running", "completed", "failed", "cancelled"})
AGENT_POLICY_DECISIONS = frozenset(
    {"automatic", "approval_required", "prohibited"}
)
AGENT_ACTION_TYPES = frozenset(
    {
        "complete_without_action",
        "request_retake",
        "create_review_task",
        "notify_manager",
        "hold_batch",
        "discard_inventory",
        "declare_food_safe",
    }
)
WORKFLOW_TASK_STATUSES = frozenset({"open", "completed", "cancelled"})
APPROVAL_STATUSES = frozenset({"pending", "approved", "rejected"})
ACTION_EXECUTION_STATUSES = frozenset(
    {"pending", "shadow_only", "executed", "awaiting_approval", "blocked", "failed"}
)
CONVERSATION_STATUSES = frozenset({"active", "archived"})
CHAT_MESSAGE_ROLES = frozenset({"user", "assistant"})
ASSISTANT_LANGUAGES = frozenset({"auto", "en", "zh"})
ASSISTANT_RESPONSE_DETAILS = frozenset({"concise", "standard", "detailed"})
ASSISTANT_REVIEW_FOCUSES = frozenset({"balanced", "freshness_risk", "operations"})


class SaaSStoreError(RuntimeError):
    """Raised when SaaS metadata cannot be validated or persisted."""


class InspectionNotFoundError(SaaSStoreError):
    """Raised when an inspection is absent from the authenticated workspace."""


class AgentRunNotFoundError(SaaSStoreError):
    """Raised when an agent run is absent from the authenticated workspace."""


class ConversationNotFoundError(SaaSStoreError):
    """Raised when a manager conversation is absent from the workspace."""


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

                    CREATE TABLE IF NOT EXISTS agent_runs (
                        run_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        inspection_id TEXT NOT NULL,
                        created_by_identity_hash TEXT NOT NULL,
                        mode TEXT NOT NULL,
                        objective TEXT NOT NULL,
                        planner_version TEXT NOT NULL,
                        status TEXT NOT NULL,
                        max_steps INTEGER NOT NULL,
                        steps_completed INTEGER NOT NULL,
                        final_summary TEXT NOT NULL,
                        error_code TEXT,
                        created_at_utc TEXT NOT NULL,
                        completed_at_utc TEXT,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id),
                        FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id)
                    );

                    CREATE TABLE IF NOT EXISTS agent_steps (
                        step_id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        step_index INTEGER NOT NULL,
                        step_kind TEXT NOT NULL,
                        tool_name TEXT,
                        rationale TEXT NOT NULL,
                        input_json TEXT NOT NULL,
                        output_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        FOREIGN KEY(run_id) REFERENCES agent_runs(run_id),
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id),
                        UNIQUE(run_id, step_index)
                    );

                    CREATE TABLE IF NOT EXISTS action_proposals (
                        proposal_id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        inspection_id TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        policy_decision TEXT NOT NULL,
                        execution_status TEXT NOT NULL,
                        rationale TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        resolved_at_utc TEXT,
                        resolved_by_identity_hash TEXT,
                        FOREIGN KEY(run_id) REFERENCES agent_runs(run_id),
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id),
                        FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id)
                    );

                    CREATE TABLE IF NOT EXISTS workflow_tasks (
                        task_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        inspection_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        task_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        priority TEXT NOT NULL,
                        title TEXT NOT NULL,
                        instructions TEXT NOT NULL,
                        assigned_role TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        completed_at_utc TEXT,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id),
                        FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id),
                        FOREIGN KEY(run_id) REFERENCES agent_runs(run_id)
                    );

                    CREATE TABLE IF NOT EXISTS notifications (
                        notification_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        recipient_role TEXT NOT NULL,
                        kind TEXT NOT NULL,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        related_type TEXT NOT NULL,
                        related_id TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        read_at_utc TEXT,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
                    );

                    CREATE TABLE IF NOT EXISTS approval_requests (
                        approval_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        inspection_id TEXT NOT NULL,
                        run_id TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        status TEXT NOT NULL,
                        rationale TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        requested_at_utc TEXT NOT NULL,
                        resolved_at_utc TEXT,
                        resolved_by_identity_hash TEXT,
                        resolution_note TEXT NOT NULL,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id),
                        FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id),
                        FOREIGN KEY(run_id) REFERENCES agent_runs(run_id)
                    );

                    CREATE TABLE IF NOT EXISTS agent_memory (
                        memory_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        inspection_id TEXT NOT NULL,
                        memory_kind TEXT NOT NULL,
                        fruit TEXT,
                        location_name TEXT NOT NULL,
                        batch_reference TEXT NOT NULL,
                        predicted_outcome TEXT,
                        reviewed_outcome TEXT,
                        content_json TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id),
                        FOREIGN KEY(inspection_id) REFERENCES inspections(inspection_id)
                    );

                    CREATE TABLE IF NOT EXISTS manager_conversations (
                        conversation_id TEXT PRIMARY KEY,
                        workspace_id TEXT NOT NULL,
                        created_by_identity_hash TEXT NOT NULL,
                        title TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
                    );

                    CREATE TABLE IF NOT EXISTS manager_messages (
                        message_id TEXT PRIMARY KEY,
                        conversation_id TEXT NOT NULL,
                        workspace_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        citations_json TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        created_at_utc TEXT NOT NULL,
                        FOREIGN KEY(conversation_id) REFERENCES manager_conversations(conversation_id),
                        FOREIGN KEY(workspace_id) REFERENCES workspaces(workspace_id)
                    );

                    CREATE TABLE IF NOT EXISTS manager_preferences (
                        workspace_id TEXT NOT NULL,
                        identity_hash TEXT NOT NULL,
                        preferred_language TEXT NOT NULL,
                        response_detail TEXT NOT NULL,
                        default_location_name TEXT NOT NULL,
                        review_focus TEXT NOT NULL,
                        custom_instructions TEXT NOT NULL,
                        updated_at_utc TEXT NOT NULL,
                        PRIMARY KEY(workspace_id, identity_hash),
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
                    CREATE INDEX IF NOT EXISTS idx_agent_runs_workspace_created
                        ON agent_runs(workspace_id, created_at_utc DESC);
                    CREATE INDEX IF NOT EXISTS idx_agent_steps_run
                        ON agent_steps(run_id, step_index);
                    CREATE INDEX IF NOT EXISTS idx_action_proposals_workspace
                        ON action_proposals(workspace_id, created_at_utc DESC);
                    CREATE INDEX IF NOT EXISTS idx_workflow_tasks_workspace_status
                        ON workflow_tasks(workspace_id, status, created_at_utc DESC);
                    CREATE INDEX IF NOT EXISTS idx_notifications_workspace_created
                        ON notifications(workspace_id, created_at_utc DESC);
                    CREATE INDEX IF NOT EXISTS idx_approvals_workspace_status
                        ON approval_requests(workspace_id, status, requested_at_utc DESC);
                    CREATE INDEX IF NOT EXISTS idx_agent_memory_workspace_created
                        ON agent_memory(workspace_id, created_at_utc DESC);
                    CREATE INDEX IF NOT EXISTS idx_manager_conversations_workspace_updated
                        ON manager_conversations(workspace_id, updated_at_utc DESC);
                    CREATE INDEX IF NOT EXISTS idx_manager_messages_conversation_created
                        ON manager_messages(conversation_id, created_at_utc, message_id);
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
                    elif int(row["value"]) in {1, 2, 3, 4}:
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
            inspection = connection.execute(
                """
                SELECT i.fruit, i.predicted_freshness, i.batch_reference,
                       l.name AS location_name
                FROM inspections i
                JOIN locations l ON l.location_id = i.location_id
                WHERE i.workspace_id = ? AND i.inspection_id = ?
                """,
                (workspace_id, inspection_id),
            ).fetchone()
            if inspection is None:
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
            memory_content = {
                "review_status": review_status,
                "reviewed_outcome": reviewed_outcome,
                "note": note,
                "prediction_matched_review": (
                    reviewed_outcome is not None
                    and reviewed_outcome == inspection["predicted_freshness"]
                ),
            }
            connection.execute(
                """
                INSERT INTO agent_memory(
                    memory_id, workspace_id, inspection_id, memory_kind, fruit,
                    location_name, batch_reference, predicted_outcome,
                    reviewed_outcome, content_json, created_at_utc
                ) VALUES (?, ?, ?, 'human_review', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    workspace_id,
                    inspection_id,
                    inspection["fruit"],
                    inspection["location_name"],
                    inspection["batch_reference"],
                    inspection["predicted_freshness"],
                    reviewed_outcome,
                    _bounded_json(memory_content, "memory_content", 100_000),
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE workflow_tasks
                SET status = 'completed', completed_at_utc = ?
                WHERE workspace_id = ? AND inspection_id = ?
                  AND status = 'open'
                  AND task_type IN ('create_review_task', 'request_retake')
                """,
                (now, workspace_id, inspection_id),
            )
            self._insert_notification(
                connection,
                workspace_id=workspace_id,
                recipient_role="manager",
                kind="review_completed",
                title="Human review completed",
                message=(
                    f"{inspection['location_name']}: {review_status} review recorded "
                    f"for {inspection['fruit'] or 'unclassified input'}."
                ),
                related_type="inspection",
                related_id=inspection_id,
                created_at_utc=now,
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

    def create_agent_run(
        self,
        *,
        identity_hash: str,
        inspection_id: str,
        objective: str,
        planner_version: str,
        max_steps: int,
        mode: str = "shadow",
    ) -> dict[str, Any]:
        if not 1 <= max_steps <= 20:
            raise SaaSStoreError("Agent max_steps must be between 1 and 20.")
        if mode not in {"shadow", "supervised"}:
            raise SaaSStoreError("Agent mode is invalid.")
        objective = _bounded_required(objective, "objective", 2000)
        planner_version = _bounded_required(
            planner_version,
            "planner_version",
            100,
        )
        workspace_id = self._workspace_id(identity_hash)
        self._require_workspace_inspection(
            workspace_id=workspace_id,
            inspection_id=inspection_id,
        )
        run_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_runs(
                    run_id, workspace_id, inspection_id, created_by_identity_hash,
                    mode, objective, planner_version, status, max_steps,
                    steps_completed, final_summary, error_code, created_at_utc,
                    completed_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', ?, 0, '', NULL, ?, NULL)
                """,
                (
                    run_id,
                    workspace_id,
                    inspection_id,
                    identity_hash,
                    mode,
                    objective,
                    planner_version,
                    max_steps,
                    _utc_now(),
                ),
            )
        return self.agent_run(identity_hash, run_id)

    def append_agent_step(
        self,
        *,
        identity_hash: str,
        run_id: str,
        step_index: int,
        step_kind: str,
        tool_name: str | None,
        rationale: str,
        input_data: Mapping[str, Any],
        output_data: Mapping[str, Any],
        status: str,
    ) -> dict[str, Any]:
        if not 1 <= step_index <= 20:
            raise SaaSStoreError("Agent step_index must be between 1 and 20.")
        if step_kind not in {"tool", "finish"}:
            raise SaaSStoreError("Agent step_kind is invalid.")
        if status not in {"completed", "failed"}:
            raise SaaSStoreError("Agent step status is invalid.")
        workspace_id = self._workspace_id(identity_hash)
        self._require_workspace_agent_run(
            workspace_id=workspace_id,
            run_id=run_id,
            required_status="running",
        )
        rationale = _bounded_required(rationale, "rationale", 2000)
        normalized_tool = (
            _bounded_required(tool_name, "tool_name", 80)
            if tool_name is not None
            else None
        )
        input_json = _bounded_json(input_data, "input_data", 100_000)
        output_json = _bounded_json(output_data, "output_data", 250_000)
        step_id = str(uuid4())
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_steps(
                    step_id, run_id, workspace_id, step_index, step_kind,
                    tool_name, rationale, input_json, output_json, status,
                    created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step_id,
                    run_id,
                    workspace_id,
                    step_index,
                    step_kind,
                    normalized_tool,
                    rationale,
                    input_json,
                    output_json,
                    status,
                    now,
                ),
            )
            connection.execute(
                """
                UPDATE agent_runs SET steps_completed = ?
                WHERE workspace_id = ? AND run_id = ?
                """,
                (step_index, workspace_id, run_id),
            )
        return {
            "step_id": step_id,
            "run_id": run_id,
            "step_index": step_index,
            "step_kind": step_kind,
            "tool_name": normalized_tool,
            "rationale": rationale,
            "input": json.loads(input_json),
            "output": json.loads(output_json),
            "status": status,
            "created_at_utc": now,
        }

    def create_action_proposal(
        self,
        *,
        identity_hash: str,
        run_id: str,
        inspection_id: str,
        action_type: str,
        policy_decision: str,
        rationale: str,
        payload: Mapping[str, Any],
        execution_status: str = "shadow_only",
    ) -> dict[str, Any]:
        if policy_decision not in AGENT_POLICY_DECISIONS:
            raise SaaSStoreError("Agent policy_decision is invalid.")
        if action_type not in AGENT_ACTION_TYPES:
            raise SaaSStoreError("Agent action_type is invalid.")
        if execution_status not in ACTION_EXECUTION_STATUSES:
            raise SaaSStoreError("Agent execution_status is invalid.")
        workspace_id = self._workspace_id(identity_hash)
        self._require_workspace_agent_run(
            workspace_id=workspace_id,
            run_id=run_id,
            required_status="running",
        )
        self._require_workspace_inspection(
            workspace_id=workspace_id,
            inspection_id=inspection_id,
        )
        action_type = _bounded_required(action_type, "action_type", 80)
        rationale = _bounded_required(rationale, "rationale", 2000)
        payload_json = _bounded_json(payload, "payload", 100_000)
        proposal_id = str(uuid4())
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO action_proposals(
                    proposal_id, run_id, workspace_id, inspection_id,
                    action_type, policy_decision, execution_status, rationale,
                    payload_json, created_at_utc, resolved_at_utc,
                    resolved_by_identity_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    proposal_id,
                    run_id,
                    workspace_id,
                    inspection_id,
                    action_type,
                    policy_decision,
                    execution_status,
                    rationale,
                    payload_json,
                    now,
                ),
            )
        return {
            "proposal_id": proposal_id,
            "run_id": run_id,
            "inspection_id": inspection_id,
            "action_type": action_type,
            "policy_decision": policy_decision,
            "execution_status": execution_status,
            "rationale": rationale,
            "payload": json.loads(payload_json),
            "created_at_utc": now,
            "resolved_at_utc": None,
        }

    def complete_agent_run(
        self,
        *,
        identity_hash: str,
        run_id: str,
        final_summary: str,
    ) -> dict[str, Any]:
        return self._finish_agent_run(
            identity_hash=identity_hash,
            run_id=run_id,
            status="completed",
            final_summary=_bounded_required(
                final_summary,
                "final_summary",
                4000,
            ),
            error_code=None,
        )

    def fail_agent_run(
        self,
        *,
        identity_hash: str,
        run_id: str,
        error_code: str,
    ) -> dict[str, Any]:
        return self._finish_agent_run(
            identity_hash=identity_hash,
            run_id=run_id,
            status="failed",
            final_summary="The bounded agent stopped before completing its workflow.",
            error_code=_bounded_required(error_code, "error_code", 120),
        )

    def agent_run(self, identity_hash: str, run_id: str) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        with self._connect() as connection:
            run = connection.execute(
                """
                SELECT run_id, inspection_id, mode, objective, planner_version,
                       status, max_steps, steps_completed, final_summary,
                       error_code, created_at_utc, completed_at_utc
                FROM agent_runs
                WHERE workspace_id = ? AND run_id = ?
                """,
                (workspace_id, run_id),
            ).fetchone()
            if run is None:
                raise AgentRunNotFoundError(
                    "Agent run not found in this workspace."
                )
            steps = connection.execute(
                """
                SELECT step_id, run_id, step_index, step_kind, tool_name,
                       rationale, input_json, output_json, status, created_at_utc
                FROM agent_steps
                WHERE workspace_id = ? AND run_id = ?
                ORDER BY step_index
                """,
                (workspace_id, run_id),
            ).fetchall()
            proposals = connection.execute(
                """
                SELECT proposal_id, run_id, inspection_id, action_type,
                       policy_decision, execution_status, rationale, payload_json,
                       created_at_utc, resolved_at_utc
                FROM action_proposals
                WHERE workspace_id = ? AND run_id = ?
                ORDER BY created_at_utc
                """,
                (workspace_id, run_id),
            ).fetchall()
        return {
            **dict(run),
            "steps": [_agent_step_record(row) for row in steps],
            "action_proposals": [_action_proposal_record(row) for row in proposals],
        }

    def list_agent_runs(
        self,
        identity_hash: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise SaaSStoreError("limit must be between 1 and 100.")
        workspace_id = self._workspace_id(identity_hash)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT run_id FROM agent_runs
                WHERE workspace_id = ?
                ORDER BY created_at_utc DESC, run_id DESC LIMIT ?
                """,
                (workspace_id, limit),
            ).fetchall()
        return [self.agent_run(identity_hash, str(row["run_id"])) for row in rows]

    def execute_agent_action(
        self,
        *,
        identity_hash: str,
        run_id: str,
        proposal_id: str,
        inspection_id: str,
        action_type: str,
        rationale: str,
    ) -> dict[str, Any]:
        """Execute only reversible workflow actions inside FreshSense."""
        if action_type not in {
            "complete_without_action",
            "request_retake",
            "create_review_task",
            "notify_manager",
        }:
            raise SaaSStoreError("This agent action cannot execute automatically.")
        workspace_id = self._workspace_id(identity_hash)
        self._require_workspace_agent_run(
            workspace_id=workspace_id,
            run_id=run_id,
            required_status="running",
        )
        inspection = self.inspection(identity_hash, inspection_id)
        now = _utc_now()
        task: dict[str, Any] | None = None
        notification: dict[str, Any] | None = None
        with self._connect() as connection:
            proposal = connection.execute(
                """
                SELECT execution_status FROM action_proposals
                WHERE workspace_id = ? AND run_id = ? AND proposal_id = ?
                """,
                (workspace_id, run_id, proposal_id),
            ).fetchone()
            if proposal is None or proposal["execution_status"] != "pending":
                raise SaaSStoreError("The agent proposal is not executable.")

            if action_type in {"request_retake", "create_review_task"}:
                task_id = str(uuid4())
                is_retake = action_type == "request_retake"
                title = "Retake fruit photo" if is_retake else "Review AI inspection"
                assigned_role = "inspector" if is_retake else "reviewer"
                priority = "normal" if is_retake else "high"
                connection.execute(
                    """
                    INSERT INTO workflow_tasks(
                        task_id, workspace_id, inspection_id, run_id, task_type,
                        status, priority, title, instructions, assigned_role,
                        created_at_utc, completed_at_utc
                    ) VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        task_id,
                        workspace_id,
                        inspection_id,
                        run_id,
                        action_type,
                        priority,
                        title,
                        rationale,
                        assigned_role,
                        now,
                    ),
                )
                task = {
                    "task_id": task_id,
                    "task_type": action_type,
                    "status": "open",
                    "assigned_role": assigned_role,
                }
                notification = self._insert_notification(
                    connection,
                    workspace_id=workspace_id,
                    recipient_role=assigned_role,
                    kind="workflow_task_created",
                    title=title,
                    message=(
                        f"{inspection.get('location_name')}: {rationale}"
                    ),
                    related_type="task",
                    related_id=task_id,
                    created_at_utc=now,
                )
            elif action_type == "notify_manager":
                notification = self._insert_notification(
                    connection,
                    workspace_id=workspace_id,
                    recipient_role="manager",
                    kind="manager_attention",
                    title="Inspection needs manager attention",
                    message=rationale,
                    related_type="inspection",
                    related_id=inspection_id,
                    created_at_utc=now,
                )

            connection.execute(
                """
                UPDATE action_proposals
                SET execution_status = 'executed', resolved_at_utc = ?,
                    resolved_by_identity_hash = ?
                WHERE workspace_id = ? AND proposal_id = ?
                """,
                (now, identity_hash, workspace_id, proposal_id),
            )
        return {"status": "executed", "task": task, "notification": notification}

    def request_agent_approval(
        self,
        *,
        identity_hash: str,
        run_id: str,
        proposal_id: str,
        inspection_id: str,
        action_type: str,
        rationale: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        if action_type != "hold_batch":
            raise SaaSStoreError("Only batch holds use the approval workflow.")
        workspace_id = self._workspace_id(identity_hash)
        self._require_workspace_agent_run(
            workspace_id=workspace_id,
            run_id=run_id,
            required_status="running",
        )
        approval_id = str(uuid4())
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO approval_requests(
                    approval_id, workspace_id, inspection_id, run_id,
                    action_type, status, rationale, payload_json,
                    requested_at_utc, resolved_at_utc,
                    resolved_by_identity_hash, resolution_note
                ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, NULL, NULL, '')
                """,
                (
                    approval_id,
                    workspace_id,
                    inspection_id,
                    run_id,
                    action_type,
                    _bounded_required(rationale, "rationale", 2000),
                    _bounded_json(payload, "payload", 100_000),
                    now,
                ),
            )
            self._insert_notification(
                connection,
                workspace_id=workspace_id,
                recipient_role="manager",
                kind="approval_requested",
                title="Batch hold requires approval",
                message=rationale,
                related_type="approval",
                related_id=approval_id,
                created_at_utc=now,
            )
            connection.execute(
                """
                UPDATE action_proposals SET execution_status = 'awaiting_approval'
                WHERE workspace_id = ? AND proposal_id = ?
                  AND execution_status = 'pending'
                """,
                (workspace_id, proposal_id),
            )
        return self.approval(identity_hash, approval_id)

    def set_action_proposal_status(
        self,
        *,
        identity_hash: str,
        proposal_id: str,
        execution_status: str,
    ) -> None:
        if execution_status not in ACTION_EXECUTION_STATUSES - {"pending"}:
            raise SaaSStoreError("Agent execution_status is invalid.")
        workspace_id = self._workspace_id(identity_hash)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE action_proposals
                SET execution_status = ?, resolved_at_utc = ?,
                    resolved_by_identity_hash = ?
                WHERE workspace_id = ? AND proposal_id = ?
                  AND execution_status = 'pending'
                """,
                (
                    execution_status,
                    _utc_now(),
                    identity_hash,
                    workspace_id,
                    proposal_id,
                ),
            )
        if cursor.rowcount != 1:
            raise SaaSStoreError("The agent proposal could not be resolved.")

    def notify_analysis_completed(
        self,
        *,
        identity_hash: str,
        inspection_id: str,
        message: str,
    ) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        now = _utc_now()
        with self._connect() as connection:
            return self._insert_notification(
                connection,
                workspace_id=workspace_id,
                recipient_role="all",
                kind="inspection_completed",
                title="Fruit inspection completed",
                message=message,
                related_type="inspection",
                related_id=inspection_id,
                created_at_utc=now,
            )

    def list_workflow_tasks(
        self,
        identity_hash: str,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if status is not None and status not in WORKFLOW_TASK_STATUSES:
            raise SaaSStoreError("Workflow task status is invalid.")
        if not 1 <= limit <= 200:
            raise SaaSStoreError("limit must be between 1 and 200.")
        workspace_id = self._workspace_id(identity_hash)
        role = self._workspace_role(workspace_id, identity_hash)
        query = """
            SELECT * FROM workflow_tasks
            WHERE workspace_id = ? AND (assigned_role = ? OR ? = 'manager')
        """
        values: list[Any] = [workspace_id, role, role]
        if status is not None:
            query += " AND status = ?"
            values.append(status)
        query += " ORDER BY created_at_utc DESC, task_id DESC LIMIT ?"
        values.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._public_row(row, "workspace_id") for row in rows]

    def list_notifications(
        self,
        identity_hash: str,
        *,
        unread_only: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 200:
            raise SaaSStoreError("limit must be between 1 and 200.")
        workspace_id = self._workspace_id(identity_hash)
        role = self._workspace_role(workspace_id, identity_hash)
        query = """
            SELECT * FROM notifications
            WHERE workspace_id = ? AND recipient_role IN (?, 'all')
        """
        values: list[Any] = [workspace_id, role]
        if unread_only:
            query += " AND read_at_utc IS NULL"
        query += " ORDER BY created_at_utc DESC, notification_id DESC LIMIT ?"
        values.append(limit)
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._public_row(row, "workspace_id") for row in rows]

    def mark_notification_read(
        self,
        *,
        identity_hash: str,
        notification_id: str,
    ) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        role = self._workspace_role(workspace_id, identity_hash)
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE notifications SET read_at_utc = ?
                WHERE workspace_id = ? AND notification_id = ?
                  AND recipient_role IN (?, 'all')
                """,
                (_utc_now(), workspace_id, notification_id, role),
            )
            row = connection.execute(
                """
                SELECT * FROM notifications
                WHERE workspace_id = ? AND notification_id = ?
                  AND recipient_role IN (?, 'all')
                """,
                (workspace_id, notification_id, role),
            ).fetchone()
        if row is None:
            raise SaaSStoreError("Notification not found in this workspace.")
        return self._public_row(row, "workspace_id")

    def list_approvals(
        self,
        identity_hash: str,
        *,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        if status is not None and status not in APPROVAL_STATUSES:
            raise SaaSStoreError("Approval status is invalid.")
        workspace_id = self._workspace_id(identity_hash)
        query = "SELECT * FROM approval_requests WHERE workspace_id = ?"
        values: list[Any] = [workspace_id]
        if status is not None:
            query += " AND status = ?"
            values.append(status)
        query += " ORDER BY requested_at_utc DESC, approval_id DESC"
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._approval_record(row) for row in rows]

    def approval(self, identity_hash: str, approval_id: str) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM approval_requests WHERE workspace_id = ? AND approval_id = ?",
                (workspace_id, approval_id),
            ).fetchone()
        if row is None:
            raise SaaSStoreError("Approval not found in this workspace.")
        return self._approval_record(row)

    def resolve_approval(
        self,
        *,
        identity_hash: str,
        approval_id: str,
        decision: str,
        note: str,
    ) -> dict[str, Any]:
        if decision not in {"approved", "rejected"}:
            raise SaaSStoreError("Approval decision is invalid.")
        workspace_id = self._workspace_id(identity_hash)
        if self._workspace_role(workspace_id, identity_hash) != "manager":
            raise SaaSStoreError("Only a workspace manager can resolve approvals.")
        note = _bounded_optional(note, "note", 1000)
        now = _utc_now()
        with self._connect() as connection:
            approval = connection.execute(
                """
                SELECT * FROM approval_requests
                WHERE workspace_id = ? AND approval_id = ? AND status = 'pending'
                """,
                (workspace_id, approval_id),
            ).fetchone()
            if approval is None:
                raise SaaSStoreError("The approval is not pending.")
            connection.execute(
                """
                UPDATE approval_requests
                SET status = ?, resolved_at_utc = ?,
                    resolved_by_identity_hash = ?, resolution_note = ?
                WHERE workspace_id = ? AND approval_id = ?
                """,
                (decision, now, identity_hash, note, workspace_id, approval_id),
            )
            proposal_status = "executed" if decision == "approved" else "blocked"
            connection.execute(
                """
                UPDATE action_proposals
                SET execution_status = ?, resolved_at_utc = ?,
                    resolved_by_identity_hash = ?
                WHERE workspace_id = ? AND run_id = ? AND action_type = ?
                """,
                (
                    proposal_status,
                    now,
                    identity_hash,
                    workspace_id,
                    approval["run_id"],
                    approval["action_type"],
                ),
            )
            if decision == "approved":
                task_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO workflow_tasks(
                        task_id, workspace_id, inspection_id, run_id, task_type,
                        status, priority, title, instructions, assigned_role,
                        created_at_utc, completed_at_utc
                    ) VALUES (?, ?, ?, ?, 'approved_hold_batch', 'open', 'urgent',
                              'Apply approved batch hold', ?, 'manager', ?, NULL)
                    """,
                    (
                        task_id,
                        workspace_id,
                        approval["inspection_id"],
                        approval["run_id"],
                        approval["rationale"],
                        now,
                    ),
                )
            self._insert_notification(
                connection,
                workspace_id=workspace_id,
                recipient_role="all",
                kind="approval_resolved",
                title=f"Batch hold {decision}",
                message=note or f"A manager {decision} the proposed batch hold.",
                related_type="approval",
                related_id=approval_id,
                created_at_utc=now,
            )
        return self.approval(identity_hash, approval_id)

    def list_agent_memory(
        self,
        identity_hash: str,
        *,
        fruit: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        workspace_id = self._workspace_id(identity_hash)
        query = "SELECT * FROM agent_memory WHERE workspace_id = ?"
        values: list[Any] = [workspace_id]
        if fruit:
            query += " AND fruit = ?"
            values.append(_bounded_required(fruit, "fruit", 80))
        query += " ORDER BY created_at_utc DESC, memory_id DESC LIMIT ?"
        values.append(max(1, min(limit, 200)))
        with self._connect() as connection:
            rows = connection.execute(query, values).fetchall()
        records = []
        for row in rows:
            value = self._public_row(row, "workspace_id")
            value["content"] = json.loads(value.pop("content_json"))
            records.append(value)
        return records

    def manager_preferences(self, identity_hash: str) -> dict[str, Any]:
        """Return durable, per-manager response preferences for this workspace."""

        workspace_id = self._workspace_id(identity_hash)
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO manager_preferences(
                    workspace_id, identity_hash, preferred_language,
                    response_detail, default_location_name, review_focus,
                    custom_instructions, updated_at_utc
                ) VALUES (?, ?, 'auto', 'standard', '', 'balanced', '', ?)
                ON CONFLICT DO NOTHING
                """,
                (workspace_id, identity_hash, now),
            )
            row = connection.execute(
                """
                SELECT preferred_language, response_detail, default_location_name,
                       review_focus, custom_instructions, updated_at_utc
                FROM manager_preferences
                WHERE workspace_id = ? AND identity_hash = ?
                """,
                (workspace_id, identity_hash),
            ).fetchone()
        if row is None:
            raise SaaSStoreError("Manager preferences could not be loaded.")
        return dict(row)

    def update_manager_preferences(
        self,
        *,
        identity_hash: str,
        preferred_language: str | None = None,
        response_detail: str | None = None,
        default_location_name: str | None = None,
        review_focus: str | None = None,
        custom_instructions: str | None = None,
    ) -> dict[str, Any]:
        current = self.manager_preferences(identity_hash)
        language = preferred_language or str(current["preferred_language"])
        detail = response_detail or str(current["response_detail"])
        focus = review_focus or str(current["review_focus"])
        location = (
            str(current["default_location_name"])
            if default_location_name is None
            else _bounded_optional(default_location_name, "default_location_name", 80)
        )
        instructions = (
            str(current["custom_instructions"])
            if custom_instructions is None
            else _bounded_optional(custom_instructions, "custom_instructions", 600)
        )
        if language not in ASSISTANT_LANGUAGES:
            raise SaaSStoreError("preferred_language is invalid.")
        if detail not in ASSISTANT_RESPONSE_DETAILS:
            raise SaaSStoreError("response_detail is invalid.")
        if focus not in ASSISTANT_REVIEW_FOCUSES:
            raise SaaSStoreError("review_focus is invalid.")

        workspace_id = self._workspace_id(identity_hash)
        if location:
            with self._connect() as connection:
                found = connection.execute(
                    "SELECT 1 FROM locations WHERE workspace_id = ? AND name = ?",
                    (workspace_id, location),
                ).fetchone()
            if found is None:
                raise SaaSStoreError("default_location_name is not in this workspace.")

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE manager_preferences
                SET preferred_language = ?, response_detail = ?,
                    default_location_name = ?, review_focus = ?,
                    custom_instructions = ?, updated_at_utc = ?
                WHERE workspace_id = ? AND identity_hash = ?
                """,
                (
                    language,
                    detail,
                    location,
                    focus,
                    instructions,
                    _utc_now(),
                    workspace_id,
                    identity_hash,
                ),
            )
        return self.manager_preferences(identity_hash)

    def create_manager_conversation(
        self,
        *,
        identity_hash: str,
        title: str = "New conversation",
    ) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        conversation_id = str(uuid4())
        now = _utc_now()
        normalized_title = _bounded_required(title, "title", 120)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO manager_conversations(
                    conversation_id, workspace_id, created_by_identity_hash,
                    title, status, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, 'active', ?, ?)
                """,
                (
                    conversation_id,
                    workspace_id,
                    identity_hash,
                    normalized_title,
                    now,
                    now,
                ),
            )
        return self.manager_conversation(identity_hash, conversation_id)

    def list_manager_conversations(
        self,
        identity_hash: str,
        *,
        limit: int = 30,
        status: str = "active",
    ) -> list[dict[str, Any]]:
        if status not in CONVERSATION_STATUSES:
            raise SaaSStoreError("Conversation status is invalid.")
        if not 1 <= limit <= 100:
            raise SaaSStoreError("limit must be between 1 and 100.")
        workspace_id = self._workspace_id(identity_hash)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT c.conversation_id, c.title, c.status, c.created_at_utc,
                       c.updated_at_utc,
                       (SELECT COUNT(*) FROM manager_messages m
                        WHERE m.conversation_id = c.conversation_id) AS message_count,
                       (SELECT m.content FROM manager_messages m
                        WHERE m.conversation_id = c.conversation_id
                        ORDER BY m.created_at_utc DESC, m.message_id DESC LIMIT 1)
                        AS last_message
                FROM manager_conversations c
                WHERE c.workspace_id = ? AND c.created_by_identity_hash = ?
                  AND c.status = ?
                ORDER BY c.updated_at_utc DESC, c.conversation_id DESC
                LIMIT ?
                """,
                (workspace_id, identity_hash, status, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def manager_conversation(
        self,
        identity_hash: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        conversation_id = _bounded_required(conversation_id, "conversation_id", 64)
        with self._connect() as connection:
            conversation = connection.execute(
                """
                SELECT conversation_id, title, status, created_at_utc, updated_at_utc
                FROM manager_conversations
                WHERE workspace_id = ? AND created_by_identity_hash = ?
                  AND conversation_id = ?
                """,
                (workspace_id, identity_hash, conversation_id),
            ).fetchone()
            if conversation is None:
                raise ConversationNotFoundError(
                    "Conversation not found in this workspace."
                )
            messages = connection.execute(
                """
                SELECT message_id, conversation_id, role, content,
                       citations_json, metadata_json, created_at_utc
                FROM manager_messages
                WHERE workspace_id = ? AND conversation_id = ?
                ORDER BY created_at_utc, message_id
                """,
                (workspace_id, conversation_id),
            ).fetchall()
        return {
            **dict(conversation),
            "messages": [_manager_message_record(row) for row in messages],
        }

    def add_manager_message(
        self,
        *,
        identity_hash: str,
        conversation_id: str,
        role: str,
        content: str,
        citations: list[Mapping[str, Any]] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if role not in CHAT_MESSAGE_ROLES:
            raise SaaSStoreError("Chat message role is invalid.")
        maximum = 4_000 if role == "user" else 10_000
        normalized_content = _bounded_required(content, "content", maximum)
        workspace_id = self._workspace_id(identity_hash)
        conversation_id = _bounded_required(conversation_id, "conversation_id", 64)
        now = _utc_now()
        message_id = str(uuid4())
        citation_values = list(citations or [])
        metadata_value = dict(metadata or {})
        citations_json = _bounded_json_value(
            citation_values,
            "citations",
            100_000,
        )
        metadata_json = _bounded_json_value(
            metadata_value,
            "message_metadata",
            100_000,
        )
        with self._connect() as connection:
            conversation = connection.execute(
                """
                SELECT title FROM manager_conversations
                WHERE workspace_id = ? AND created_by_identity_hash = ?
                  AND conversation_id = ? AND status = 'active'
                """,
                (workspace_id, identity_hash, conversation_id),
            ).fetchone()
            if conversation is None:
                raise ConversationNotFoundError(
                    "Conversation not found in this workspace."
                )
            existing_count = connection.execute(
                "SELECT COUNT(*) AS count FROM manager_messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            connection.execute(
                """
                INSERT INTO manager_messages(
                    message_id, conversation_id, workspace_id, role, content,
                    citations_json, metadata_json, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    workspace_id,
                    role,
                    normalized_content,
                    citations_json,
                    metadata_json,
                    now,
                ),
            )
            title = str(conversation["title"])
            if (
                role == "user"
                and title == "New conversation"
                and int(existing_count["count"] if existing_count else 0) == 0
            ):
                title = _chat_title(normalized_content)
            connection.execute(
                """
                UPDATE manager_conversations
                SET title = ?, updated_at_utc = ?
                WHERE workspace_id = ? AND conversation_id = ?
                """,
                (title, now, workspace_id, conversation_id),
            )
            row = connection.execute(
                """
                SELECT message_id, conversation_id, role, content,
                       citations_json, metadata_json, created_at_utc
                FROM manager_messages WHERE message_id = ?
                """,
                (message_id,),
            ).fetchone()
        if row is None:
            raise SaaSStoreError("The chat message could not be stored.")
        return _manager_message_record(row)

    def archive_manager_conversation(
        self,
        *,
        identity_hash: str,
        conversation_id: str,
    ) -> dict[str, Any]:
        workspace_id = self._workspace_id(identity_hash)
        with self._connect() as connection:
            changed = connection.execute(
                """
                UPDATE manager_conversations
                SET status = 'archived', updated_at_utc = ?
                WHERE workspace_id = ? AND created_by_identity_hash = ?
                  AND conversation_id = ? AND status = 'active'
                """,
                (_utc_now(), workspace_id, identity_hash, conversation_id),
            )
        if changed.rowcount != 1:
            raise ConversationNotFoundError(
                "Conversation not found in this workspace."
            )
        return self.manager_conversation(identity_hash, conversation_id)

    def daily_report(self, identity_hash: str, report_date: str) -> dict[str, Any]:
        try:
            day = datetime.strptime(report_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise SaaSStoreError("report_date must use YYYY-MM-DD.") from exc
        start = day.isoformat()
        end = (day + timedelta(days=1)).isoformat()
        workspace_id = self._workspace_id(identity_hash)
        with self._connect() as connection:
            inspections = connection.execute(
                """
                SELECT predicted_freshness, decision, review_status, reviewed_outcome,
                       fruit, confidence FROM inspections
                WHERE workspace_id = ? AND created_at_utc >= ? AND created_at_utc < ?
                """,
                (workspace_id, start, end),
            ).fetchall()
            open_tasks = connection.execute(
                "SELECT COUNT(*) AS count FROM workflow_tasks WHERE workspace_id = ? AND status = 'open'",
                (workspace_id,),
            ).fetchone()
            pending_approvals = connection.execute(
                "SELECT COUNT(*) AS count FROM approval_requests WHERE workspace_id = ? AND status = 'pending'",
                (workspace_id,),
            ).fetchone()
        total = len(inspections)
        rotten = sum(row["predicted_freshness"] == "rotten" for row in inspections)
        uncertain = sum(
            row["decision"] in {"unsupported_input", "uncertain_input", "retake_photo"}
            for row in inspections
        )
        reviewed = sum(row["review_status"] != "pending" for row in inspections)
        corrections = sum(row["review_status"] == "corrected" for row in inspections)
        fruit_counts: dict[str, int] = {}
        for row in inspections:
            key = row["fruit"] or "unclassified"
            fruit_counts[key] = fruit_counts.get(key, 0) + 1
        narrative = (
            f"{total} inspections were recorded on {report_date}; {rotten} were flagged "
            f"with visible rotten patterns, {uncertain} required retake or review, and "
            f"{reviewed} received human review."
        )
        return {
            "report_date": report_date,
            "total_inspections": total,
            "rotten_flags": rotten,
            "uncertain_or_retake": uncertain,
            "reviewed": reviewed,
            "corrections": corrections,
            "open_tasks": int(open_tasks["count"] if open_tasks else 0),
            "pending_approvals": int(
                pending_approvals["count"] if pending_approvals else 0
            ),
            "fruit_counts": fruit_counts,
            "summary": narrative,
            "generated_at_utc": _utc_now(),
        }

    def _finish_agent_run(
        self,
        *,
        identity_hash: str,
        run_id: str,
        status: str,
        final_summary: str,
        error_code: str | None,
    ) -> dict[str, Any]:
        if status not in AGENT_RUN_STATUSES - {"running"}:
            raise SaaSStoreError("Agent terminal status is invalid.")
        workspace_id = self._workspace_id(identity_hash)
        self._require_workspace_agent_run(
            workspace_id=workspace_id,
            run_id=run_id,
            required_status="running",
        )
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE agent_runs
                SET status = ?, final_summary = ?, error_code = ?,
                    completed_at_utc = ?
                WHERE workspace_id = ? AND run_id = ? AND status = 'running'
                """,
                (
                    status,
                    final_summary,
                    error_code,
                    _utc_now(),
                    workspace_id,
                    run_id,
                ),
            )
        return self.agent_run(identity_hash, run_id)

    def _require_workspace_inspection(
        self,
        *,
        workspace_id: str,
        inspection_id: str,
    ) -> None:
        inspection_id = _bounded_required(
            inspection_id,
            "inspection_id",
            64,
        )
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM inspections
                WHERE workspace_id = ? AND inspection_id = ?
                """,
                (workspace_id, inspection_id),
            ).fetchone()
        if row is None:
            raise InspectionNotFoundError("Inspection not found in this workspace.")

    def _require_workspace_agent_run(
        self,
        *,
        workspace_id: str,
        run_id: str,
        required_status: str | None = None,
    ) -> None:
        run_id = _bounded_required(run_id, "run_id", 64)
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT status FROM agent_runs
                WHERE workspace_id = ? AND run_id = ?
                """,
                (workspace_id, run_id),
            ).fetchone()
        if row is None:
            raise AgentRunNotFoundError("Agent run not found in this workspace.")
        if required_status is not None and row["status"] != required_status:
            raise SaaSStoreError(
                f"Agent run must be {required_status} for this operation."
            )

    def _workspace_role(self, workspace_id: str, identity_hash: str) -> str:
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

    @staticmethod
    def _insert_notification(
        connection: DatabaseConnection,
        *,
        workspace_id: str,
        recipient_role: str,
        kind: str,
        title: str,
        message: str,
        related_type: str,
        related_id: str,
        created_at_utc: str,
    ) -> dict[str, Any]:
        if recipient_role not in WORKSPACE_ROLES | {"all"}:
            raise SaaSStoreError("Notification recipient role is invalid.")
        notification_id = str(uuid4())
        title = _bounded_required(title, "title", 200)
        message = _bounded_required(message, "message", 2000)
        connection.execute(
            """
            INSERT INTO notifications(
                notification_id, workspace_id, recipient_role, kind, title,
                message, related_type, related_id, created_at_utc, read_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                notification_id,
                workspace_id,
                recipient_role,
                _bounded_required(kind, "kind", 80),
                title,
                message,
                _bounded_required(related_type, "related_type", 80),
                _bounded_required(related_id, "related_id", 80),
                created_at_utc,
            ),
        )
        return {
            "notification_id": notification_id,
            "recipient_role": recipient_role,
            "kind": kind,
            "title": title,
            "message": message,
            "related_type": related_type,
            "related_id": related_id,
            "created_at_utc": created_at_utc,
            "read_at_utc": None,
        }

    @staticmethod
    def _public_row(row: Mapping[str, Any], *hidden: str) -> dict[str, Any]:
        value = dict(row)
        for key in hidden:
            value.pop(key, None)
        return value

    @classmethod
    def _approval_record(cls, row: Mapping[str, Any]) -> dict[str, Any]:
        value = cls._public_row(row, "workspace_id", "resolved_by_identity_hash")
        value["payload"] = json.loads(value.pop("payload_json"))
        return value

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


def _agent_step_record(row: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(row)
    value["input"] = json.loads(value.pop("input_json"))
    value["output"] = json.loads(value.pop("output_json"))
    return value


def _action_proposal_record(row: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(row)
    value["payload"] = json.loads(value.pop("payload_json"))
    return value


def _manager_message_record(row: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(row)
    value["citations"] = json.loads(value.pop("citations_json"))
    value["metadata"] = json.loads(value.pop("metadata_json"))
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


def _bounded_json(value: Mapping[str, Any], name: str, maximum: int) -> str:
    try:
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise SaaSStoreError(f"{name} must be JSON serializable.") from exc
    if len(serialized.encode("utf-8")) > maximum:
        raise SaaSStoreError(f"{name} exceeds {maximum} bytes.")
    return serialized


def _bounded_json_value(value: Any, name: str, maximum: int) -> str:
    try:
        serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise SaaSStoreError(f"{name} must be JSON serializable.") from exc
    if len(serialized.encode("utf-8")) > maximum:
        raise SaaSStoreError(f"{name} exceeds {maximum} bytes.")
    return serialized


def _chat_title(content: str) -> str:
    compact = " ".join(content.split())
    return compact if len(compact) <= 72 else compact[:69].rstrip() + "..."


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
