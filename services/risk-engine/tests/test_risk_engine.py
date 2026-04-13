from fastapi.testclient import TestClient

from app.main import app, calculate_base_score

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "risk-engine"}


def test_scenarios() -> None:
    response = client.get("/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert "public_timeline" in data
    assert "hidden_capability" in data
    assert "partial_break" in data
    assert "compliance_pressure" in data
    assert data["hidden_capability"] == 1.35
    assert data["partial_break"] == 1.10
    assert data["compliance_pressure"] == 1.18


def test_calculate_base_score() -> None:
    class Obj:
        criticality = 5
        confidentiality_lifetime = 5
        quantum_exposure = 5
        blast_radius = 5
        vendor_lock_in = 5
        migration_difficulty = 5

    score = calculate_base_score(Obj())
    assert score == 5.0


def test_score_endpoint() -> None:
    payload = {
        "contract_version": "stage1-v1",
        "asset_name": "vpn-gateway-01",
        "criticality": 5,
        "confidentiality_lifetime": 5,
        "quantum_exposure": 5,
        "blast_radius": 5,
        "vendor_lock_in": 4,
        "migration_difficulty": 3,
        "scenario": "hidden_capability",
    }
    response = client.post("/score", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["scenario"] == "hidden_capability"
    assert data["contract_version"] == "stage1-v1"
    assert data["asset_name"] == "vpn-gateway-01"
    assert data["scenario_multiplier"] == 1.35
    assert data["base_score"] > 0
    assert data["final_score"] >= data["base_score"]
    assert data["rating"] in {"minimal", "low", "medium", "high", "critical"}


def test_score_validation() -> None:
    payload = {
        "contract_version": "stage1-v1",
        "asset_name": "vpn-gateway-01",
        "criticality": 7,
        "confidentiality_lifetime": 5,
        "quantum_exposure": 5,
        "blast_radius": 5,
        "vendor_lock_in": 4,
        "migration_difficulty": 3,
        "scenario": "hidden_capability",
    }
    response = client.post("/score", json=payload)
    assert response.status_code == 422


def test_score_endpoint_supports_compliance_pressure() -> None:
    payload = {
        "contract_version": "stage1-v1",
        "asset_name": "ca-service",
        "criticality": 4,
        "confidentiality_lifetime": 4,
        "quantum_exposure": 4,
        "blast_radius": 4,
        "vendor_lock_in": 4,
        "migration_difficulty": 4,
        "scenario": "compliance_pressure",
    }
    response = client.post("/score", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["scenario"] == "compliance_pressure"
    assert data["scenario_multiplier"] == 1.18


def test_score_endpoint_supports_partial_break() -> None:
    payload = {
        "contract_version": "stage1-v1",
        "asset_name": "legacy-endpoint",
        "criticality": 3,
        "confidentiality_lifetime": 3,
        "quantum_exposure": 3,
        "blast_radius": 3,
        "vendor_lock_in": 3,
        "migration_difficulty": 3,
        "scenario": "partial_break",
    }
    response = client.post("/score", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["scenario"] == "partial_break"
    assert data["scenario_multiplier"] == 1.10
