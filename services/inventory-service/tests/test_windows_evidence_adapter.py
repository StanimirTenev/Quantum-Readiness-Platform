import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main
from app.repository import AssetRepository
from app.windows_evidence import (
    build_ingest_request,
    build_windows_normalized_signals,
)

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "stage2_evidence"
    / "windows_enriched_ingest_example.json"
)

REQUIRED_SIGNAL_KEYS = {
    "platform",
    "asset_type",
    "software_total_observed",
    "crypto_relevant_software_count",
    "certificates_observed_count",
    "expired_certificates_count",
    "weak_signature_indicators_count",
    "crypto_relevant_services_count",
    "domain_joined",
    "ad_details_collected",
    "domain_controller_role_observed",
    "private_keys_exported",
    "warnings_count",
    "errors_count",
}


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


# --- normalized signal builder ---------------------------------------------


def test_normalized_signals_match_required_contract_shape() -> None:
    signals = build_windows_normalized_signals(_load_fixture())
    assert set(signals) == REQUIRED_SIGNAL_KEYS


def test_normalized_signals_carry_expected_aggregate_values() -> None:
    signals = build_windows_normalized_signals(_load_fixture())
    assert signals["platform"] == "windows"
    assert signals["asset_type"] == "endpoint"
    assert signals["software_total_observed"] == 42
    assert signals["crypto_relevant_software_count"] == 3
    assert signals["certificates_observed_count"] == 12
    assert signals["expired_certificates_count"] == 1
    assert signals["domain_joined"] is True
    assert signals["private_keys_exported"] is False
    assert signals["warnings_count"] == 1
    assert signals["errors_count"] == 0


def test_normalized_signals_are_defensive_on_empty_document() -> None:
    signals = build_windows_normalized_signals({})
    assert set(signals) == REQUIRED_SIGNAL_KEYS
    assert signals["software_total_observed"] == 0
    assert signals["domain_joined"] is False
    assert signals["platform"] == "windows"


def test_normalized_signals_coerce_non_numeric_counts_to_zero() -> None:
    doc = {
        "asset": {"platform": "windows", "asset_type": "endpoint"},
        "windows_evidence": {
            "installed_software_summary": {"total_observed": "lots"},
            "certificate_store_indicators": {"certificates_observed_count": None},
            "warnings": "not-a-list",
        },
    }
    signals = build_windows_normalized_signals(doc)
    assert signals["software_total_observed"] == 0
    assert signals["certificates_observed_count"] == 0
    assert signals["warnings_count"] == 0


# --- ingest request builder ------------------------------------------------


def test_ingest_request_is_host_scoped_single_asset() -> None:
    request = build_ingest_request(_load_fixture())
    assert request.source == "host"
    assert len(request.assets) == 1
    asset = request.assets[0]
    assert asset.asset_type == "endpoint"
    assert asset.name == "redacted-windows-host"
    assert asset.environment == "windows_server_or_workstation"
    assert asset.criticality == 3  # domain-joined workstation


def test_ingest_request_persists_normalized_signals_on_crypto_evidence() -> None:
    request = build_ingest_request(_load_fixture())
    dumped = request.crypto_evidence.model_dump()
    assert dumped["windows_normalized_signals"]["certificates_observed_count"] == 12
    # 3 crypto-relevant packages observed -> openssl_available true
    assert request.crypto_evidence.openssl_available is True


def test_ingest_request_maps_os_metadata_to_host_inventory() -> None:
    request = build_ingest_request(_load_fixture())
    assert request.host_inventory.os == "windows_server_or_workstation"
    assert request.host_inventory.architecture == "x86_64"


def test_ingest_request_has_no_certificate_when_surface_absent() -> None:
    request = build_ingest_request(_load_fixture())
    assert request.tls_evidence is None


def test_ingest_request_prefers_quantum_vulnerable_certificate() -> None:
    doc = _load_fixture()
    doc["certificate_crypto_surface"] = [
        {"public_key_algorithm": "ECC", "public_key_size": 256, "signature_algorithm": "sha256ECDSA", "not_after": "2027-01-01T00:00:00Z"},
        {"public_key_algorithm": "RSA", "public_key_size": 1024, "signature_algorithm": "sha1RSA", "not_after": "2020-01-01T00:00:00Z"},
    ]
    request = build_ingest_request(doc)
    assert request.tls_evidence is not None
    cert = request.tls_evidence.certificate
    # RSA and ECC are both vulnerable; the first vulnerable candidate (ECC) wins,
    # and the Windows friendly name is normalized to risk_mapper's vocabulary.
    assert cert.public_key_algorithm == "EC"


def test_ingest_request_normalizes_rsa_friendly_name() -> None:
    doc = _load_fixture()
    doc["certificate_crypto_surface"] = [
        {"public_key_algorithm": "RSA", "public_key_size": 2048, "signature_algorithm": "sha256RSA", "not_after": "2027-01-01T00:00:00Z"},
    ]
    request = build_ingest_request(doc)
    assert request.tls_evidence.certificate.public_key_algorithm == "RSA"


def test_ingest_request_maps_unknown_asset_type_to_other() -> None:
    doc = _load_fixture()
    doc["asset"]["asset_type"] = "toaster"
    request = build_ingest_request(doc)
    assert request.assets[0].asset_type == "other"


# --- endpoint --------------------------------------------------------------


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "repository", AssetRepository(tmp_path / "inventory.db"))

    def fake_score(self, payload):
        return {
            "contract_version": payload["contract_version"],
            "asset_name": payload["asset_name"],
            "scenario": payload["scenario"],
            "scenario_multiplier": 1.0,
            "base_score": 3.1,
            "final_score": 3.1,
            "normalized_score_100": 62.0,
            "rating": "high",
            "dependency_count": payload["dependency_count"],
            "vendor_blocked": payload["vendor_blocked"],
            "rationale": payload,
        }

    monkeypatch.setattr("app.clients.risk_engine.RiskEngineClient.score", fake_score)
    with TestClient(main.app) as test_client:
        yield test_client


def test_windows_ingest_endpoint_persists_and_scores(client: TestClient) -> None:
    response = client.post("/scans/ingest/windows", json=_load_fixture())
    assert response.status_code == 201
    data = response.json()
    assert data["source"] == "host"
    assert data["created"] == 1
    scan_id = data["scan_id"]

    scan = client.get(f"/scans/{scan_id}").json()["scan"]
    assert scan["source"] == "host"
    signals = scan["crypto_evidence"]["windows_normalized_signals"]
    assert signals["certificates_observed_count"] == 12

    risks = client.get("/risks", params={"scan_id": scan_id}).json()
    assert len(risks) == 1
    assert risks[0]["rating"] == "high"


def test_windows_ingest_is_idempotent_on_asset_but_accumulates_scans(client: TestClient) -> None:
    first = client.post("/scans/ingest/windows", json=_load_fixture()).json()
    second = client.post("/scans/ingest/windows", json=_load_fixture()).json()

    # Same redacted host -> one asset (dedup by name+type), two scan snapshots.
    assert client.get("/assets").json().__len__() == 1
    assert first["scan_id"] != second["scan_id"]
    assert len(client.get("/scans").json()) == 2


def test_windows_ingest_rejects_non_object_document(client: TestClient) -> None:
    response = client.post("/scans/ingest/windows", json=["not", "an", "object"])
    assert response.status_code == 422
