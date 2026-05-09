import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.repository import AssetRepository

FIXTURES = Path(__file__).parent / "fixtures" / "stage2_evidence"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "repository", AssetRepository(tmp_path / "inventory.db"))
    monkeypatch.setattr("app.clients.risk_engine.RiskEngineClient.score", lambda *args, **kwargs: {
        "contract_version": "stage1-v1", "asset_name": "a", "scenario": "public_timeline",
        "scenario_multiplier": 1.0, "base_score": 1.0, "final_score": 1.0,
        "normalized_score_100": 20.0, "rating": "low", "dependency_count": 0,
        "vendor_blocked": False, "rationale": {}
    })
    with TestClient(main.app) as test_client:
        yield test_client


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_stage1_minimal_payload_still_ingests(client: TestClient) -> None:
    response = client.post("/scans/ingest", json=_load("minimal_ingest.json"))
    assert response.status_code == 201
    body = response.json()
    assert body["scan_id"] and body["created"] == 1 and len(body["asset_ids"]) == 1


def test_host_enriched_crypto_blocks_ingest_and_preserve(client: TestClient) -> None:
    response = client.post("/scans/ingest", json=_load("host_enriched_ingest.json"))
    assert response.status_code == 201
    scan = client.get(f"/scans/{response.json()['scan_id']}").json()["scan"]
    assert len(scan["crypto_evidence"]["package_metadata"]["packages"]) == 1
    assert "certificate_file_indicators" in scan["crypto_evidence"]["cert_indicators"]


def test_network_enriched_tls_metadata_ingest_and_preserve_chain(client: TestClient) -> None:
    response = client.post("/scans/ingest", json=_load("network_enriched_ingest.json"))
    assert response.status_code == 201
    scan = client.get(f"/scans/{response.json()['scan_id']}").json()["scan"]
    chain = scan["tls_evidence"]["certificate_chain"]
    assert isinstance(chain["certificates"], list)
    assert chain["certificates"][0]["subject"]["display_dn"] == "CN=api.example.internal,O=Example Internal"


def test_missing_optional_stage2_blocks_does_not_fail(client: TestClient) -> None:
    payload = _load("minimal_ingest.json")
    payload.pop("tls_metadata", None)
    response = client.post("/scans/ingest", json=payload)
    assert response.status_code == 201


def test_invalid_package_metadata_packages_type_is_rejected(client: TestClient) -> None:
    response = client.post("/scans/ingest", json=_load("invalid_package_metadata.json"))
    assert response.status_code == 422


def test_invalid_tls_metadata_port_type_is_rejected(client: TestClient) -> None:
    payload = _load("invalid_tls_metadata.json")
    response = client.post("/scans/ingest", json=payload)
    assert response.status_code == 422
