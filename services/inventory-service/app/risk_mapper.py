from __future__ import annotations

from typing import Any, Optional

from .models import ScanIngestRequest

# Risk-engine factors are all constrained to [0, 5]; keep derived values in range.
_MAX_FACTOR = 5.0


def build_risk_payload(payload: ScanIngestRequest, asset_name: str, scenario: str = "public_timeline") -> dict:
    target_asset = next((asset for asset in payload.assets if asset.name == asset_name), payload.assets[0])
    windows_signals = _windows_signals(payload)

    criticality = float(target_asset.criticality or 3)
    dependency_count = _dependency_count(target_asset, windows_signals)
    vendor_blocked = _vendor_blocked(target_asset)
    confidentiality_lifetime = _confidentiality_lifetime(payload)
    quantum_exposure = _quantum_exposure(payload)
    blast_radius = _blast_radius(payload, windows_signals)
    vendor_lock_in = _vendor_lock_in(target_asset)
    migration_difficulty = _migration_difficulty(payload, windows_signals)

    return {
        "contract_version": "stage1-v1",
        "asset_name": asset_name,
        "criticality": criticality,
        "confidentiality_lifetime": confidentiality_lifetime,
        "quantum_exposure": quantum_exposure,
        "blast_radius": blast_radius,
        "vendor_lock_in": vendor_lock_in,
        "migration_difficulty": migration_difficulty,
        "dependency_count": dependency_count,
        "vendor_blocked": vendor_blocked,
        "scenario": scenario,
    }


def _windows_signals(payload: ScanIngestRequest) -> Optional[dict[str, Any]]:
    """Return the persisted Windows aggregate signals, if this scan carries them.

    The Windows ingest adapter stores them on crypto_evidence (extra field)
    under `windows_normalized_signals`; non-Windows scans return None and keep
    the original generic scoring behavior."""
    crypto_evidence = payload.crypto_evidence
    if crypto_evidence is None:
        return None
    signals = (crypto_evidence.model_extra or {}).get("windows_normalized_signals")
    return signals if isinstance(signals, dict) else None


def _signal_int(signals: dict[str, Any], key: str) -> int:
    value = signals.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _confidentiality_lifetime(payload: ScanIngestRequest) -> float:
    if payload.source == "host":
        return 4.0
    if payload.source == "network":
        return 3.0
    return 2.0


def _quantum_exposure(payload: ScanIngestRequest) -> float:
    if payload.tls_evidence and payload.tls_evidence.certificate:
        cert = payload.tls_evidence.certificate
        public_key_algorithm = (cert.public_key_algorithm or "").upper()
        if public_key_algorithm in {"RSA", "ECDSA", "ECDH", "EC"}:
            return 5.0
        return 3.0
    if payload.crypto_evidence and payload.crypto_evidence.openssl_available:
        return 4.0
    return 2.0


def _blast_radius(payload: ScanIngestRequest, windows_signals: Optional[dict[str, Any]]) -> float:
    if payload.source == "network":
        base = 4.0
    elif payload.source == "host":
        base = 3.0
    else:
        base = 2.0

    if windows_signals:
        # A domain controller is the trust anchor for the whole domain; a
        # domain-joined host still has a wider blast radius than a standalone one.
        if windows_signals.get("domain_controller_role_observed") is True:
            return _MAX_FACTOR
        if windows_signals.get("domain_joined") is True:
            base = max(base, 4.0)

    return min(base, _MAX_FACTOR)


def _vendor_lock_in(asset) -> float:
    if asset.vendor:
        return 3.0
    return 1.0


def _dependency_count(asset, windows_signals: Optional[dict[str, Any]]) -> int:
    if asset.asset_type in {"endpoint", "service"}:
        base = 3
    elif asset.asset_type in {"server", "pipeline"}:
        base = 2
    else:
        base = 1

    if windows_signals:
        if windows_signals.get("domain_controller_role_observed") is True:
            base += 2
        elif windows_signals.get("domain_joined") is True:
            base += 1

    return base


def _vendor_blocked(asset) -> bool:
    return bool(asset.vendor)


def _migration_difficulty(payload: ScanIngestRequest, windows_signals: Optional[dict[str, Any]]) -> float:
    if payload.source == "host":
        base = 3.0
    elif payload.source == "network":
        base = 2.0
    else:
        base = 2.0

    if windows_signals:
        # More certificates in the store means more crypto to migrate; weak or
        # expired certificates add remediation burden on top of that.
        certificates = _signal_int(windows_signals, "certificates_observed_count")
        if certificates >= 50:
            base += 2.0
        elif certificates >= 10:
            base += 1.0

        weak = _signal_int(windows_signals, "weak_signature_indicators_count")
        expired = _signal_int(windows_signals, "expired_certificates_count")
        if weak > 0 or expired > 0:
            base += 1.0

    return min(base, _MAX_FACTOR)
