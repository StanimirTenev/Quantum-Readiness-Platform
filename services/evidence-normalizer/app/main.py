from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import AliasChoices, BaseModel, Field

app = FastAPI(title="Evidence Normalizer", version="0.1.0")

CONTRACT_VERSION = "evn-v1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clean_str(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _safe_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _dn(value: Any) -> str | None:
    """Accept either a plain DN string or a Stage 2 {display_dn: ...} object."""
    if isinstance(value, dict):
        return _clean_str(value.get("display_dn"))
    return _clean_str(value)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class NormalizeRequest(BaseModel):
    source: str = "manual"
    assets: list[dict[str, Any]] = Field(default_factory=list)
    host_inventory: dict[str, Any] | None = None
    crypto_evidence: dict[str, Any] | None = None
    tls_evidence: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("tls_evidence", "tls_metadata"),
    )


class NormalizedCertificate(BaseModel):
    subject: str | None = None
    issuer: str | None = None
    not_before: str | None = None
    not_after: str | None = None
    signature_algorithm: str | None = None
    public_key_algorithm: str | None = None
    public_key_size: int | None = None
    dns_names: list[str] = Field(default_factory=list)
    fingerprint_sha256: str | None = None


class NormalizedCertificateChain(BaseModel):
    available: bool = False
    length: int = 0
    fingerprints: list[str] = Field(default_factory=list)


class NormalizedNetworkEvidence(BaseModel):
    collected: bool = False
    target: str | None = None
    server_name: str | None = None
    port: int | None = None
    tls_version: str | None = None
    cipher_suite: str | None = None
    certificate: NormalizedCertificate | None = None
    certificate_chain: NormalizedCertificateChain | None = None


class NormalizedPackage(BaseModel):
    name: str
    version: str | None = None
    package_manager: str | None = None


class NormalizedHostEvidence(BaseModel):
    hostname: str | None = None
    os: str | None = None
    package_manager: str | None = None
    packages: list[NormalizedPackage] = Field(default_factory=list)
    certificate_files: list[str] = Field(default_factory=list)
    config_files: list[str] = Field(default_factory=list)
    private_key_indicator: bool = False


class NormalizedAsset(BaseModel):
    asset_type: str | None = None
    name: str | None = None
    owner: str | None = None
    criticality: int | None = None
    environment: str | None = None
    vendor: str | None = None
    lifecycle_years: int | None = None


class NormalizeResponse(BaseModel):
    contract_version: str
    source: str
    assets: list[NormalizedAsset]
    host_evidence: NormalizedHostEvidence | None = None
    network_evidence: NormalizedNetworkEvidence | None = None
    warnings: list[str]


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------
def _normalize_asset(raw: dict[str, Any], warnings: list[str], index: int) -> NormalizedAsset:
    name = _clean_str(raw.get("name"))
    if name is None:
        warnings.append(f"assets[{index}]: missing name")
    criticality = raw.get("criticality")
    if criticality is not None and _safe_int(criticality) is None:
        warnings.append(f"assets[{index}]: non-integer criticality dropped")
    return NormalizedAsset(
        asset_type=_clean_str(raw.get("asset_type")),
        name=name,
        owner=_clean_str(raw.get("owner")),
        criticality=_safe_int(criticality),
        environment=_clean_str(raw.get("environment")),
        vendor=_clean_str(raw.get("vendor")),
        lifecycle_years=_safe_int(raw.get("lifecycle_years")),
    )


def _normalize_certificate(raw: dict[str, Any], warnings: list[str]) -> NormalizedCertificate:
    algorithms = raw.get("algorithms")
    if isinstance(algorithms, dict):
        signature = _clean_str(algorithms.get("signature"))
        public_key = _clean_str(algorithms.get("public_key"))
        warnings.append("certificate.algorithms: normalized from stage2 nested object")
    else:
        signature = _clean_str(raw.get("signature_algorithm"))
        public_key = _clean_str(raw.get("public_key_algorithm"))

    validity = raw.get("validity")
    if isinstance(validity, dict):
        not_before = _clean_str(validity.get("not_before"))
        not_after = _clean_str(validity.get("not_after"))
    else:
        not_before = _clean_str(raw.get("not_before"))
        not_after = _clean_str(raw.get("not_after"))

    key = raw.get("key")
    if isinstance(key, dict) and key.get("size_bits") is not None:
        public_key_size = _safe_int(key.get("size_bits"))
    else:
        public_key_size = _safe_int(raw.get("public_key_size"))

    san = raw.get("san")
    if isinstance(san, dict):
        dns_source = san.get("dns_names")
    else:
        dns_source = raw.get("dns_names")
    dns_names = [d for d in (_clean_str(x) for x in dns_source) if d] if isinstance(dns_source, list) else []

    fingerprint = _clean_str(raw.get("fingerprint_sha256")) or _clean_str(raw.get("sha256_fingerprint"))

    return NormalizedCertificate(
        subject=_dn(raw.get("subject")),
        issuer=_dn(raw.get("issuer")),
        not_before=not_before,
        not_after=not_after,
        signature_algorithm=signature,
        public_key_algorithm=public_key,
        public_key_size=public_key_size,
        dns_names=dns_names,
        fingerprint_sha256=fingerprint,
    )


