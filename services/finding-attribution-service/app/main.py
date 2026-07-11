from __future__ import annotations

import hashlib
from typing import Any, Literal

from fastapi import FastAPI
from pydantic import AliasChoices, BaseModel, Field

app = FastAPI(title="Finding Attribution Service", version="0.1.0")

CONTRACT_VERSION = "attr-v1"

# ---------------------------------------------------------------------------
# Finding Location & Application Attribution Contract
# ---------------------------------------------------------------------------
# Every crypto-fingerprint finding is enriched with:
#   - a typed LOCATION (network endpoint / file / package / manual)
#   - an ATTRIBUTION to an asset, a service/application, and the concrete crypto
#     object it lives on (certificate / library / pipeline / cipher suite)
# and an explicit CHAIN:
#   vulnerability -> location -> service/app -> asset -> certificate/library/pipeline

LocationKind = Literal["network_endpoint", "config_file", "package", "manual", "unknown"]
CryptoObjectKind = Literal["certificate", "library", "pipeline", "cipher_suite", "config"]


class Vulnerability(BaseModel):
    algorithm_family: str | None = None
    classification: str | None = None
    severity: str | None = None
    quantum_vulnerable: bool = False
    harvest_now_decrypt_later: bool = False
    reason: str | None = None


class Location(BaseModel):
    kind: LocationKind
    value: str | None = None
    evidence_ref: str | None = None


class CryptoObject(BaseModel):
    kind: CryptoObjectKind
    id: str | None = None
    label: str | None = None


class Attribution(BaseModel):
    asset: str
    service: str | None = None
    application: str | None = None
    crypto_object: CryptoObject | None = None


class AttributedFinding(BaseModel):
    finding_id: str
    vulnerability: Vulnerability
    location: Location
    attribution: Attribution
    chain: list[str]


class AttributeRequest(BaseModel):
    asset_name: str = Field(..., min_length=1)
    application: str | None = None
    findings: list[dict[str, Any]] = Field(default_factory=list)
    # Accept the evidence-normalizer shapes or the raw scanner shapes.
    network_evidence: dict[str, Any] | None = Field(
        default=None, validation_alias=AliasChoices("network_evidence", "tls_metadata")
    )
    host_evidence: dict[str, Any] | None = Field(
        default=None, validation_alias=AliasChoices("host_evidence", "crypto_evidence")
    )


class AttributeSummary(BaseModel):
    total: int
    attributed: int
    unattributed: int
    network_endpoint: int
    package: int


class AttributeResponse(BaseModel):
    contract_version: str
    asset_name: str
    attributed_findings: list[AttributedFinding]
    summary: AttributeSummary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _endpoint(network: dict[str, Any] | None) -> str | None:
    if not isinstance(network, dict):
        return None
    target = network.get("target") or network.get("server_name")
    port = network.get("port")
    if target and port is not None:
        return f"{target}:{port}"
    return str(target) if target else None


