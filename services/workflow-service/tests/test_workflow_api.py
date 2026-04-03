from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "workflow-service"}


def test_task_lifecycle() -> None:
    create_response = client.post(
        "/tasks",
        json={
            "title": "Review google endpoint",
            "asset_name": "google.com:443",
            "wave": "wave_1",
            "priority": "high",
            "description": "Review TLS configuration and migration path.",
            "recommended_action": "Review TLS configuration, certificate algorithms, and PQC migration path.",
        },
    )
    assert create_response.status_code == 201
    task = create_response.json()
    task_id = task["id"]

    submit_response = client.post(f"/tasks/{task_id}/submit")
    assert submit_response.status_code == 200
    assert submit_response.json()["status"] == "pending_approval"

    approve_response = client.post(
        f"/tasks/{task_id}/approve",
        json={"approver": "security-lead", "decision": "approved", "note": "Proceed"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["decision"] == "approved"

    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 200
    assert get_response.json()["status"] == "approved"

    approvals_response = client.get("/approvals")
    assert approvals_response.status_code == 200
    assert len(approvals_response.json()) >= 1


def test_cleanup_duplicates() -> None:
    payload = {
        "title": "Review google endpoint",
        "asset_name": "google.com:443",
        "wave": "wave_1",
        "priority": "high",
        "description": "Review TLS configuration and migration path.",
        "recommended_action": "Review TLS configuration, certificate algorithms, and PQC migration path.",
    }

    first = client.post("/tasks", json=payload)
    assert first.status_code == 201

    cleanup = client.post("/admin/cleanup-duplicates")
    assert cleanup.status_code == 200
    assert "deleted_tasks" in cleanup.json()
