import pytest

from saas.store import InspectionNotFoundError, SaaSStore, SaaSStoreError


def _analysis(*, freshness: str = "fresh") -> dict[str, object]:
    return {
        "decision": "accept_prediction",
        "status": "completed",
        "prediction": {
            "class_name": f"{freshness}banana",
            "display_name": f"{freshness.title()} Banana",
            "fruit": "banana",
            "freshness": freshness,
            "confidence": 0.91,
        },
        "reasoning": {"risk_level": "low"},
        "warnings": [{"level": "warning", "message": "Visual assessment only."}],
        "recommendation": "Ask a staff member to inspect the fruit.",
        "safety_notice": "Not a food-safety test.",
    }


def test_store_creates_isolated_workspaces_and_never_records_an_image(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")

    first = store.workspace("identity-a")
    second = store.workspace("identity-b")
    inspection = store.record_inspection(
        identity_hash="identity-a",
        location_name="Produce receiving",
        batch_reference="PO-42",
        operator_note="Morning delivery",
        analysis=_analysis(),
        model_version="0.6.0",
    )

    assert first["workspace_id"] != second["workspace_id"]
    assert inspection["location_name"] == "Produce receiving"
    assert inspection["image_retained"] is False
    assert "filename" not in inspection
    assert store.list_inspections("identity-b") == []


def test_store_initialization_is_cached_after_success(tmp_path, monkeypatch):
    store = SaaSStore(tmp_path / "saas.db")
    store.initialize()

    def unexpected_connect():
        pytest.fail("A completed schema initialization must not run again.")

    monkeypatch.setattr(store, "_connect", unexpected_connect)

    store.initialize()


def test_store_supports_review_audit_and_dashboard_metrics(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    inspection = store.record_inspection(
        identity_hash="identity-a",
        location_name="Main store",
        batch_reference="",
        operator_note="",
        analysis=_analysis(),
        model_version="0.6.0",
    )

    reviewed = store.review_inspection(
        identity_hash="identity-a",
        inspection_id=inspection["inspection_id"],
        review_status="corrected",
        reviewed_outcome="rotten",
        note="Dark soft area confirmed by staff.",
    )
    dashboard = store.dashboard("identity-a")

    assert reviewed["review_status"] == "corrected"
    assert reviewed["reviewed_outcome"] == "rotten"
    assert dashboard["total_inspections"] == 1
    assert dashboard["pending_reviews"] == 0
    assert dashboard["review_completion_rate"] == 1.0
    assert dashboard["false_fresh_reviews"] == 1


def test_store_rejects_cross_workspace_review_and_invalid_review(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    inspection = store.record_inspection(
        identity_hash="identity-a",
        location_name="Main store",
        batch_reference="",
        operator_note="",
        analysis=_analysis(),
        model_version="0.6.0",
    )

    with pytest.raises(InspectionNotFoundError):
        store.review_inspection(
            identity_hash="identity-b",
            inspection_id=inspection["inspection_id"],
            review_status="confirmed",
            reviewed_outcome="fresh",
            note="",
        )
    with pytest.raises(SaaSStoreError, match="needs an outcome"):
        store.review_inspection(
            identity_hash="identity-a",
            inspection_id=inspection["inspection_id"],
            review_status="confirmed",
            reviewed_outcome=None,
            note="",
        )


def test_workspace_invitation_is_email_bound_one_time_and_role_scoped(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    manager = store.workspace(
        "manager-identity",
        email="manager@example.test",
        display_name="Produce Manager",
    )
    invitation = store.create_invitation(
        identity_hash="manager-identity",
        email="reviewer@example.test",
        role="reviewer",
    )

    joined = store.accept_invitation(
        identity_hash="reviewer-identity",
        email="Reviewer@Example.Test",
        display_name="Quality Reviewer",
        invitation_token=invitation["invitation_token"],
    )

    assert joined["workspace_id"] == manager["workspace_id"]
    assert joined["current_role"] == "reviewer"
    assert {member["role"] for member in joined["members"]} == {
        "manager",
        "reviewer",
    }
    with pytest.raises(SaaSStoreError, match="already accepted"):
        store.accept_invitation(
            identity_hash="another-reviewer",
            email="reviewer@example.test",
            display_name=None,
            invitation_token=invitation["invitation_token"],
        )


def test_workspace_invitation_rejects_wrong_email_and_non_manager(tmp_path):
    store = SaaSStore(tmp_path / "saas.db")
    store.workspace("manager-identity")
    invitation = store.create_invitation(
        identity_hash="manager-identity",
        email="inspector@example.test",
        role="inspector",
    )

    with pytest.raises(SaaSStoreError, match="does not match"):
        store.accept_invitation(
            identity_hash="inspector-identity",
            email="other@example.test",
            display_name=None,
            invitation_token=invitation["invitation_token"],
        )

    store.accept_invitation(
        identity_hash="inspector-identity",
        email="inspector@example.test",
        display_name=None,
        invitation_token=invitation["invitation_token"],
    )
    with pytest.raises(SaaSStoreError, match="Only a workspace manager"):
        store.create_invitation(
            identity_hash="inspector-identity",
            email="new@example.test",
            role="reviewer",
        )