def _certificate(network: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """Return (certificate_id, label) from either normalizer or raw TLS shape."""
    if not isinstance(network, dict):
        return None, None
    cert = network.get("certificate")
    if not isinstance(cert, dict):
        return None, None
    fp = cert.get("fingerprint_sha256") or cert.get("sha256_fingerprint")
    subject = cert.get("subject")
    if isinstance(subject, dict):
        subject = subject.get("display_dn")
    cert_id = f"certificate:{fp}" if fp else None
    return cert_id, (subject if isinstance(subject, str) else None)


def _finding_id(asset: str, family: str | None, location_value: str | None, classification: str | None) -> str:
    material = f"{asset}|{family}|{location_value}|{classification}"
    return "finding:" + hashlib.sha256(material.encode()).hexdigest()[:16]


def attribute_finding(
    finding: dict[str, Any],
    asset_name: str,
    application: str | None,
    network: dict[str, Any] | None,
) -> AttributedFinding:
    source = str(finding.get("source") or "")
    loc_ref = str(finding.get("location") or "")
    family = finding.get("algorithm_family")
    classification = finding.get("classification")
    raw_value = finding.get("raw_value")

    service: str | None = None
    crypto_object: CryptoObject | None = None
    location_kind: LocationKind = "unknown"
    location_value: str | None = raw_value

    if source == "tls_certificate" or loc_ref.startswith("tls_metadata.certificate"):
        endpoint = _endpoint(network)
        location_kind, location_value, service = "network_endpoint", endpoint, endpoint
        cert_id, cert_label = _certificate(network)
        crypto_object = CryptoObject(kind="certificate", id=cert_id, label=cert_label or family)
    elif source == "tls_cipher_suite":
        endpoint = _endpoint(network)
        location_kind, location_value, service = "network_endpoint", endpoint, endpoint
        crypto_object = CryptoObject(kind="cipher_suite", id=None, label=raw_value)
    elif source == "host_package" or loc_ref.startswith("crypto_evidence.package"):
        name = raw_value or family
        location_kind, location_value = "package", name
        crypto_object = CryptoObject(kind="library", id=f"package:{name}" if name else None, label=name)
    elif source == "repo_ci_pipeline":
        location_kind, location_value = "config_file", loc_ref or raw_value
        crypto_object = CryptoObject(kind="pipeline", id=None, label=raw_value)
    elif source == "repo_embedded_key":
        location_kind, location_value = "config_file", loc_ref or raw_value
        crypto_object = CryptoObject(kind="config", id=None, label=raw_value)
    elif source == "explicit_algorithm":
        location_kind, location_value = "manual", raw_value
    else:
        location_kind, location_value = "unknown", raw_value

    vulnerability = Vulnerability(
        algorithm_family=family,
        classification=classification,
        severity=finding.get("severity"),
        quantum_vulnerable=bool(finding.get("quantum_vulnerable")),
        harvest_now_decrypt_later=bool(finding.get("harvest_now_decrypt_later")),
        reason=finding.get("reason"),
    )
    attribution = Attribution(
        asset=asset_name, service=service, application=application, crypto_object=crypto_object
    )

    chain: list[str] = [
        f"{family} ({classification})" if family else str(classification),
        location_value or "unknown-location",
        service or application or "unattributed-service",
        f"asset:{asset_name}",
    ]
    if crypto_object and crypto_object.label:
        chain.append(f"{crypto_object.kind}:{crypto_object.label}")

    return AttributedFinding(
        finding_id=_finding_id(asset_name, family, location_value, classification),
        vulnerability=vulnerability,
        location=Location(kind=location_kind, value=location_value, evidence_ref=loc_ref or None),
        attribution=attribution,
        chain=chain,
    )


def attribute(request: AttributeRequest) -> AttributeResponse:
    attributed = [
        attribute_finding(f, request.asset_name, request.application, request.network_evidence)
        for f in request.findings
        if isinstance(f, dict)
    ]
    network_count = sum(1 for a in attributed if a.location.kind == "network_endpoint")
    package_count = sum(1 for a in attributed if a.location.kind == "package")
    attributed_count = sum(1 for a in attributed if a.attribution.service or a.attribution.crypto_object)

    return AttributeResponse(
        contract_version=CONTRACT_VERSION,
        asset_name=request.asset_name,
        attributed_findings=attributed,
        summary=AttributeSummary(
            total=len(attributed),
            attributed=attributed_count,
            unattributed=len(attributed) - attributed_count,
            network_endpoint=network_count,
            package=package_count,
        ),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "finding-attribution-service"}


@app.get("/contract")
def contract() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "chain": ["vulnerability", "location", "service/application", "asset", "certificate/library/pipeline"],
        "location_kinds": ["network_endpoint", "config_file", "package", "manual", "unknown"],
        "crypto_object_kinds": ["certificate", "library", "pipeline", "cipher_suite", "config"],
    }


@app.post("/attribute", response_model=AttributeResponse)
def attribute_endpoint(request: AttributeRequest) -> AttributeResponse:
    return attribute(request)
