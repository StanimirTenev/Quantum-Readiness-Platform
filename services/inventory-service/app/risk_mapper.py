from __future__ import annotations

from .models import ScanIngestRequest


def build_risk_payload(payload: ScanIngestRequest, asset_name: str, scenario: str = "public_timeline") -> dict:
    target_asset = next((asset for asset in payload.assets if asset.name == asset_name), payload.assets[0])
    criticality = float(target_asset.criticality or 3)
    dependency_count = _dependency_count(target_asset)
    vendor_blocked = _vendor_blocked(target_asset)
    confidentiality_lifetime = _confidentiality_lifetime(payload)
    quantum_exposure = _quantum_exposure(payload)
    blast_radius = _blast_radius(payload)
    vendor_lock_in = _vendor_lock_in(target_asset)
    migration_difficulty = _migration_difficulty(payload)

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


def _confidentiality_lifetime(payload: ScanIngestRequest) -> float:
    if payload.source == "host":
        return 4.0
    if payload.source == "network":
        return 3.0
    return 2.0


def _quantum_exposure(payload: ScanIngestRequest) -> float:
    if payload.tls_evidence:
        cert = payload.tls_evidence.certificate
        if cert.public_key_algorithm.upper() in {"RSA", "ECDSA", "ECDH", "EC"}:
            return 5.0
        return 3.0
    if payload.crypto_evidence and payload.crypto_evidence.openssl_available:
        return 4.0
    return 2.0


def _blast_radius(payload: ScanIngestRequest) -> float:
    if payload.source == "network":
        return 4.0
    if payload.source == "host":
        return 3.0
    return 2.0


def _vendor_lock_in(asset) -> float:
    if asset.vendor:
        return 3.0
    return 1.0


def _dependency_count(asset) -> int:
    if asset.asset_type in {"endpoint", "service"}:
        return 3
    if asset.asset_type in {"server", "pipeline"}:
        return 2
    return 1


def _vendor_blocked(asset) -> bool:
    return bool(asset.vendor)


def _migration_difficulty(payload: ScanIngestRequest) -> float:
    if payload.source == "host":
        return 3.0
    if payload.source == "network":
        return 2.0
    return 2.0
