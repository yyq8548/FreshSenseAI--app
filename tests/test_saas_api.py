from hashlib import sha256

from fastapi.testclient import TestClient

from api.app import create_app
from tests.test_api import _FakeAgent, _image_bytes, _upload


API_KEY = "saas-test-key-with-at-least-32-characters"


def _app(tmp_path):
    return create_app(
        agent_factory=lambda: _FakeAgent(),
        api_key=API_KEY,
        api_key_file=None,
        saas_database_path=tmp_path / "saas.db",
    )


def test_inspection_vertical_slice_analyzes_records_reviews_and_summarizes(tmp_path):
    app = _app(tmp_path)
    headers = {"X-API-Key": API_KEY}
    with TestClient(app) as client:
        workspace = client.get("/api/v1/workspace", headers=headers)
        created = client.post(
            "/api/v1/inspections/analyze",
            headers=headers,
            data={
                "location_name": "Produce receiving",
                "batch_reference": "PO-42",
                "operator_note": "Morning delivery",
            },
            files=_upload(_image_bytes()),
        )
        inspection_id = created.json()["inspection"]["inspection_id"]
        listed = client.get("/api/v1/inspections", headers=headers)
        reviewed = client.patch(
            f"/api/v1/inspections/{inspection_id}/review",
            headers=headers,
            json={
                "review_status": "confirmed",
                "reviewed_outcome": "fresh",
                "note": "Visual and touch check agreed.",
            },
        )
        dashboard = client.get("/api/v1/dashboard", headers=headers)

    assert workspace.status_code == 200
    assert workspace.json()["plan"] == "pilot"
    assert created.status_code == 200
    body = created.json()
    assert body["analysis"]["prediction"]["fruit"] == "banana"
    assert body["inspection"]["location_name"] == "Produce receiving"
    assert body["inspection"]["image_retained"] is False
    assert "banana.png" not in created.text
    assert listed.json()["count"] == 1
    assert reviewed.json()["review_status"] == "confirmed"
    assert dashboard.json()["reviewed_inspections"] == 1


def test_saas_routes_require_authentication_before_upload_parsing(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        workspace = client.get("/api/v1/workspace")
        analyze = client.post(
            "/api/v1/inspections/analyze",
            files=_upload(_image_bytes()),
        )

    assert workspace.status_code == 401
    assert analyze.status_code == 401
    assert analyze.json()["error"]["code"] == "INVALID_API_KEY"


def test_inspection_cannot_be_reviewed_from_another_api_identity(tmp_path):
    first_key = API_KEY
    second_key = "different-saas-key-with-at-least-32-characters"
    first_app = create_app(
        agent_factory=lambda: _FakeAgent(),
        api_key=first_key,
        api_key_file=None,
        saas_database_path=tmp_path / "saas.db",
    )
    with TestClient(first_app) as client:
        created = client.post(
            "/api/v1/inspections/analyze",
            headers={"X-API-Key": first_key},
            files=_upload(_image_bytes()),
        )
    inspection_id = created.json()["inspection"]["inspection_id"]

    second_app = create_app(
        agent_factory=lambda: _FakeAgent(),
        api_key=second_key,
        api_key_file=None,
        saas_database_path=tmp_path / "saas.db",
    )
    with TestClient(second_app) as client:
        response = client.patch(
            f"/api/v1/inspections/{inspection_id}/review",
            headers={"X-API-Key": second_key},
            json={
                "review_status": "confirmed",
                "reviewed_outcome": "fresh",
                "note": "",
            },
        )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "INSPECTION_NOT_FOUND"


def test_openapi_documents_workspace_inspection_and_review_contracts(tmp_path):
    app = _app(tmp_path)
    with TestClient(app) as client:
        schema = client.get("/openapi.json").json()

    assert "/api/v1/workspace" in schema["paths"]
    assert "/api/v1/dashboard" in schema["paths"]
    assert "/api/v1/inspections" in schema["paths"]
    assert "/api/v1/inspections/analyze" in schema["paths"]
    assert "/api/v1/inspections/{inspection_id}/review" in schema["paths"]
    assert "/api/v1/agent/runs" in schema["paths"]
    assert "/api/v1/agent/runs/{run_id}" in schema["paths"]
    assert "/api/v1/workflow/tasks" in schema["paths"]
    assert "/api/v1/notifications" in schema["paths"]
    assert "/api/v1/approvals" in schema["paths"]
    assert "/api/v1/reports/daily" in schema["paths"]
    create_operation = schema["paths"]["/api/v1/inspections/analyze"]["post"]
    assert "multipart/form-data" in create_operation["requestBody"]["content"]


def test_shadow_agent_api_records_an_audited_proposal(tmp_path):
    app = _app(tmp_path)
    headers = {"X-API-Key": API_KEY}
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/inspections/analyze",
            headers=headers,
            files=_upload(_image_bytes()),
        )
        inspection_id = created.json()["inspection"]["inspection_id"]
        started = client.post(
            "/api/v1/agent/runs",
            headers=headers,
            json={"inspection_id": inspection_id},
        )
        run_id = started.json()["run_id"]
        fetched = client.get(f"/api/v1/agent/runs/{run_id}", headers=headers)
        listed = client.get("/api/v1/agent/runs", headers=headers)

    assert started.status_code == 200
    assert started.json()["status"] == "completed"
    assert started.json()["mode"] == "shadow"
    assert started.json()["steps_completed"] == 5
    assert started.json()["action_proposals"][0]["execution_status"] == "shadow_only"
    assert fetched.status_code == 200
    assert listed.json()["count"] == 2


