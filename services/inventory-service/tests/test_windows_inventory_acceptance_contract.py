import json
from pathlib import Path

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "stage2_evidence"
    / "windows_enriched_ingest_example.json"
)

ALLOWED_NORMALIZED_SIGNAL_KEYS = {
    "platform",
    "asset_type",
    "evidence_family",
    "collector_type",
    "software_inventory_total_observed",
    "certificate_store_certificates_observed_count",
    "domain_membership_domain_joined",
}


def _load_windows_contract_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_future_normalized_signals(payload: dict) -> dict:
    asset = payload["asset"]
    evidence = payload["windows_evidence"]
    signals = {
        "platform": asset["platform"],
        "asset_type": asset["asset_type"],
        "software_inventory_total_observed": evidence["installed_software_summary"][
            "total_observed"
        ],
        "certificate_store_certificates_observed_count": evidence[
            "certificate_store_indicators"
        ]["certificates_observed_count"],
        "domain_membership_domain_joined": evidence["domain_membership_indicators"][
            "domain_joined"
        ],
    }
    if "evidence_family" in payload:
        signals["evidence_family"] = payload["evidence_family"]
    if "collector_type" in payload:
        signals["collector_type"] = payload["collector_type"]
    return signals


def test_future_windows_inventory_acceptance_contract_can_be_interpreted_as_normalized_evidence() -> None:
    payload = _load_windows_contract_fixture()

    assert isinstance(payload, dict)
    assert isinstance(payload.get("asset"), dict)
    assert isinstance(payload.get("windows_evidence"), dict)


def test_future_windows_inventory_acceptance_contract_has_required_windows_sections() -> None:
    payload = _load_windows_contract_fixture()
    asset = payload["asset"]
    evidence = payload["windows_evidence"]

    assert asset["asset_id"]
    assert asset["asset_type"]
    assert asset["platform"] == "windows"

    assert isinstance(evidence["os_metadata"], dict)
    assert isinstance(evidence["installed_software_summary"], dict)
    assert isinstance(evidence["certificate_store_indicators"], dict)
    assert isinstance(evidence["windows_service_indicators"], dict)
    assert isinstance(evidence["domain_membership_indicators"], dict)
    assert isinstance(evidence["machine_role_indicators"], dict)


def test_future_windows_inventory_acceptance_contract_defines_expected_normalized_summary_fields() -> None:
    payload = _load_windows_contract_fixture()
    asset = payload["asset"]
    evidence = payload["windows_evidence"]

    assert asset["platform"] == "windows"
    assert isinstance(asset["asset_type"], str)

    assert "evidence_family" not in payload
    assert "collector_type" not in payload

    assert isinstance(evidence["installed_software_summary"]["total_observed"], int)
    assert isinstance(
        evidence["certificate_store_indicators"]["certificates_observed_count"], int
    )
    assert isinstance(evidence["domain_membership_indicators"]["domain_joined"], bool)


def test_future_windows_inventory_acceptance_contract_enforces_safety_invariants() -> None:
    evidence = _load_windows_contract_fixture()["windows_evidence"]

    assert evidence["installed_software_summary"]["package_names_redacted"] is True
    assert evidence["certificate_store_indicators"]["private_keys_exported"] is False
    assert evidence["domain_membership_indicators"]["domain_name_redacted"] is True
    assert evidence["domain_membership_indicators"]["ad_details_collected"] is False


def test_future_windows_inventory_acceptance_contract_limits_risk_and_planning_inputs_to_aggregates() -> None:
    payload = _load_windows_contract_fixture()
    normalized_signals = _build_future_normalized_signals(payload)

    assert set(normalized_signals).issubset(ALLOWED_NORMALIZED_SIGNAL_KEYS)
    assert normalized_signals["platform"] == "windows"
    assert isinstance(normalized_signals["software_inventory_total_observed"], int)
    assert isinstance(
        normalized_signals["certificate_store_certificates_observed_count"], int
    )
    assert isinstance(normalized_signals["domain_membership_domain_joined"], bool)

    disallowed_raw_windows_keys = {
        "stores_observed",
        "service_names",
        "certificate_fingerprints",
        "domain_name",
    }
    assert not (set(normalized_signals) & disallowed_raw_windows_keys)
