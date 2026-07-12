from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import auth
import main


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "auth_repository", auth.AuthRepository(tmp_path / "gateway.db"))
    with TestClient(main.app) as test_client:
        yield test_client


def test_bootstrap_creates_first_admin(client: TestClient) -> None:
    response = client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})

    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "admin"
    assert body["role"] == "admin"


def test_bootstrap_rejects_once_an_admin_exists(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})

    response = client.post("/api/auth/bootstrap", json={"username": "someone-else", "password": "correct-horse-2"})

    assert response.status_code == 409


def test_password_is_not_stored_plaintext(client: TestClient, tmp_path) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})

    user = main.auth_repository.verify_credentials("admin", "correct-horse-1")
    assert user is not None
    with main.auth_repository._connect() as connection:  # noqa: SLF001 -- test-only introspection
        row = connection.execute("SELECT password_hash FROM users WHERE username = ?", ("admin",)).fetchone()
    assert dict(row)["password_hash"] != "correct-horse-1"


def test_login_sets_session_cookie_and_me_returns_user(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})

    login_response = client.post("/api/auth/login", json={"username": "admin", "password": "correct-horse-1"})
    assert login_response.status_code == 200
    assert "qrp_session" in login_response.cookies

    me_response = client.get("/api/auth/me")
    assert me_response.status_code == 200
    assert me_response.json()["username"] == "admin"


def test_login_rejects_wrong_password(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})

    response = client.post("/api/auth/login", json={"username": "admin", "password": "wrong-password"})

    assert response.status_code == 401
    assert "qrp_session" not in response.cookies


def test_me_without_session_is_401(client: TestClient) -> None:
    assert client.get("/api/auth/me").status_code == 401


def test_logout_clears_session(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    client.post("/api/auth/login", json={"username": "admin", "password": "correct-horse-1"})
    assert client.get("/api/auth/me").status_code == 200

    logout_response = client.post("/api/auth/logout")
    assert logout_response.status_code == 204

    assert client.get("/api/auth/me").status_code == 401


def test_change_password_then_login_with_new_password(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    client.post("/api/auth/login", json={"username": "admin", "password": "correct-horse-1"})

    change_response = client.post(
        "/api/auth/password",
        json={"current_password": "correct-horse-1", "new_password": "new-correct-horse-2"},
    )
    assert change_response.status_code == 204

    client.post("/api/auth/logout")
    old_login = client.post("/api/auth/login", json={"username": "admin", "password": "correct-horse-1"})
    assert old_login.status_code == 401
    new_login = client.post("/api/auth/login", json={"username": "admin", "password": "new-correct-horse-2"})
    assert new_login.status_code == 200


def test_change_password_rejects_wrong_current_password(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    client.post("/api/auth/login", json={"username": "admin", "password": "correct-horse-1"})

    response = client.post(
        "/api/auth/password",
        json={"current_password": "wrong-current", "new_password": "new-correct-horse-2"},
    )

    assert response.status_code == 401


# --- RBAC v1 (Product v1 roadmap Phase 3 item 7) ---


def _login_as(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def test_rbac_is_open_before_any_admin_is_bootstrapped(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})

    response = client.post("/api/scans/host", json={"assets": [{"asset_type": "server", "name": "h1"}]})

    assert response.status_code == 200


def test_unauthenticated_request_is_rejected_once_admin_exists(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})

    response = client.get("/api/assets")

    assert response.status_code == 401


def test_auditor_cannot_create_scans(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")
    client.post("/api/users", json={"username": "auditor1", "password": "auditor-pass1", "role": "auditor"})
    client.post("/api/auth/logout")

    _login_as(client, "auditor1", "auditor-pass1")
    response = client.post("/api/scans/host", json={"assets": [{"asset_type": "server", "name": "h1"}]})

    assert response.status_code == 403


def test_security_architect_can_create_scans(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w1"})
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")
    client.post("/api/users", json={"username": "sa1", "password": "sa-password1", "role": "security_architect"})
    client.post("/api/auth/logout")

    _login_as(client, "sa1", "sa-password1")
    response = client.post("/api/scans/host", json={"assets": [{"asset_type": "server", "name": "h1"}]})

    assert response.status_code == 200


def test_operator_cannot_access_admin_only_route(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")
    client.post("/api/users", json={"username": "operator1", "password": "operator-pass1", "role": "operator"})
    client.post("/api/auth/logout")

    _login_as(client, "operator1", "operator-pass1")
    response = client.get("/api/users")

    assert response.status_code == 403


def test_admin_can_manage_users(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")

    create_response = client.post("/api/users", json={"username": "op1", "password": "operator-pass1", "role": "operator"})
    assert create_response.status_code == 201
    assert create_response.json()["role"] == "operator"

    list_response = client.get("/api/users")
    assert list_response.status_code == 200
    usernames = {u["username"] for u in list_response.json()}
    assert usernames == {"admin", "op1"}


def test_create_user_rejects_duplicate_username(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")

    response = client.post("/api/users", json={"username": "admin", "password": "whatever12", "role": "operator"})

    assert response.status_code == 409


def test_api_key_bypasses_rbac(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "QRP_API_KEY", "test-shared-key")
    headers = {"X-API-Key": "test-shared-key"}
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"}, headers=headers)

    response = client.get("/api/users", headers=headers)

    assert response.status_code == 200