def test_supervised_workflow_api_exposes_notifications_memory_report_and_approval(tmp_path):
    app = _app(tmp_path)
    headers = {"X-API-Key": API_KEY}
    identity = sha256(f"api-key:{API_KEY}".encode("utf-8")).hexdigest()
    with TestClient(app) as client:
        created = client.post(
            "/api/v1/inspections/analyze",
            headers=headers,
            files=_upload(_image_bytes()),
        )
        inspection_id = created.json()["inspection"]["inspection_id"]
        notifications = client.get("/api/v1/notifications", headers=headers)
        report = client.get("/api/v1/reports/daily", headers=headers)
        client.patch(
            f"/api/v1/inspections/{inspection_id}/review",
            headers=headers,
            json={
                "review_status": "confirmed",
                "reviewed_outcome": "fresh",
                "note": "Staff confirmed the visible condition.",
            },
        )
        memory = client.get("/api/v1/agent/memory", headers=headers)

        rotten = app.state.saas_store.record_inspection(
            identity_hash=identity,
            location_name="Produce receiving",
            batch_reference="PO-ROTTEN",
            operator_note="Approval API test",
            analysis={
                "decision": "accept_prediction",
                "status": "completed",
                "prediction": {
                    "class_name": "rottenbanana",
                    "display_name": "Rotten Banana",
                    "fruit": "banana",
                    "freshness": "rotten",
                    "confidence": 0.94,
                },
                "reasoning": {"risk_level": "high"},
                "warnings": [],
                "recommendation": "Inspect the physical batch.",
                "safety_notice": "Decision support only.",
            },
            model_version="test",
        )
        app.state.autonomous_agent.run(
            identity_hash=identity,
            inspection_id=rotten["inspection_id"],
            mode="supervised",
        )
        approvals = client.get("/api/v1/approvals?status=pending", headers=headers)
        approval_id = approvals.json()["approvals"][0]["approval_id"]
        resolved = client.patch(
            f"/api/v1/approvals/{approval_id}",
            headers=headers,
            json={"decision": "approved", "note": "Physical check completed."},
        )
        tasks = client.get("/api/v1/workflow/tasks?status=open", headers=headers)

    assert created.json()["workflow_status"] == "completed"
    assert created.json()["agent_run_id"]
    assert notifications.json()["unread_count"] >= 1
    assert report.json()["total_inspections"] == 1
    assert memory.json()["count"] == 1
    assert approvals.json()["count"] == 1
    assert resolved.json()["status"] == "approved"
    assert tasks.json()["tasks"][0]["task_type"] == "approved_hold_batch"
