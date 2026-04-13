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
        "base_score": 3.0,
        "final_score": 3.0,
        "normalized_score_100": 60.0,
        "rating": "high",
        "dependency_count": payload["dependency_count"],
        "vendor_blocked": payload["vendor_blocked"],
        "rationale": payload,
    }


def test_stage2_smoke_validation_enriched_ingest_scan_risk_flow(client: TestClient, monkeypatch) -> None:
    """Short smoke path for Stage 2 enriched evidence using current Stage 1/2 modules."""
    monkeypatch.setattr("app.clients.risk_engine.RiskEngineClient.score", _fake_score)

    host_response = client.post("/scans/ingest", json=_load_fixture("host_enriched_ingest.json"))
    network_response = client.post("/scans/ingest", json=_load_fixture("network_enriched_ingest.json"))

    assert host_response.status_code == 201
    assert network_response.status_code == 201

    host_scan_id = host_response.json()["scan_id"]
    network_scan_id = network_response.json()["scan_id"]

    host_scan = client.get(f"/scans/{host_scan_id}").json()
    network_scan = client.get(f"/scans/{network_scan_id}").json()

    assert host_scan["scan"]["source"] == "host"
    assert network_scan["scan"]["source"] == "network"
    assert len(host_scan["risks"]) > 0
    assert len(network_scan["risks"]) > 0

    all_scans = client.get("/scans").json()
    stored_ids = {scan["id"] for scan in all_scans}
    assert host_scan_id in stored_ids
    assert network_scan_id in stored_ids