def _normalize_chain(raw: dict[str, Any]) -> NormalizedCertificateChain:
    certificates = raw.get("certificates")
    fingerprints: list[str] = []
    if isinstance(certificates, list):
        for cert in certificates:
            if isinstance(cert, dict):
                fp = _clean_str(cert.get("sha256_fingerprint")) or _clean_str(cert.get("fingerprint_sha256"))
                if fp:
                    fingerprints.append(fp)
    length = _safe_int(raw.get("length"))
    return NormalizedCertificateChain(
        available=bool(raw.get("available") is True),
        length=length if length is not None else len(fingerprints),
        fingerprints=fingerprints,
    )


def _normalize_network(tls: dict[str, Any], warnings: list[str]) -> NormalizedNetworkEvidence:
    certificate = tls.get("certificate")
    normalized_cert = (
        _normalize_certificate(certificate, warnings) if isinstance(certificate, dict) else None
    )
    if normalized_cert is None:
        warnings.append("tls_evidence: no certificate block present")

    chain = tls.get("certificate_chain")
    normalized_chain = _normalize_chain(chain) if isinstance(chain, dict) else None

    port = tls.get("port")
    if port is not None and _safe_int(port) is None:
        warnings.append("tls_evidence.port: non-integer dropped")

    return NormalizedNetworkEvidence(
        collected=bool(tls.get("collected") is True),
        target=_clean_str(tls.get("target")),
        server_name=_clean_str(tls.get("server_name")),
        port=_safe_int(port),
        tls_version=_clean_str(tls.get("tls_version")) or _clean_str(tls.get("protocol_version")),
        cipher_suite=_clean_str(tls.get("cipher_suite")),
        certificate=normalized_cert,
        certificate_chain=normalized_chain,
    )


def _indicator_paths(indicators: dict[str, Any], key: str) -> list[str]:
    block = indicators.get(key)
    if not isinstance(block, dict):
        return []
    files = block.get("files")
    if not isinstance(files, list):
        return []
    paths: list[str] = []
    for entry in files:
        if isinstance(entry, dict):
            path = _clean_str(entry.get("path"))
            if path:
                paths.append(path)
    return paths


def _normalize_host(
    crypto_evidence: dict[str, Any], host_inventory: dict[str, Any] | None, warnings: list[str]
) -> NormalizedHostEvidence:
    package_metadata = crypto_evidence.get("package_metadata")
    package_manager = None
    packages: list[NormalizedPackage] = []
    if isinstance(package_metadata, dict):
        package_manager = _clean_str(package_metadata.get("package_manager"))
        raw_packages = package_metadata.get("packages")
        if isinstance(raw_packages, list):
            for entry in raw_packages:
                if isinstance(entry, dict):
                    name = _clean_str(entry.get("name"))
                    if name:
                        packages.append(
                            NormalizedPackage(
                                name=name,
                                version=_clean_str(entry.get("version")),
                                package_manager=package_manager,
                            )
                        )

    cert_indicators = crypto_evidence.get("cert_indicators")
    certificate_files: list[str] = []
    config_files: list[str] = []
    private_key_indicator = False
    if isinstance(cert_indicators, dict):
        certificate_files = _indicator_paths(cert_indicators, "certificate_file_indicators")
        config_files = _indicator_paths(cert_indicators, "config_file_indicators")
        counts = (
            (cert_indicators.get("certificate_file_indicators") or {}).get("counts", {})
            if isinstance(cert_indicators.get("certificate_file_indicators"), dict)
            else {}
        )
        key_count = _safe_int(counts.get("key")) if isinstance(counts, dict) else None
        private_key_indicator = bool(key_count and key_count > 0)
        if private_key_indicator:
            warnings.append("host_evidence: private key indicator present")

    host = host_inventory if isinstance(host_inventory, dict) else {}
    return NormalizedHostEvidence(
        hostname=_clean_str(host.get("hostname")),
        os=_clean_str(host.get("os")),
        package_manager=package_manager,
        packages=packages,
        certificate_files=certificate_files,
        config_files=config_files,
        private_key_indicator=private_key_indicator,
    )


def normalize(request: NormalizeRequest) -> NormalizeResponse:
    warnings: list[str] = []

    assets = [
        _normalize_asset(raw, warnings, index)
        for index, raw in enumerate(request.assets)
        if isinstance(raw, dict)
    ]
    if not assets:
        warnings.append("no assets provided")

    host_evidence = None
    if isinstance(request.crypto_evidence, dict) or isinstance(request.host_inventory, dict):
        host_evidence = _normalize_host(
            request.crypto_evidence or {}, request.host_inventory, warnings
        )

    network_evidence = None
    if isinstance(request.tls_evidence, dict):
        network_evidence = _normalize_network(request.tls_evidence, warnings)

    if host_evidence is None and network_evidence is None:
        warnings.append("no host or network evidence provided")

    return NormalizeResponse(
        contract_version=CONTRACT_VERSION,
        source=request.source,
        assets=assets,
        host_evidence=host_evidence,
        network_evidence=network_evidence,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "evidence-normalizer"}


@app.post("/normalize", response_model=NormalizeResponse)
def normalize_endpoint(request: NormalizeRequest) -> NormalizeResponse:
    return normalize(request)
