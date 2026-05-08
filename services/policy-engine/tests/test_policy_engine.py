from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import app.main as main

client = TestClient(main.app)


def test_health_returns_ok() -> None:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "policy-engine"}


def test_evaluate_vendor_blocked_returns_deny() -> None:
    response = client.post('/evaluate', json={"asset_name": "a", "criticality": 3, "normalized_score_100": 40, "vendor_blocked": True})
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "deny"
    assert "vendor_blocked" in data["reasons"]


def test_evaluate_critical_score_returns_deny() -> None:
    response = client.post('/evaluate', json={"asset_name": "a", "criticality": 3, "normalized_score_100": 85})
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "deny"
    assert "critical_risk_score" in data["reasons"]


def test_evaluate_high_risk_production_returns_review() -> None:
    response = client.post('/evaluate', json={"asset_name": "a", "environment": "production", "criticality": 5, "normalized_score_100": 65})
    assert response.status_code == 200
    assert response.json()["decision"] == "review"


def test_evaluate_dependency_complexity_returns_review() -> None:
    response = client.post('/evaluate', json={"asset_name": "a", "criticality": 3, "normalized_score_100": 55, "dependency_count": 6})
    assert response.status_code == 200
    assert response.json()["decision"] == "review"


def test_evaluate_low_risk_non_production_returns_allow() -> None:
    response = client.post('/evaluate', json={"asset_name": "a", "environment": "staging", "criticality": 2, "normalized_score_100": 25})
    assert response.status_code == 200
    assert response.json()["decision"] == "allow"


def test_evaluate_missing_asset_name_returns_422() -> None:
    response = client.post('/evaluate', json={"criticality": 2, "normalized_score_100": 25})
    assert response.status_code == 422


def test_evaluate_invalid_score_over_100_returns_422() -> None:
    response = client.post('/evaluate', json={"asset_name": "a", "criticality": 2, "normalized_score_100": 101})
    assert response.status_code == 422
