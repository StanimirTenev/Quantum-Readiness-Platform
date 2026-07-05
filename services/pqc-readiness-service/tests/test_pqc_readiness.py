from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import app.main as main

client = TestClient(main.app)


def _classify(**overrides):
    payload = {"asset_name": "asset"}
    payload.update(overrides)
    return client.post("/classify", json=payload)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "pqc-readiness-service"}


def test_readiness_states_lists_all_five() -> None:
    response = client.get("/readiness-states")
    assert response.status_code == 200
    states = {s["state"] for s in response.json()["states"]}
    assert states == {"classical_only", "hybrid_capable", "pqc_ready", "vendor_blocked", "unknown"}


def test_only_pqc_findings_is_pqc_ready() -> None:
    response = _classify(findings=[{"classification": "pqc_ready"}])
    assert response.status_code == 200
    data = response.json()
    assert data["readiness"] == "pqc_ready"
    assert data["confidence"] == "high"


def test_classical_and_pqc_is_hybrid_capable() -> None:
    response = _classify(findings=[
        {"classification": "classical_vulnerable"},
        {"classification": "pqc_ready"},
    ])
    assert response.status_code == 200
    assert response.json()["readiness"] == "hybrid_capable"


def test_only_classical_is_classical_only() -> None:
    response = _classify(findings=[{"classification": "classical_vulnerable"}])
    assert response.status_code == 200
    assert response.json()["readiness"] == "classical_only"


def test_only_classical_but_hybrid_supported_is_hybrid_capable() -> None:
    response = _classify(findings=[{"classification": "classical_vulnerable"}], hybrid_supported=True)
    assert response.status_code == 200
    assert response.json()["readiness"] == "hybrid_capable"


def test_vendor_blocked_wins_even_with_pqc() -> None:
    response = _classify(findings=[{"classification": "pqc_ready"}], vendor_blocked=True)
    assert response.status_code == 200
    assert response.json()["readiness"] == "vendor_blocked"


def test_no_relevant_findings_is_unknown() -> None:
    response = _classify(findings=[{"classification": "symmetric_reduced"}, {"classification": "hash"}])
    assert response.status_code == 200
    data = response.json()
    assert data["readiness"] == "unknown"
    assert data["confidence"] == "low"


def test_empty_findings_is_unknown() -> None:
    response = _classify()
    assert response.status_code == 200
    assert response.json()["readiness"] == "unknown"


def test_signals_reflect_hndl_and_weak_key() -> None:
    response = _classify(findings=[
        {"classification": "classical_vulnerable", "harvest_now_decrypt_later": True, "weak_key": True},
    ])
    assert response.status_code == 200
    signals = response.json()["signals"]
    assert signals["hndl_exposure"] is True
    assert signals["weak_key_present"] is True
    assert signals["classical_vulnerable_present"] is True
    assert signals["finding_count"] == 1


def test_missing_asset_name_returns_422() -> None:
    response = client.post("/classify", json={"findings": []})
    assert response.status_code == 422
