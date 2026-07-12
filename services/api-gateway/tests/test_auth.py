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
