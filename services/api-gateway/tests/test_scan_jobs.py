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


def _process_next_job() -> scan_jobs.ScanJob | None:
    """Simulates one worker.py poll cycle (claim + run) without running the
    actual worker process -- see worker.py's run_forever()."""
    job = main.scan_job_repository.claim_next_queued_job()
    if job is None:
        return None
    main.run_scan_job(job.id, job.scan_type, job.workspace_id, job.created_by, None)
    return main.scan_job_repository.get_job(job.id)


HOST_PAYLOAD = {"assets": [{"asset_type": "server", "name": "job-host-1"}]}


def test_create_job_returns_queued_and_does_not_run_itself(client: TestClient, monkeypatch) -> None:
    called = []
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: called.append(1) or {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    _bootstrap_and_login_admin(client)

    response = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD})

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    # POST /api/scan-jobs must not itself execute the scan -- only a worker does.
    assert called == []
    still_queued = main.scan_job_repository.get_job(response.json()["id"])
    assert still_queued.status == "queued"


def test_worker_processes_queued_job_to_success(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    _bootstrap_and_login_admin(client)
    client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD})

    job = _process_next_job()

    assert job.status == "succeeded"
    assert "created=1" in job.logs
    assert job.result_summary is not None


def test_create_job_requires_admin_or_security_architect(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    client.post("/api/users", json={"username": "op1", "password": "operator-pass1", "role": "operator"})
    client.post("/api/auth/logout")
    _login_as(client, "op1", "operator-pass1")

    response = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD})

    assert response.status_code == 403


def test_failed_ingest_retries_then_permanently_fails(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "MAX_SCAN_JOB_RETRIES", 2)

    def boom(*a, **k):
        from fastapi import HTTPException
        raise HTTPException(status_code=502, detail="downstream unavailable")

    monkeypatch.setattr(main, "_request_json", boom)
    _bootstrap_and_login_admin(client)
    client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD})

    # Attempt 1: fails, retries (requeued).
    job = _process_next_job()
    assert job.status == "queued"
    assert job.retry_count == 1
    assert "retrying" in job.logs

    # Attempt 2: fails, retries again.
    job = _process_next_job()
    assert job.status == "queued"
    assert job.retry_count == 2

    # Attempt 3: exceeds max_retries=2 -- permanently failed.
    job = _process_next_job()
    assert job.status == "failed"
    assert job.retry_count == 3
    assert "downstream unavailable" in job.result_summary
    assert "giving up" in job.logs


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


def test_cancel_queued_job_before_worker_runs(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    job_id = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD}).json()["id"]

    response = client.post(f"/api/scan-jobs/{job_id}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    # The worker's claim skips it -- a cancelled job is never picked up.
    assert main.scan_job_repository.claim_next_queued_job() is None


def test_cancel_already_succeeded_job_returns_409(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    _bootstrap_and_login_admin(client)
    job_id = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD}).json()["id"]
    _process_next_job()

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


def test_scan_scope_rejection_eventually_marks_job_failed(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "MAX_SCAN_JOB_RETRIES", 0)
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

    job = _process_next_job()

    assert job.status == "failed"
    assert "rejected by scan scope" in job.result_summary


# --- claim_next_queued_job / worker-queue mechanics (Product v1 roadmap Phase 4 item 11) ---


def test_claim_next_queued_job_returns_none_when_empty(client: TestClient) -> None:
    assert main.scan_job_repository.claim_next_queued_job() is None


def test_claim_next_queued_job_is_fifo_and_marks_running(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    _bootstrap_and_login_admin(client)
    first = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD}).json()["id"]
    second = client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD}).json()["id"]

    claimed = main.scan_job_repository.claim_next_queued_job()

    assert claimed.id == first
    assert claimed.status == "running"
    # The second job is untouched -- still queued, not yet claimed.
    assert main.scan_job_repository.get_job(second).status == "queued"


def test_claim_next_queued_job_does_not_double_claim(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    _bootstrap_and_login_admin(client)
    client.post("/api/scan-jobs", json={"scan_type": "host", "payload": HOST_PAYLOAD})

    first_claim = main.scan_job_repository.claim_next_queued_job()
    second_claim = main.scan_job_repository.claim_next_queued_job()

    assert first_claim is not None
    assert second_claim is None  # already running -- a second worker gets nothing
