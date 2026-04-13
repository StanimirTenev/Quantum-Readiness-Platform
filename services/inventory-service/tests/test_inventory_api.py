import pytest
from fastapi.testclient import TestClient

from app import main
from app.repository import AssetRepository


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "repository", AssetRepository(tmp_path / "inventory.db"))
    with TestClient(main.app) as test_client:
        yield test_client


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "inventory-service"


def test_scan_ingest_and_list_scans(client: TestClient, monkeypatch) -> None:
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
    assert len(scans) == 1

    risks_response = client.get("/risks")
    assert risks_response.status_code == 200
    risks = risks_response.json()
    assert len(risks) == 1
    assert risks[0]["rating"] == "high"
    assert risks[0]["contract_version"] == "stage1-v1"


def test_scan_ingest_accepts_stage2_evidence_shape(client: TestClient, monkeypatch) -> None:
    def fake_score(self, payload):
        return {
            "contract_version": payload["contract_version"],
            "asset_name": payload["asset_name"],
            "scenario": payload["scenario"],
            "scenario_multiplier": 1.0,
            "base_score": 2.0,
            "final_score": 2.0,
            "normalized_score_100": 40.0,
            "rating": "medium",
            "dependency_count": payload["dependency_count"],
            "vendor_blocked": payload["vendor_blocked"],
            "rationale": payload,
        }

    monkeypatch.setattr("app.clients.risk_engine.RiskEngineClient.score", fake_score)

    response = client.post(
        "/scans/ingest",
        json={
            "source": "network",
            "assets": [{"asset_type": "endpoint", "name": "stage2.example:443"}],
            "tls_evidence": {
                "target": "stage2.example:443",
                "tls_version": "TLS1.3",
                "cipher_suite": "TLS_AES_256_GCM_SHA384",
                "server_name": "stage2.example",
                "certificate": {
                    "subject": {"display_dn": "CN=stage2.example"},
                    "issuer": {"display_dn": "CN=Stage2 Issuer"},
                    "validity": {
                        "not_before": "2026-01-01T00:00:00Z",
                        "not_after": "2026-12-31T00:00:00Z",
                    },
                    "algorithms": {"signature": "ECDSA-SHA384", "public_key": "ECDSA"},
                    "san": {"dns_names": ["stage2.example"]},
                },
                "certificate_chain": {
                    "available": True,
                    "presented_chain_length": 2,
                    "summary": "leaf + intermediate",
                },
            },
            "crypto_evidence": {
                "openssl_available": True,
                "openssl_version": "OpenSSL 3.0.15",
                "known_crypto_files": ["/etc/ssl/openssl.cnf"],
                "config_indicators": {"ssh_config_indicators": []},
                "cert_indicators": {"trust_store_indicators": []},
                "package_metadata": {"package_manager_type": "apt", "crypto_packages": []},
            },
        },
    )

    assert response.status_code == 201
    scan_id = response.json()["scan_id"]

    scan = client.get(f"/scans/{scan_id}").json()["scan"]
    cert = scan["tls_evidence"]["certificate"]
    assert cert["subject"] == "CN=stage2.example"
    assert cert["issuer"] == "CN=Stage2 Issuer"
    assert cert["public_key_algorithm"] == "ECDSA"
    assert scan["tls_evidence"]["certificate_chain"]["available"] is True


def test_scan_ingest_tolerates_partial_and_weird_enrichment_blocks(client: TestClient, monkeypatch) -> None:
    def fake_score(self, payload):
        return {
            "contract_version": payload["contract_version"],
            "asset_name": payload["asset_name"],
            "scenario": payload["scenario"],
            "scenario_multiplier": 1.0,
            "base_score": 2.0,
            "final_score": 2.0,
            "normalized_score_100": 40.0,
            "rating": "medium",
            "dependency_count": payload["dependency_count"],
            "vendor_blocked": payload["vendor_blocked"],
            "rationale": payload,
        }

    monkeypatch.setattr("app.clients.risk_engine.RiskEngineClient.score", fake_score)

    response = client.post(
        "/scans/ingest",
        json={
            "source": "host",
            "assets": [{"asset_type": "server", "name": "srv-1"}],
            "host_inventory": {
                "hostname": " srv-1 ",
                "ips": ["10.0.0.10", 42, " "],
            },
            "crypto_evidence": {
                "openssl_available": "yes",
                "known_crypto_files": " /etc/ssl/openssl.cnf ",
                "config_indicators": "unexpected",
            },
            "tls_evidence": {
                "target": "srv-1:443",
                "certificate_chain": "unexpected",
            },
        },
    )

    assert response.status_code == 201
    scan_id = response.json()["scan_id"]
    scan = client.get(f"/scans/{scan_id}").json()["scan"]

    assert scan["host_inventory"]["hostname"] == "srv-1"
    assert scan["host_inventory"]["ips"] == ["10.0.0.10"]
    assert scan["crypto_evidence"]["openssl_available"] is False
    assert scan["crypto_evidence"]["known_crypto_files"] == ["/etc/ssl/openssl.cnf"]
    assert scan["crypto_evidence"]["config_indicators"] is None
    assert scan["tls_evidence"]["certificate_chain"] is None

    tls_warnings = scan["tls_evidence"]["normalization_warnings"]
    assert "tls_evidence.certificate: missing certificate block" in tls_warnings
    assert "tls_evidence.certificate_chain: expected object, dropped invalid value" in tls_warnings


def test_scan_ingest_rejects_invalid_source(client: TestClient) -> None:
    response = client.post(
        "/scans/ingest",
        json={
            "source": "scanner_v2",
            "assets": [{"asset_type": "service", "name": "svc-a"}],
        },
    )

    assert response.status_code == 422
