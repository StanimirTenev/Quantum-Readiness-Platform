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

REQUIRED_WINDOWS_EVIDENCE_SECTIONS = {
    "os_metadata",
    "installed_software_summary",
    "certificate_store_indicators",
    "windows_service_indicators",
    "domain_membership_indicators",
    "machine_role_indicators",
    "warnings",
    "errors",
}

FORBIDDEN_KEYS = {
    "password",
    "secret",
    "token",
    "credential",
    "private_key",
    "private_keys",
    "key_material",
    "ntlm",
    "kerberos_ticket",
    "user_profile",
    "username",
    "hostname",
    "fqdn",
    "ip",
    "ip_address",
    "package_names",
    "service_names",
    "certificate_fingerprint",
    "thumbprint",
}

SAFE_DOMAIN_VALUES = {"redacted.example", "example.invalid"}
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOMAIN_LIKE_RE = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\b", re.IGNORECASE)
PEM_MARKER_RE = re.compile(r"-----BEGIN [A-Z0-9 ]+-----|-----END [A-Z0-9 ]+-----")
WINDOWS_USER_PATH_RE = re.compile(r"[A-Za-z]:\\Users\\")


def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _walk(node: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    if isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}"
            yield child_path, value
            yield from _walk(value, child_path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child_path = f"{path}[{index}]"
            yield child_path, value
            yield from _walk(value, child_path)


def _build_safe_normalized_summary(payload: dict[str, Any]) -> dict[str, Any]:
    asset = payload["asset"]
    evidence = payload["windows_evidence"]

    installed = evidence["installed_software_summary"]
    certs = evidence["certificate_store_indicators"]
    services = evidence["windows_service_indicators"]
    domain = evidence["domain_membership_indicators"]
    roles = evidence["machine_role_indicators"]

    return {
        "platform": asset["platform"],
        "asset_type": asset["asset_type"],
        "software_total_observed": installed["total_observed"],
        "crypto_relevant_software_count": installed.get(
            "crypto_relevant_count", installed.get("crypto_relevant_observed", 0)
        ),
        "certificates_observed_count": certs["certificates_observed_count"],
        "expired_certificates_count": certs.get("expired_certificates_count", 0),
        "weak_signature_indicators_count": certs.get("weak_signature_indicators_count", 0),
        "crypto_relevant_services_count": services.get(
            "crypto_relevant_services_count",
            services.get("crypto_relevant_services_observed", 0),
        ),
        "domain_joined": domain["domain_joined"],
        "ad_details_collected": domain["ad_details_collected"],
        "domain_controller_role_observed": roles["domain_controller_role_observed"],
        "private_keys_exported": certs["private_keys_exported"],
        "warnings_count": len(evidence["warnings"]),
        "errors_count": len(evidence["errors"]),
    }


def test_windows_inventory_schema_required_top_level_shape_and_asset_contract() -> None:
    payload = _load_fixture()

    assert set(("asset", "windows_evidence")).issubset(payload)

    asset = payload["asset"]
    assert isinstance(asset.get("asset_id"), str) and asset["asset_id"].strip()
    assert isinstance(asset.get("asset_type"), str) and asset["asset_type"].strip()
    assert asset.get("platform") == "windows"


def test_windows_inventory_schema_required_evidence_sections_and_basic_types() -> None:
    evidence = _load_fixture()["windows_evidence"]

    assert REQUIRED_WINDOWS_EVIDENCE_SECTIONS.issubset(evidence)
    assert isinstance(evidence["warnings"], list)
    assert isinstance(evidence["errors"], list)
    assert all(isinstance(item, str) for item in evidence["warnings"])
    assert all(isinstance(item, str) for item in evidence["errors"])


def test_windows_inventory_schema_os_metadata_aggregate_only_constraints() -> None:
    os_metadata = _load_fixture()["windows_evidence"]["os_metadata"]

    assert isinstance(os_metadata, dict)
    assert "hostname" not in os_metadata
    assert "user_profile" not in os_metadata
    assert "username" not in os_metadata
    assert "product_name" in os_metadata or "family" in os_metadata


def test_windows_inventory_schema_software_summary_contract_and_redaction() -> None:
    software = _load_fixture()["windows_evidence"]["installed_software_summary"]

    assert isinstance(software["total_observed"], int)
    if "crypto_relevant_count" in software:
        assert isinstance(software["crypto_relevant_count"], int)
    assert software.get("package_names_redacted") is True
    assert "package_names" not in software


def test_windows_inventory_schema_certificate_service_domain_role_contracts() -> None:
    evidence = _load_fixture()["windows_evidence"]
    certs = evidence["certificate_store_indicators"]
    services = evidence["windows_service_indicators"]
    domain = evidence["domain_membership_indicators"]
    roles = evidence["machine_role_indicators"]

    assert isinstance(certs["certificates_observed_count"], int)
    if "expired_certificates_count" in certs:
        assert isinstance(certs["expired_certificates_count"], int)
    if "weak_signature_indicators_count" in certs:
        assert isinstance(certs["weak_signature_indicators_count"], int)
    assert certs["private_keys_exported"] is False
    assert "certificate_fingerprint" not in certs
    assert "thumbprint" not in certs

    if "crypto_relevant_services_count" in services:
        assert isinstance(services["crypto_relevant_services_count"], int)
    if "service_names" in services:
        assert services.get("service_names_redacted") is True
    assert "service_names" not in services

    assert isinstance(domain["domain_joined"], bool)
    if domain["domain_joined"]:
        assert domain.get("domain_name_redacted") is True
    assert domain["ad_details_collected"] is False
    assert "domain_name" not in domain

    assert isinstance(roles["domain_controller_role_observed"], bool)
    if "role_details" in roles:
        assert roles.get("role_details_redacted") is True


def test_windows_inventory_schema_recursive_forbidden_key_and_heuristic_value_scan() -> None:
    payload = _load_fixture()

    forbidden_key_hits: list[str] = []
    ipv4_hits: list[tuple[str, str]] = []
    domain_hits: list[tuple[str, str]] = []
    pem_hits: list[tuple[str, str]] = []
    windows_user_path_hits: list[tuple[str, str]] = []

    for path, value in _walk(payload):
        key = path.split(".")[-1].lower().strip("[]0123456789")
        if key in FORBIDDEN_KEYS:
            forbidden_key_hits.append(path)

        if not isinstance(value, str):
            continue

        for match in IPV4_RE.findall(value):
            octets = [int(part) for part in match.split(".")]
            if all(0 <= octet <= 255 for octet in octets):
                ipv4_hits.append((path, value))

        for match in DOMAIN_LIKE_RE.findall(value):
            lowered = match.lower()
            if lowered not in SAFE_DOMAIN_VALUES:
                domain_hits.append((path, value))

        if PEM_MARKER_RE.search(value):
            pem_hits.append((path, value))

        if WINDOWS_USER_PATH_RE.search(value):
            windows_user_path_hits.append((path, value))

    assert not forbidden_key_hits
    assert not ipv4_hits
    assert not domain_hits
    assert not pem_hits
    assert not windows_user_path_hits


def test_windows_inventory_schema_future_safe_normalized_summary_aggregate_only() -> None:
    summary = _build_safe_normalized_summary(_load_fixture())

    expected_keys = {
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
    assert set(summary) == expected_keys

    assert summary["platform"] == "windows"
    assert isinstance(summary["asset_type"], str)

    for key in expected_keys - {"platform", "asset_type", "domain_joined", "ad_details_collected", "domain_controller_role_observed", "private_keys_exported"}:
        assert isinstance(summary[key], int), f"{key} must be int"

    for key in {"domain_joined", "ad_details_collected", "domain_controller_role_observed", "private_keys_exported"}:
        assert isinstance(summary[key], bool), f"{key} must be bool"

    disallowed_raw_detail_keys = {
        "package_names",
        "service_names",
        "certificate_fingerprint",
        "thumbprint",
        "domain_name",
        "stores_observed",
        "os_metadata",
    }
    assert not (set(summary) & disallowed_raw_detail_keys)
