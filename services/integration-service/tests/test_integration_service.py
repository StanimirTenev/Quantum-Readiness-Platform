from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import app.main as main

client = TestClient(main.app)


def _dry_run(**overrides):
    payload = {"action": "rotate_certificate", "target_type": "ca", "asset_name": "payments-api"}
    payload.update(overrides)
    return client.post("/dry-run", json=payload)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "integration-service"}


def test_integrations_are_all_disabled() -> None:
    response = client.get("/integrations")
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "dry_run_disabled"
    assert data["executed_changes_supported"] is False
    assert all(t["status"] == "disabled" for t in data["targets"])


def test_dry_run_never_executes_even_when_fully_approved() -> None:
    response = _dry_run(approved=True, approvals_provided=["security_review", "change_approval"])
    assert response.status_code == 200
    data = response.json()
    assert data["executed"] is False
    assert data["mode"] == "dry_run_disabled"
    assert "integration_execution_disabled" in data["blocked_reasons"]
    # It would pass the approval gate, but execution remains disabled.
    assert data["approvals_satisfied"] is True
    assert data["would_execute_if_enabled"] is True


def test_dry_run_missing_approvals_not_satisfied() -> None:
    response = _dry_run(approved=True, approvals_provided=["security_review"])
    assert response.status_code == 200
    data = response.json()
    assert data["approvals_satisfied"] is False
    assert data["would_execute_if_enabled"] is False
    assert any("missing approvals" in w for w in data["warnings"])


def test_dry_run_unrecognized_action_is_blocked() -> None:
    response = _dry_run(action="delete_everything")
    assert response.status_code == 200
    data = response.json()
    assert data["recognized_action"] is False
    assert "unrecognized_action" in data["blocked_reasons"]
    assert data["would_execute_if_enabled"] is False


def test_dry_run_wrong_target_type_is_blocked() -> None:
    response = _dry_run(action="sign_artifact", target_type="ca", approved=True, approvals_provided=["release_approval"])
    assert response.status_code == 200
    data = response.json()
    assert "target_type_not_allowed_for_action" in data["blocked_reasons"]
    assert data["would_execute_if_enabled"] is False


def test_dry_run_rejects_sensitive_material() -> None:
    response = _dry_run(
        approved=True,
        approvals_provided=["security_review", "change_approval"],
        parameters={"private_key": "-----BEGIN...", "note": "rotate"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "sensitive_material_rejected" in data["blocked_reasons"]
    assert data["would_execute_if_enabled"] is False
    # Sensitive keys are never echoed back.
    assert data["parameter_keys"] == []
    assert "private_key" not in response.text


def test_dry_run_rejects_nested_sensitive_material() -> None:
    response = _dry_run(parameters={"outer": {"api_token": "abc"}})
    assert response.status_code == 200
    assert "sensitive_material_rejected" in response.json()["blocked_reasons"]


def test_dry_run_safe_parameters_are_echoed_as_keys() -> None:
    response = _dry_run(parameters={"reason": "expiry", "ticket": "OPS-1"})
    assert response.status_code == 200
    assert response.json()["parameter_keys"] == ["reason", "ticket"]


def test_dry_run_invalid_target_type_returns_422() -> None:
    response = _dry_run(target_type="production_root")
    assert response.status_code == 422


def test_dry_run_missing_asset_name_returns_422() -> None:
    response = client.post("/dry-run", json={"action": "open_ticket", "target_type": "ticketing"})
    assert response.status_code == 422
