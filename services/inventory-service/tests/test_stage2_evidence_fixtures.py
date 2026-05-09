import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.repository import AssetRepository

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "stage2_evidence"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "repository", AssetRepository(tmp_path / "inventory.db"))
    with TestClient(main.app) as test_client:
        yield test_client


def _load_fixture(name: str) -> dict:
    with (FIXTURES_DIR / name).open("r", encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


def _fake_score(self, payload):
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


@pytest.mark.parametrize(
    "fixture_name,expected_source",
    [
        ("minimal_ingest.json", "network"),
        ("host_enriched_ingest.json", "host"),
        ("network_enriched_ingest.json", "network"),
    ],
)
def test_official_stage2_fixtures_ingest_success(
    client: TestClient,
    monkeypatch,
    fixture_name: str,
    expected_source: str,
) -> None:
    monkeypatch.setattr("app.clients.risk_engine.RiskEngineClient.score", _fake_score)

    payload = _load_fixture(fixture_name)
    response = client.post("/scans/ingest", json=payload)

    assert response.status_code == 201
    scan_id = response.json()["scan_id"]

    scan = client.get(f"/scans/{scan_id}").json()["scan"]
    assert scan["source"] == expected_source


def test_network_fixture_preserves_certificate_chain(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.clients.risk_engine.RiskEngineClient.score", _fake_score)

    response = client.post("/scans/ingest", json=_load_fixture("network_enriched_ingest.json"))
    assert response.status_code == 201

    scan = client.get(f"/scans/{response.json()['scan_id']}").json()["scan"]
    chain = scan["tls_evidence"]["certificate_chain"]
    assert isinstance(chain["certificates"], list)
    assert chain["certificates"][0]["sha256_fingerprint"] == "11aa22bb33cc44dd55ee66ff77889900aabbccddeeff00112233445566778899"
