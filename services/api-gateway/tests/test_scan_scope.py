from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import audit
import auth
import main
import scan_scope


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "gateway.db"
    monkeypatch.setattr(main, "auth_repository", auth.AuthRepository(db_path))
    monkeypatch.setattr(main, "audit_repository", audit.AuditRepository(db_path))
    monkeypatch.setattr(main, "scan_scope_repository", scan_scope.ScanScopeRepository(db_path))
    with TestClient(main.app) as test_client:
        yield test_client


def _login_as(client: TestClient, username: str, password: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200


def _bootstrap_and_login_admin(client: TestClient) -> None:
    client.post("/api/auth/bootstrap", json={"username": "admin", "password": "correct-horse-1"})
    _login_as(client, "admin", "correct-horse-1")


NETWORK_PAYLOAD = {
    "assets": [{"asset_type": "endpoint", "name": "10.0.0.5:443"}],
    "tls_evidence": {"collected": True, "target": "10.0.0.5:443", "port": 443},
}


# --- Unit-level: scan_scope.py's matching logic ---


def test_validate_cidr_rejects_internet_wide() -> None:
    with pytest.raises(ValueError):
        scan_scope.ScanScopeCreate(workspace_id="w1", allowed_cidr_ranges=["0.0.0.0/0"])


def test_check_target_allows_host_in_cidr() -> None:
    scope = scan_scope.ScanScope(
        id="s1", workspace_id="w1", allowed_cidr_ranges=["10.0.0.0/24"], created_at="now"
    )
    allowed, _ = scan_scope.check_target(scope, "10.0.0.5:443")
    assert allowed is True


def test_check_target_rejects_host_outside_scope() -> None:
    scope = scan_scope.ScanScope(
        id="s1", workspace_id="w1", allowed_cidr_ranges=["10.0.0.0/24"], created_at="now"
    )
    allowed, _ = scan_scope.check_target(scope, "8.8.8.8:443")
    assert allowed is False


def test_check_target_exclusion_wins_over_allowed_cidr() -> None:
    scope = scan_scope.ScanScope(
        id="s1", workspace_id="w1",
        allowed_cidr_ranges=["10.0.0.0/24"], excluded_targets=["10.0.0.5"],
        created_at="now",
    )
    allowed, reason = scan_scope.check_target(scope, "10.0.0.5:443")
    assert allowed is False
    assert "excluded" in reason


def test_check_target_domain_wildcard() -> None:
    scope = scan_scope.ScanScope(
        id="s1", workspace_id="w1", allowed_domains=["*.example.com"], created_at="now"
    )
    assert scan_scope.check_target(scope, "api.example.com:443")[0] is True
    assert scan_scope.check_target(scope, "evil.com:443")[0] is False


# --- API-level: RBAC on scope creation ---


def test_create_scope_requires_admin_or_security_architect(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    client.post("/api/users", json={"username": "op1", "password": "operator-pass1", "role": "operator"})
    client.post("/api/auth/logout")
    _login_as(client, "op1", "operator-pass1")

    response = client.post("/api/scan-scopes", json={"workspace_id": "w1", "allowed_cidr_ranges": ["10.0.0.0/24"]})

    assert response.status_code == 403


def test_create_scope_rejects_internet_wide_cidr_via_api(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)

    response = client.post("/api/scan-scopes", json={"workspace_id": "w1", "allowed_cidr_ranges": ["0.0.0.0/0"]})

    assert response.status_code == 422


def test_create_scope_writes_audit_event(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)

    client.post("/api/scan-scopes", json={"workspace_id": "w1", "allowed_cidr_ranges": ["10.0.0.0/24"]})

    events = client.get("/api/audit-log").json()
    creations = [e for e in events if e["action"] == "scan_scope.create"]
    assert len(creations) == 1
    assert creations[0]["workspace_id"] == "w1"


# --- API-level: enforcement on scan ingestion ---


def test_workspace_without_scope_accepts_any_target(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w-unscoped"})
    _bootstrap_and_login_admin(client)

    response = client.post("/api/scans/network?workspace_id=w-unscoped", json=NETWORK_PAYLOAD)

    assert response.status_code == 200


def test_scoped_workspace_accepts_allowed_target(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(main, "_request_json", lambda *a, **k: {"created": 1, "scan_id": "s1", "workspace_id": "w-scoped"})
    _bootstrap_and_login_admin(client)
    client.post("/api/scan-scopes", json={"workspace_id": "w-scoped", "allowed_cidr_ranges": ["10.0.0.0/24"]})

    response = client.post("/api/scans/network?workspace_id=w-scoped", json=NETWORK_PAYLOAD)

    assert response.status_code == 200


def test_scoped_workspace_rejects_disallowed_target(client: TestClient):
    _bootstrap_and_login_admin(client)
    client.post("/api/scan-scopes", json={"workspace_id": "w-scoped", "allowed_cidr_ranges": ["192.168.0.0/24"]})

    response = client.post("/api/scans/network?workspace_id=w-scoped", json=NETWORK_PAYLOAD)

    assert response.status_code == 403


def test_scoped_workspace_rejects_excluded_target_even_in_allowed_cidr(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    client.post(
        "/api/scan-scopes",
        json={
            "workspace_id": "w-scoped",
            "allowed_cidr_ranges": ["10.0.0.0/24"],
            "excluded_targets": ["10.0.0.5"],
        },
    )

    response = client.post("/api/scans/network?workspace_id=w-scoped", json=NETWORK_PAYLOAD)

    assert response.status_code == 403


def test_rejected_scan_writes_audit_event(client: TestClient) -> None:
    _bootstrap_and_login_admin(client)
    client.post("/api/scan-scopes", json={"workspace_id": "w-scoped", "allowed_cidr_ranges": ["192.168.0.0/24"]})

    client.post("/api/scans/network?workspace_id=w-scoped", json=NETWORK_PAYLOAD)

    events = client.get("/api/audit-log").json()
    rejections = [e for e in events if e["action"] == "scan.rejected"]
    assert len(rejections) == 1
    assert rejections[0]["workspace_id"] == "w-scoped"
