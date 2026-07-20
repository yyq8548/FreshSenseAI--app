from fastapi.testclient import TestClient
from starlette.requests import Request as StarletteRequest

from api.app import create_app
from api.identity import TokenValidationError
from tests.test_api import _FakeAgent, _image_bytes, _upload


TENANT_ID = "11111111-2222-3333-4444-555555555555"
API_CLIENT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
AUTHORITY = f"https://freshsense.ciamlogin.com/{TENANT_ID}"


class _FakeValidator:
    initialized = False

    def initialize(self):
        self.initialized = True

    def validate(self, token):
        accounts = {
            "valid-access-token": (
                "external-user-subject",
                "Produce Manager",
                "manager@example.test",
            ),
            "inspector-token": (
                "inspector-subject",
                "Store Inspector",
                "inspector@example.test",
            ),
            "reviewer-token": (
                "reviewer-subject",
                "Quality Reviewer",
                "reviewer@example.test",
            ),
        }
        account = accounts.get(token)
        if account is None:
            raise TokenValidationError("invalid")
        subject, name, email = account
        return {
            "sub": subject,
            "tid": TENANT_ID,
            "name": name,
            "emails": [email],
            "scp": "access_as_user",
        }


def _app(tmp_path, validator=None):
    return create_app(
        agent_factory=lambda: _FakeAgent(),
        auth_mode="entra",
        entra_tenant_id=TENANT_ID,
        entra_api_client_id=API_CLIENT_ID,
        entra_authority=AUTHORITY,
        entra_token_validator=validator or _FakeValidator(),
        saas_database_path=tmp_path / "saas.db",
    )


def test_entra_mode_accepts_bearer_and_rejects_missing_invalid_or_api_key(tmp_path):
    validator = _FakeValidator()
    app = _app(tmp_path, validator)
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        missing = client.get("/api/v1/workspace")
        invalid = client.get(
            "/api/v1/workspace",
            headers={"Authorization": "Bearer invalid"},
        )
        api_key = client.get(
            "/api/v1/workspace",
            headers={"X-API-Key": "x" * 40},
        )
        accepted = client.get(
            "/api/v1/workspace",
            headers={"Authorization": "Bearer valid-access-token"},
        )

    assert validator.initialized is True
    assert health.status_code == 200
    assert health.json()["authentication_required"] is True
    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert api_key.status_code == 401
    assert accepted.status_code == 200
    assert accepted.json()["display_name"] == "FreshSense Pilot Workspace"


def test_entra_rejects_upload_before_multipart_parsing(tmp_path, monkeypatch):
    async def fail_if_parsed(_request):
        raise AssertionError("multipart parsing should not run before authentication")

    monkeypatch.setattr(StarletteRequest, "_get_form", fail_if_parsed)
    app = _app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/inspections/analyze",
            files=_upload(_image_bytes()),
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_ACCESS_TOKEN"


def test_openapi_declares_entra_bearer_scheme(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["FreshSenseEntraBearer"] == {
        "type": "http",
        "description": "Microsoft Entra access token issued for the FreshSense API.",
        "scheme": "bearer",
    }


def test_entra_workspace_invitations_enforce_manager_inspector_reviewer_roles(
    tmp_path,
):
    app = _app(tmp_path)
    manager = {"Authorization": "Bearer valid-access-token"}
    inspector = {"Authorization": "Bearer inspector-token"}
    reviewer = {"Authorization": "Bearer reviewer-token"}
    with TestClient(app) as client:
        manager_me = client.get("/api/v1/me", headers=manager)
        inspector_invite = client.post(
            "/api/v1/workspace/invitations",
            headers=manager,
            json={"email": "inspector@example.test", "role": "inspector"},
        )
        inspector_join = client.post(
            "/api/v1/workspace/invitations/accept",
            headers=inspector,
            json={"invitation_token": inspector_invite.json()["invitation_token"]},
        )
        inspector_analysis = client.post(
            "/api/v1/inspections/analyze",
            headers=inspector,
            files=_upload(_image_bytes()),
        )
        inspection_id = inspector_analysis.json()["inspection"]["inspection_id"]
        inspector_review = client.patch(
            f"/api/v1/inspections/{inspection_id}/review",
            headers=inspector,
            json={
                "review_status": "confirmed",
                "reviewed_outcome": "fresh",
            },
        )
        reviewer_invite = client.post(
            "/api/v1/workspace/invitations",
            headers=manager,
            json={"email": "reviewer@example.test", "role": "reviewer"},
        )
        reviewer_join = client.post(
            "/api/v1/workspace/invitations/accept",
            headers=reviewer,
            json={"invitation_token": reviewer_invite.json()["invitation_token"]},
        )
        reviewer_analysis = client.post(
            "/api/v1/inspections/analyze",
            headers=reviewer,
            files=_upload(_image_bytes()),
        )
        reviewer_direct_analysis = client.post(
            "/api/v1/analyze",
            headers=reviewer,
            files=_upload(_image_bytes()),
        )
        reviewer_review = client.patch(
            f"/api/v1/inspections/{inspection_id}/review",
            headers=reviewer,
            json={
                "review_status": "confirmed",
                "reviewed_outcome": "fresh",
                "note": "Manual check agreed.",
            },
        )

    assert manager_me.status_code == 200
    assert manager_me.json()["workspace_role"] == "manager"
    assert inspector_invite.status_code == 201
    assert inspector_join.json()["current_role"] == "inspector"
    assert inspector_analysis.status_code == 200
    assert inspector_review.status_code == 403
    assert inspector_review.json()["error"]["code"] == "INSUFFICIENT_WORKSPACE_ROLE"
    assert reviewer_join.json()["current_role"] == "reviewer"
    assert reviewer_analysis.status_code == 403
    assert reviewer_direct_analysis.status_code == 403
    assert reviewer_review.status_code == 200
