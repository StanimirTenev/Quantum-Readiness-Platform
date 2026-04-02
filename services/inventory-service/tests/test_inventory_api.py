from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "inventory-service"


def test_scan_ingest_and_list_scans() -> None:
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
    assert scans[0]["source"] in {"network", "host", "repo", "manual"}
