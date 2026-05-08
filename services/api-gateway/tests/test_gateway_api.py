from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import main

client = TestClient(main.app)


def test_post_api_scans_host_forces_host_source_and_forwards(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"scan_id": "scan-1", "created": 1}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.post(
        "/api/scans/host?scenario=hidden_capability",
        json={"assets": [{"asset_type": "server", "name": "host-1"}], "source": "manual"},
    )

    assert response.status_code == 200
    assert response.json()["scan_id"] == "scan-1"
    assert captured["method"] == "POST"
    assert "scenario=hidden_capability" in captured["url"]
    assert captured["payload"]["source"] == "host"


def test_get_api_assets_asset_id_risk_builds_payload_and_returns_wrapped_response(monkeypatch) -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        calls.append((method, url, payload))
        if url.endswith("/assets/asset-1"):
            return {
                "id": "asset-1",
                "name": "payments-api",
                "criticality": 5,
                "environment": "production",
                "vendor": "acme",
                "lifecycle_years": 10,
            }
        return {
            "scenario": "early_break",
            "normalized_score_100": 88.0,
            "rating": "critical",
        }

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/assets/asset-1/risk?scenario=early_break")

    assert response.status_code == 200
    data = response.json()
    assert data["asset_id"] == "asset-1"
    assert data["asset_name"] == "payments-api"
    assert data["risk"]["rating"] == "critical"

    assert len(calls) == 2
    assert calls[0][0] == "GET"
    assert calls[1][0] == "POST"
    assert calls[1][2]["scenario"] == "early_break"
    assert calls[1][2]["criticality"] == 5.0


def test_post_api_policies_evaluate_forwards_payload_and_returns_upstream(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {
            "asset_name": "payments-api",
            "decision": "review",
            "score": 65,
            "reasons": ["high_risk_production_asset"],
            "rule_id": "pqc-readiness-gate-v1",
            "rule_version": "1.0.0",
        }

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {
        "asset_id": "asset-1",
        "asset_name": "payments-api",
        "asset_type": "service",
        "environment": "production",
        "criticality": 5,
        "normalized_score_100": 65,
        "rating": "high",
        "vendor_blocked": False,
        "dependency_count": 3,
        "scenario": "public_timeline",
    }

    response = client.post("/api/policies/evaluate", json=payload)

    assert response.status_code == 200
    assert response.json()["decision"] == "review"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/evaluate")
    assert captured["payload"] == payload
    assert response.json() == {
        "asset_name": "payments-api",
        "decision": "review",
        "score": 65,
        "reasons": ["high_risk_production_asset"],
        "rule_id": "pqc-readiness-gate-v1",
        "rule_version": "1.0.0",
    }
