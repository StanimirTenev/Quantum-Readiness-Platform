import json
import re
from pathlib import Path
from typing import Any, Iterator

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "stage2_evidence"
    / "windows_enriched_ingest_example.json"
)

REQUIRED_NORMALIZED_SIGNAL_KEYS = {
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

ALLOWED_NORMALIZED_SIGNAL_KEYS = REQUIRED_NORMALIZED_SIGNAL_KEYS
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)
FINGERPRINT_RE = re.compile(r"\b[a-f0-9]{32,128}\b", re.IGNORECASE)
PACKAGE_NAME_HINT_RE = re.compile(r"[a-z0-9_.-]+/[a-z0-9_.-]+", re.IGNORECASE)
SECRET_HINT_RE = re.compile(
    r"password|secret|token|private[_-]?key|credential|apikey|api[_-]?key",
    re.IGNORECASE,
)


def _load_windows_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _walk(node: Any) -> Iterator[Any]:
    if isinstance(node, dict):
        for value in node.values():
            yield value
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield item
            yield from _walk(item)


def _build_future_normalized_signals(payload: dict[str, Any]) -> dict[str, Any]:
    asset = payload["asset"]
    evidence = payload["windows_evidence"]

    return {
        "platform": asset["platform"],
        "asset_type": asset["asset_type"],
        "software_total_observed": evidence["installed_software_summary"]["total_observed"],
        "crypto_relevant_software_count": evidence["installed_software_summary"][
            "crypto_relevant_observed"
        ],
        "certificates_observed_count": evidence["certificate_store_indicators"][
            "certificates_observed_count"
        ],
        "expired_certificates_count": evidence["certificate_store_indicators"][
            "expired_certificates_count"
        ],
        "weak_signature_indicators_count": evidence["certificate_store_indicators"][
            "weak_signature_indicators_count"
        ],
        "crypto_relevant_services_count": evidence["windows_service_indicators"][
            "crypto_relevant_services_observed"
        ],
        "domain_joined": evidence["domain_membership_indicators"]["domain_joined"],
        "ad_details_collected": evidence["domain_membership_indicators"][
            "ad_details_collected"
        ],
        "domain_controller_role_observed": evidence["machine_role_indicators"][
            "domain_controller_role_observed"
        ],
        "private_keys_exported": evidence["certificate_store_indicators"][
            "private_keys_exported"
        ],
        "warnings_count": len(evidence["warnings"]),
        "errors_count": len(evidence["errors"]),
    }


def test_future_windows_normalized_signal_builder_contract_outputs_required_aggregate_keys_only() -> None:
    normalized_signals = _build_future_normalized_signals(_load_windows_fixture())

    assert set(normalized_signals) == REQUIRED_NORMALIZED_SIGNAL_KEYS
    assert set(normalized_signals).issubset(ALLOWED_NORMALIZED_SIGNAL_KEYS)


def test_future_windows_normalized_signal_builder_contract_enforces_expected_types_and_platform() -> None:
    normalized_signals = _build_future_normalized_signals(_load_windows_fixture())

    integer_keys = {
        "software_total_observed",
        "crypto_relevant_software_count",
        "certificates_observed_count",
        "expired_certificates_count",
        "weak_signature_indicators_count",
        "crypto_relevant_services_count",
        "warnings_count",
        "errors_count",
    }
    boolean_keys = {
        "domain_joined",
        "ad_details_collected",
        "domain_controller_role_observed",
        "private_keys_exported",
    }

    assert normalized_signals["platform"] == "windows"
    assert isinstance(normalized_signals["asset_type"], str)

    for key in integer_keys:
        assert isinstance(normalized_signals[key], int), f"{key} must be an integer"

    for key in boolean_keys:
        assert isinstance(normalized_signals[key], bool), f"{key} must be a boolean"


def test_future_windows_normalized_signal_builder_contract_excludes_raw_identifiers_and_sensitive_material() -> None:
    normalized_signals = _build_future_normalized_signals(_load_windows_fixture())

    disallowed_exact_values = {
        "redacted-windows-host",
        "LocalMachine\\My",
        "LocalMachine\\Root",
    }

    for value in _walk(normalized_signals):
        if not isinstance(value, str):
            continue

        lowered = value.lower()
        assert value not in disallowed_exact_values
        assert IPV4_RE.search(value) is None
        assert DOMAIN_RE.search(value) is None
        assert PACKAGE_NAME_HINT_RE.search(value) is None
        assert FINGERPRINT_RE.search(value) is None
        assert SECRET_HINT_RE.search(lowered) is None


def test_future_windows_normalized_signal_builder_contract_is_downstream_safe_aggregate_input() -> None:
    payload = _load_windows_fixture()
    normalized_signals = _build_future_normalized_signals(payload)

    assert normalized_signals["ad_details_collected"] is False
    assert normalized_signals["private_keys_exported"] is False

    raw_windows_detail_keys = {
        "stores_observed",
        "service_names",
        "certificate_fingerprints",
        "domain_name",
        "schannel_tls_indicators",
        "os_metadata",
    }
    assert not (set(normalized_signals) & raw_windows_detail_keys)

    assert payload["windows_evidence"]["domain_membership_indicators"]["ad_details_collected"] is False
