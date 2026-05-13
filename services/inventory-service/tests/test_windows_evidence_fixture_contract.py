import json
import re
from pathlib import Path
from typing import Iterator

FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "stage2_evidence"
    / "windows_enriched_ingest_example.json"
)

FORBIDDEN_KEYS = {
    "password",
    "secret",
    "token",
    "private_key",
    "privateKey",
    "credential",
    "credentials",
    "raw_hostname",
    "raw_domain",
    "raw_ip",
    "certificate_private_material",
}

SAFE_DOMAIN_TOKENS = {
    "redacted",
    "example",
    "example.com",
    "example.org",
    "example.net",
    "local",
    "localhost",
    "internal",
}

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.IGNORECASE)


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _walk(node: object) -> Iterator[tuple[str | None, object]]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield key, value
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield None, item
            yield from _walk(item)


def test_windows_contract_fixture_file_exists() -> None:
    assert FIXTURE_PATH.exists(), "Contract fixture must exist for docs/fixture validation"


def test_windows_contract_fixture_is_valid_json() -> None:
    assert isinstance(_load_fixture(), dict)


def test_windows_contract_fixture_has_required_top_level_sections() -> None:
    payload = _load_fixture()
    assert "asset" in payload
    assert "windows_evidence" in payload


def test_windows_contract_asset_declares_windows_platform_and_redaction() -> None:
    asset = _load_fixture()["asset"]
    assert asset["platform"] == "windows"
    assert asset["hostname_redacted"] is True


def test_windows_contract_windows_evidence_has_expected_sections() -> None:
    evidence = _load_fixture()["windows_evidence"]
    expected = {
        "os_metadata",
        "installed_software_summary",
        "certificate_store_indicators",
        "windows_service_indicators",
        "domain_membership_indicators",
        "machine_role_indicators",
        "warnings",
        "errors",
    }
    assert expected.issubset(evidence.keys())


def test_windows_contract_redaction_and_private_key_export_safety_flags() -> None:
    evidence = _load_fixture()["windows_evidence"]
    assert evidence["installed_software_summary"]["package_names_redacted"] is True
    assert evidence["certificate_store_indicators"]["private_keys_exported"] is False
    assert evidence["domain_membership_indicators"]["domain_name_redacted"] is True


def test_windows_contract_contains_no_forbidden_sensitive_keys_anywhere() -> None:
    payload = _load_fixture()
    found = {key for key, _ in _walk(payload) if key in FORBIDDEN_KEYS}
    assert not found, f"Forbidden keys found in contract fixture: {sorted(found)}"


def test_windows_contract_contains_no_obvious_raw_ip_values() -> None:
    payload = _load_fixture()
    matches: list[str] = []
    for _, value in _walk(payload):
        if isinstance(value, str):
            for match in IPV4_RE.findall(value):
                octets = [int(part) for part in match.split(".")]
                if all(0 <= octet <= 255 for octet in octets):
                    matches.append(match)
    assert not matches, f"Fixture should not contain raw IP values: {matches}"


def test_windows_contract_contains_no_non_placeholder_domain_like_values() -> None:
    payload = _load_fixture()
    domains: list[str] = []
    for _, value in _walk(payload):
        if not isinstance(value, str):
            continue
        for match in DOMAIN_RE.finditer(value):
            domain = match.group(0)
            lowered = domain.lower()
            if all(token not in lowered for token in SAFE_DOMAIN_TOKENS):
                domains.append(domain)
    assert not domains, f"Fixture should not contain real domain-like values: {domains}"


def test_windows_contract_warnings_and_errors_are_arrays() -> None:
    evidence = _load_fixture()["windows_evidence"]
    assert isinstance(evidence["warnings"], list)
    assert isinstance(evidence["errors"], list)
