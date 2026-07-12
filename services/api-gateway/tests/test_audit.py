from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import audit
import auth
import main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "gateway.db"
    monkeypatch.setattr(main, "auth_repository", auth.AuthRepository(db_path))
    monkeypatch.setattr(main, "audit_repository", audit.AuditRepository(db_path))
    with TestClient(main.app) as test_client:
        yield test_client


def _login_as(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_login_writes_success_audit_event(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")

    events = client.get("/api/audit-log").json()

    actions = [e["action"] for e in events]
    assert "login" in actions
    login_event = next(e for e in events if e["action"] == "login")
    assert login_event["result"] == "success"
    assert login_event["actor_role"] == "admin"


def test_failed_login_writes_failure_audit_event(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})
    _login_as(client, "admin", "correct-horse-1")

    events = client.get("/api/audit-log").json()

    failed_logins = [e for e in events if e["action"] == "login" and e["result"] == "failure"]
    assert len(failed_logins) == 1
    assert failed_logins[0]["actor_user_id"] is None


def test_denied_request_writes_access_denied_audit_event(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")
    client.post("/api/users", json={"username": "auditor1", "password": "auditor-password1", "role": "auditor"})
    client.post("/api/auth/logout")
    _login_as(client, "auditor1", "auditor-password1")

    denied = client.post("/api/scans/host", json={"assets": [{"asset_type": "server", "name": "h1"}]})
    assert denied.status_code == 403

    _login_as(client, "admin", "correct-horse-1")
    events = client.get("/api/audit-log").json()
    denials = [e for e in events if e["action"] == "access_denied"]
    assert len(denials) == 1
    assert denials[0]["actor_role"] == "auditor"
    assert denials[0]["result"] == "failure"


def test_unauthenticated_denial_writes_audit_event_with_no_actor(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})

    denied = client.get("/api/assets")
    assert denied.status_code == 401

    _login_as(client, "admin", "correct-horse-1")
    events = client.get("/api/audit-log").json()
    denials = [e for e in events if e["action"] == "access_denied" and e["actor_user_id"] is None]
    assert len(denials) == 1


def test_audit_log_is_admin_and_auditor_only(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")
    client.post("/api/users", json={"username": "sa1", "password": "sa-password1", "role": "security_architect"})
    client.post("/api/users", json={"username": "auditor1", "password": "auditor-password1", "role": "auditor"})
    client.post("/api/auth/logout")

    _login_as(client, "sa1", "sa-password1")
    assert client.get("/api/audit-log").status_code == 403
    client.post("/api/auth/logout")

    _login_as(client, "auditor1", "auditor-password1")
    assert client.get("/api/audit-log").status_code == 200


def test_audit_log_has_no_mutation_route(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")

    assert client.post("/api/audit-log").status_code == 405
    assert client.delete("/api/audit-log").status_code == 405


def test_create_user_writes_audit_event_with_actor(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")

    client.post("/api/users", json={"username": "op1", "password": "operator-pass1", "role": "operator"})

    events = client.get("/api/audit-log").json()
    creations = [e for e in events if e["action"] == "user.create" and e["resource_id"]]
    admin_created = [e for e in creations if "op1" in (e.get("summary") or "")]
    assert len(admin_created) == 1
    assert admin_created[0]["actor_role"] == "admin"
