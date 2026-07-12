from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import audit
import auth
import scan_jobs
import scan_scope
import main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "gateway.db"
    monkeypatch.setattr(main, "auth_repository", auth.AuthRepository(db_path))
    monkeypatch.setattr(main, "audit_repository", audit.AuditRepository(db_path))
    monkeypatch.setattr(main, "scan_scope_repository", scan_scope.ScanScopeRepository(db_path))
    monkeypatch.setattr(main, "scan_job_repository", scan_jobs.ScanJobRepository(db_path))
    with TestClient(main.app) as test_client:
        yield test_client


def _login_as(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def _bootstrap_and_login_admin(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")


HOST_PAYLOAD = {"assets": [{"asset_type": "server", "name": "job-host-1"}]}


def test_create_job_returns_queued_then_succeeds(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    _bootstrap_and_login_admin(client)

    response = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD})

    assert response.status_code == 202
    assert response.json()["status"] == "queued"  # response body reflects pre-background-task state

    # TestClient runs the background task before client.post() returns control, but the
    # response body was serialized before that -- re-fetch to see the post-task state.
    job = client.get(f"/api/scan-jobs/{response.json()['id']}").json()
    assert job["status"] == "succeeded"
    assert "created=1" in job["logs"]
    assert job["result_summary"] is not None


def test_create_job_requires_admin_or_security_architect(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    client.post("/api/users", json={"username": "op1", "password": "operator-pass1", "role": "operator"})
    client.post("/api/auth/logout")
    _login_as(client, "op1", "operator-pass1")

    response = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD})

    assert response.status_code == 403


def test_failed_ingest_marks_job_failed_with_error_summary(client: TestClient, monkeypatch) -> None:
    def boom(*a, **k):
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail="downstream unavailable")

    monkeypatch.setattr(main, "_request_json", boom)
    _bootstrap_and_login_admin(client)

    response = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD})

    job = client.get(f"/api/scan-jobs/{response.json()['id']}").json()
    assert job["status"] == "failed"
    assert "downstream unavailable" in job["result_summary"]
    assert "failed" in job["logs"]


def test_get_job_returns_404_for_unknown_id(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)

    assert client.get("/api/scan-jobs/does-not-exist").status_code == 404


def test_list_jobs_filters_by_workspace(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "ws-a"})
    _bootstrap_and_login_admin(client)
    client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD, "workspace_id": "ws-a"})
    client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD, "workspace_id": "ws-b"})

    scoped = client.get("/api/scan-jobs", params={"workspace_id": "ws-a"}).json()

    assert len(scoped) == 1
    assert scoped[0]["workspace_id"] == "ws-a"


def test_cancel_queued_job_before_worker_runs(client: TestClient, monkeypatch) -> None:
    # Bypass the route's background task entirely and drive the repository directly,
    # to exercise "cancel while still queued" (TestClient otherwise runs the worker to
    # completion synchronously before the create call even returns).
    repo = scan_jobs.ScanJobRepository(main.scan_job_repository.db_path)
    _bootstrap_and_login_admin(client)
    job = repo.create_job(
        scan_jobs.ScanJobCreate(scan_type="host", payload=HOST_PAYLOAD), created_by=None
    )

    response = client.post(f"/api/scan-jobs/{job.id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    # The worker checks status before running -- a cancelled job never transitions to running.
    assert repo.mark_running(job.id) is False


def test_cancel_already_succeeded_job_returns_409(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    _bootstrap_and_login_admin(client)
    job_id = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD}).json()["id"]

    response = client.post(f"/api/scan-jobs/{job_id}/cancel")

    assert response.status_code == 409


def test_cancel_unknown_job_returns_404(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)

    assert client.post("/api/scan-jobs/does-not-exist/cancel").status_code == 404


def test_job_creation_writes_audit_event(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    _bootstrap_and_login_admin(client)

    client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD})

    events = client.get("/api/audit-log").json()
    creations = [e for e in events if e["action"] == "scan_job.create"]
    assert len(creations) == 1


def test_scan_scope_rejection_marks_job_failed(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    client.post("/api/scan-scopes", json={"workspace_id": "ws-scoped", "allowed_cidr_ranges": ["192.168.0.0/24"]})
    network_payload = {
        "assets": [{"asset_type": "endpoint", "name": "10.0.0.5:443"}],
        "tls_evidence": {"collected": True, "target": "10.0.0.5:443", "port": 443},
    }

    response = client.post(
        "/api/scan-jobs",
        json={"scan_type": "network", "payload": network_payload, "workspace_id": "ws-scoped"},
    )

    assert response.json()["targets"] == ["10.0.0.5:443"]
    job = client.get(f"/api/scan-jobs/{response.json()['id']}").json()
    assert job["status"] == "failed"
    assert "rejected by scan scope" in job["result_summary"]
