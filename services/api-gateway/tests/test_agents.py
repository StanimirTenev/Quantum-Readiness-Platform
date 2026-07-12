from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import agents
import audit
import auth
import main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "gateway.db"
    monkeypatch.setattr(main, "auth_repository", auth.AuthRepository(db_path))
    monkeypatch.setattr(main, "audit_repository", audit.AuditRepository(db_path))
    monkeypatch.setattr(main, "agent_repository", agents.AgentRepository(db_path))
    with TestClient(main.app) as test_client:
        yield test_client


def _login_as(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def _bootstrap_and_login_admin(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")


def _create_token(client: TestClient, workspace_id: str = "ws-1") -> dict:
    response = client.post("/api/agent-enrollment-tokens", json={"workspace_id": workspace_id, "label": "fleet-1"})
    assert response.status_code == 201
    return response.json()


# --- Enrollment token lifecycle ---


def test_create_enrollment_token_requires_admin_or_security_architect(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    client.post("/api/users", json={"username": "op1", "password": "operator-pass1", "role": "operator"})
    client.post("/api/auth/logout")
    _login_as(client, "op1", "operator-pass1")

    response = client.post("/api/agent-enrollment-tokens", json={"workspace_id": "ws-1"})

    assert response.status_code == 403


def test_create_token_returns_raw_token_once(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)

    token = _create_token(client)

    assert len(token["token"]) > 20
    listed = client.get("/api/agent-enrollment-tokens").json()
    assert "token" not in listed[0]  # raw token never appears again


def test_create_token_writes_audit_event(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)

    _create_token(client)

    events = client.get("/api/audit-log").json()
    assert any(e["action"] == "agent_token.create" for e in events)


def test_revoke_token_prevents_future_registration(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    token = _create_token(client)

    revoke_response = client.post(f"/api/agent-enrollment-tokens/{token['id']}/revoke")
    assert revoke_response.status_code == 200
    assert revoke_response.json()["revoked_at"] is not None

    register_response = client.post(
        "/api/agents/register",
        headers={"Authorization": f"Bearer {token['token']}"},
        json={"hostname": "host-1", "os_type": "linux", "agent_version": "1.2.0"},
    )
    assert register_response.status_code == 401


def test_revoke_unknown_token_returns_404(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)

    assert client.post("/api/agent-enrollment-tokens/does-not-exist/revoke").status_code == 404


# --- Agent registration ---


def test_register_agent_with_valid_token(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    token = _create_token(client, workspace_id="ws-42")

    response = client.post(
        "/api/agents/register",
        headers={"Authorization": f"Bearer {token['token']}"},
        json={"hostname": "prod-host-1", "os_type": "linux", "agent_version": "1.2.0", "capabilities": ["host-inventory"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "active"
    assert "agent_id" in body


def test_register_agent_requires_no_human_session(client: TestClient) -> None:
    # No login at all -- agent routes authenticate via the enrollment token,
    # not a user session, and must work even before any admin exists.
    token_repo_setup = agents.AgentRepository(main.agent_repository.db_path)
    raw_token = token_repo_setup.create_token(agents.EnrollmentTokenCreate(workspace_id="ws-1"), created_by=None).token

    response = client.post(
        "/api/agents/register",
        headers={"Authorization": f"Bearer {raw_token}"},
        json={"hostname": "host-1", "os_type": "linux", "agent_version": "1.2.0"},
    )

    assert response.status_code == 201


def test_register_agent_rejects_invalid_token(client: TestClient) -> None:
    response = client.post(
        "/api/agents/register",
        headers={"Authorization": "Bearer not-a-real-token"},
        json={"hostname": "host-1", "os_type": "linux", "agent_version": "1.2.0"},
    )

    assert response.status_code == 401


def test_register_agent_rejects_missing_token(client: TestClient) -> None:
    response = client.post(
        "/api/agents/register",
        json={"hostname": "host-1", "os_type": "linux", "agent_version": "1.2.0"},
    )

    assert response.status_code == 401


def test_register_agent_hashes_hostname(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    token = _create_token(client)

    agent_id = client.post(
        "/api/agents/register",
        headers={"Authorization": f"Bearer {token['token']}"},
        json={"hostname": "very-secret-hostname.internal", "os_type": "linux", "agent_version": "1.2.0"},
    ).json()["agent_id"]

    agent = client.get(f"/api/agents/{agent_id}").json()
    assert "very-secret-hostname" not in agent["hostname_hash"]
    assert len(agent["hostname_hash"]) == 64  # sha256 hex digest


def test_unsupported_agent_version_is_flagged(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    token = _create_token(client)

    response = client.post(
        "/api/agents/register",
        headers={"Authorization": f"Bearer {token['token']}"},
        json={"hostname": "old-host", "os_type": "linux", "agent_version": "0.5.0"},
    )

    assert response.json()["status"] == "unsupported_version"
    agent_id = response.json()["agent_id"]
    assert client.get(f"/api/agents/{agent_id}").json()["status"] == "unsupported_version"


# --- Heartbeat ---


def test_heartbeat_updates_last_seen(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    token = _create_token(client)
    agent_id = client.post(
        "/api/agents/register",
        headers={"Authorization": f"Bearer {token['token']}"},
        json={"hostname": "host-1", "os_type": "linux", "agent_version": "1.2.0"},
    ).json()["agent_id"]
    before = client.get(f"/api/agents/{agent_id}").json()["last_seen"]

    response = client.post(
        f"/api/agents/{agent_id}/heartbeat", headers={"Authorization": f"Bearer {token['token']}"}
    )

    assert response.status_code == 200
    after = response.json()["last_seen"]
    assert after >= before


def test_heartbeat_requires_valid_token(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    token = _create_token(client)
    agent_id = client.post(
        "/api/agents/register",
        headers={"Authorization": f"Bearer {token['token']}"},
        json={"hostname": "host-1", "os_type": "linux", "agent_version": "1.2.0"},
    ).json()["agent_id"]

    response = client.post(f"/api/agents/{agent_id}/heartbeat", headers={"Authorization": "Bearer wrong-token"})

    assert response.status_code == 401


def test_heartbeat_unknown_agent_returns_404(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    token = _create_token(client)

    response = client.post(
        "/api/agents/does-not-exist/heartbeat", headers={"Authorization": f"Bearer {token['token']}"}
    )

    assert response.status_code == 404


def test_revoked_token_blocks_heartbeat_too(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    token = _create_token(client)
    agent_id = client.post(
        "/api/agents/register",
        headers={"Authorization": f"Bearer {token['token']}"},
        json={"hostname": "host-1", "os_type": "linux", "agent_version": "1.2.0"},
    ).json()["agent_id"]

    client.post(f"/api/agent-enrollment-tokens/{token['id']}/revoke")

    response = client.post(
        f"/api/agents/{agent_id}/heartbeat", headers={"Authorization": f"Bearer {token['token']}"}
    )

    assert response.status_code == 401


# --- Listing (human-facing, must stay behind normal RBAC) ---


def test_list_agents_requires_authentication(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    # Establishes an admin so RBAC leaves setup mode, then a fresh unauthenticated client.
    anon = TestClient(main.app)
    assert anon.get("/api/agents").status_code == 401


def test_list_agents_filters_by_workspace(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    token_a = _create_token(client, workspace_id="ws-a")
    token_b = _create_token(client, workspace_id="ws-b")
    client.post("/api/agents/register", headers={"Authorization": f"Bearer {token_a['token']}"}, json={"hostname": "h1", "os_type": "linux", "agent_version": "1.0.0"})
    client.post("/api/agents/register", headers={"Authorization": f"Bearer {token_b['token']}"}, json={"hostname": "h2", "os_type": "linux", "agent_version": "1.0.0"})

    scoped = client.get("/api/agents", params={"workspace_id": "ws-a"}).json()

    assert len(scoped) == 1
    assert scoped[0]["workspace_id"] == "ws-a"
