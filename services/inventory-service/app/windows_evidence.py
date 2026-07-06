"""Adapter: Windows host evidence document -> persistable inventory ingest.

The Windows host agent (`agents/windows-host-agent/collect.ps1`) emits a
redacted, aggregate evidence document (see
`docs/windows-evidence-fixture-contract.md`). This module turns that document
into two things:

* `build_windows_normalized_signals` — the canonical aggregate-only signal set
  (the shape the `test_windows_normalized_signal_contract` spec pins down). It
  is the single production source of truth for "what safe numbers may flow
  downstream into risk/planning".
* `build_ingest_request` — a `ScanIngestRequest` so real host evidence can be
  persisted through the same `/scans/ingest` path (scan snapshot + asset +
  auto-scored risk), turning a one-off collection into durable inventory.

Only aggregates and per-certificate crypto surface (algorithm/size, no
subjects, no thumbprints, no private material) ever leave this adapter.
"""

from __future__ import annotations

from typing import Any, get_args

from .models import (
    AssetCreate,
    AssetType,
    CryptoEvidence,
    HostInventory,
    ScanIngestRequest,
    TLSEvidence,
    TLSEvidenceCertificate,
)

_VALID_ASSET_TYPES = set(get_args(AssetType))

# Public-key algorithms that a cryptographically-relevant quantum adversary
# breaks outright (Shor). Kept aligned with risk_mapper._quantum_exposure.
_QUANTUM_VULNERABLE_PK = ("RSA", "EC", "DSA", "DH")


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _as_bool(value: Any) -> bool:
    return value is True


def build_windows_normalized_signals(document: dict[str, Any]) -> dict[str, Any]:
    """Aggregate-only signal set derived from a Windows evidence document.

    Defensive by construction: missing or malformed blocks collapse to safe
    zero/false defaults rather than raising, so a partial collection still
    yields a usable, downstream-safe signal set.
    """
    asset = _as_dict(document.get("asset"))
    evidence = _as_dict(document.get("windows_evidence"))

    software = _as_dict(evidence.get("installed_software_summary"))
    certs = _as_dict(evidence.get("certificate_store_indicators"))
    services = _as_dict(evidence.get("windows_service_indicators"))
    domain = _as_dict(evidence.get("domain_membership_indicators"))
    role = _as_dict(evidence.get("machine_role_indicators"))
    warnings = evidence.get("warnings")
    errors = evidence.get("errors")

    return {
        "platform": asset.get("platform") or "windows",
        "asset_type": asset.get("asset_type") or "endpoint",
        "software_total_observed": _as_int(software.get("total_observed")),
        "crypto_relevant_software_count": _as_int(software.get("crypto_relevant_observed")),
        "certificates_observed_count": _as_int(certs.get("certificates_observed_count")),
        "expired_certificates_count": _as_int(certs.get("expired_certificates_count")),
        "weak_signature_indicators_count": _as_int(certs.get("weak_signature_indicators_count")),
        "crypto_relevant_services_count": _as_int(services.get("crypto_relevant_services_observed")),
        "domain_joined": _as_bool(domain.get("domain_joined")),
        "ad_details_collected": _as_bool(domain.get("ad_details_collected")),
        "domain_controller_role_observed": _as_bool(role.get("domain_controller_role_observed")),
        "private_keys_exported": _as_bool(certs.get("private_keys_exported")),
        "warnings_count": len(warnings) if isinstance(warnings, list) else 0,
        "errors_count": len(errors) if isinstance(errors, list) else 0,
    }


def _asset_type(raw: Any) -> AssetType:
    value = raw if isinstance(raw, str) else ""
    return value if value in _VALID_ASSET_TYPES else "other"  # type: ignore[return-value]


def _criticality(signals: dict[str, Any]) -> int:
    """Coarse 1-5 criticality from role/domain aggregates (no raw identity)."""
    if signals["domain_controller_role_observed"]:
        return 5
    if signals["asset_type"] == "server":
        return 4
    if signals["domain_joined"]:
        return 3
    return 2


def _representative_certificate(document: dict[str, Any]) -> TLSEvidenceCertificate | None:
    """Pick the most quantum-relevant cert from the safe crypto surface.

    Prefers a quantum-vulnerable public key (RSA/EC/DSA/DH) so the persisted
    scan drives a realistic risk score; falls back to the first cert. Only
    algorithm/size fields are carried — never subjects or thumbprints.
    """
    surface = document.get("certificate_crypto_surface")
    if not isinstance(surface, list):
        return None
    candidates = [c for c in surface if isinstance(c, dict) and c.get("public_key_algorithm")]
    if not candidates:
        return None

    def _is_vulnerable(cert: dict[str, Any]) -> bool:
        return _normalize_pk_algorithm(cert.get("public_key_algorithm")) in _QUANTUM_VULNERABLE_PK

    chosen = next((c for c in candidates if _is_vulnerable(c)), candidates[0])
    return TLSEvidenceCertificate(
        signature_algorithm=chosen.get("signature_algorithm"),
        public_key_algorithm=_normalize_pk_algorithm(chosen.get("public_key_algorithm")),
        not_after=chosen.get("not_after"),
    )


def _normalize_pk_algorithm(raw: Any) -> str | None:
    """Map Windows friendly names (RSA, ECC, ECDSA, ...) to risk_mapper's vocab."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    upper = raw.strip().upper()
    if "RSA" in upper:
        return "RSA"
    if upper.startswith("EC"):  # ECC / ECDSA / ECDH friendly names
        return "EC"
    if "DSA" in upper:
        return "DSA"
    if upper in {"DH", "DIFFIE-HELLMAN"}:
        return "DH"
    return upper


def build_ingest_request(document: dict[str, Any]) -> ScanIngestRequest:
    """Map a Windows evidence document to a persistable, scorable ingest request.

    The resulting request keeps the aggregate signal set on `crypto_evidence`
    (under `windows_normalized_signals`, allowed by the model's extra="allow")
    so the persisted scan snapshot carries the full downstream-safe context.
    """
    asset = _as_dict(document.get("asset"))
    evidence = _as_dict(document.get("windows_evidence"))
    os_metadata = _as_dict(evidence.get("os_metadata"))
    signals = build_windows_normalized_signals(document)

    asset_name = asset.get("name") if isinstance(asset.get("name"), str) and asset.get("name") else "redacted-windows-host"
    version_family = os_metadata.get("version_family")

    ingest_asset = AssetCreate(
        asset_type=_asset_type(signals["asset_type"]),
        name=asset_name,
        environment=version_family[:50] if isinstance(version_family, str) else "windows",
        criticality=_criticality(signals),
    )

    host_inventory = HostInventory(
        os=version_family if isinstance(version_family, str) else "windows",
        architecture=os_metadata.get("architecture"),
    )

    crypto_evidence = CryptoEvidence(
        openssl_available=signals["crypto_relevant_software_count"] > 0,
        windows_normalized_signals=signals,
    )

    tls_evidence: TLSEvidence | None = None
    certificate = _representative_certificate(document)
    if certificate is not None:
        tls_evidence = TLSEvidence(certificate=certificate)

    return ScanIngestRequest(
        source="host",
        assets=[ingest_asset],
        host_inventory=host_inventory,
        crypto_evidence=crypto_evidence,
        tls_evidence=tls_evidence,
    )
