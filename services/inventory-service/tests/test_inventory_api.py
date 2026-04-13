from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "inventory-service"


def test_scan_ingest_and_list_scans(monkeypatch) -> None:
    def fake_score(self, payload):
        return {
            "contract_version": payload["contract_version"],
            "asset_name": payload["asset_name"],
            "scenario": payload["scenario"],
            "scenario_multiplier": 1.0,
            "base_score": 3.4,
            "final_score": 3.4,
            "normalized_score_100": 68.0,
            "rating": "high",
            "dependency_count": payload["dependency_count"],
            "vendor_blocked": payload["vendor_blocked"],
            "rationale": payload,
        }

    monkeypatch.setattr("app.clients.risk_engine.RiskEngineClient.score", fake_score)

    ingest_response = client.post(
        "/scans/ingest",
        json={
            "source": "network",
            "assets": [
                {
                    "asset_type": "endpoint",
                    "name": "google.com:443",
                    "criticality": 3,
                    "environment": "unknown",
                    "lifecycle_years": 3,
                }
            ],
            "tls_evidence": {
                "target": "google.com:443",
                "tls_version": "TLS1.3",
                "cipher_suite": "TLS_AES_128_GCM_SHA256",
                "server_name": "google.com",
                "certificate": {
                    "subject": "CN=*.google.com",
                    "issuer": "CN=Example Issuer",
                    "not_before": "2026-01-01T00:00:00Z",
                    "not_after": "2026-06-01T00:00:00Z",
                    "signature_algorithm": "ECDSA-SHA256",
                    "public_key_algorithm": "ECDSA",
                    "dns_names": ["google.com"],
                },
            },
        },
    )
    assert ingest_response.status_code == 201
    data = ingest_response.json()
    assert data["created"] == 1
    assert data["scan_id"]

    scans_response = client.get("/scans")
    assert scans_response.status_code == 200
    scans = scans_response.json()
    assert len(scans) >= 1

    risks_response = client.get("/risks")
    assert risks_response.status_code == 200
    risks = risks_response.json()
    assert len(risks) >= 1
    assert risks[0]["rating"] == "high"
    assert risks[0]["contract_version"] == "stage1-v1"
