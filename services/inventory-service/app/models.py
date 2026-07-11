from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict, AliasChoices, field_validator, model_validator

AssetType = Literal[
    "server",
    "service",
    "endpoint",
    "certificate",
    "pipeline",
    "backup",
    "library",
    "vendor_product",
    "other",
]


def _clean_optional_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_string_list(raw: Any, warnings: list[str], field_name: str) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        value = raw.strip()
        return [value] if value else []
    if not isinstance(raw, list):
        warnings.append(f"{field_name}: expected list[str], got {type(raw).__name__}")
        return []

    normalized: list[str] = []
    dropped = 0
    for item in raw:
        if isinstance(item, str):
            cleaned = item.strip()
            if cleaned:
                normalized.append(cleaned)
                continue
        dropped += 1

    if dropped:
        warnings.append(f"{field_name}: dropped {dropped} non-string or empty entries")
    return normalized


class AssetBase(BaseModel):
    asset_type: AssetType = Field(..., description="Logical asset category.")
    name: str = Field(..., min_length=1, max_length=255)
    owner: Optional[str] = Field(default=None, max_length=255)
    criticality: Optional[int] = Field(default=None, ge=1, le=5)
    environment: Optional[str] = Field(default=None, max_length=50)
    vendor: Optional[str] = Field(default=None, max_length=255)
    lifecycle_years: Optional[int] = Field(default=None, ge=0, le=50)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty")
        return value


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseModel):
    asset_type: Optional[AssetType] = None
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    owner: Optional[str] = Field(default=None, max_length=255)
    criticality: Optional[int] = Field(default=None, ge=1, le=5)
    environment: Optional[str] = Field(default=None, max_length=50)
    vendor: Optional[str] = Field(default=None, max_length=255)
    lifecycle_years: Optional[int] = Field(default=None, ge=0, le=50)

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("name must not be empty")
        return value


class Asset(AssetBase):
    id: str
    created_at: Optional[str] = None
    workspace_id: Optional[str] = None


class HostInventory(BaseModel):
    model_config = ConfigDict(extra="allow")

    hostname: Optional[str] = None
    os: Optional[str] = None
    kernel: Optional[str] = None
    architecture: Optional[str] = None
    ips: list[str] = Field(default_factory=list)
    normalization_warnings: list[str] = Field(default_factory=list, validation_alias=AliasChoices("_normalization_warnings", "normalization_warnings"), serialization_alias="_normalization_warnings")

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        warnings: list[str] = list(data.get("_normalization_warnings") or [])
        data = dict(data)
        data["hostname"] = _clean_optional_string(data.get("hostname"))
        data["os"] = _clean_optional_string(data.get("os"))
        data["kernel"] = _clean_optional_string(data.get("kernel"))
        data["architecture"] = _clean_optional_string(data.get("architecture"))
        data["ips"] = _normalize_string_list(data.get("ips"), warnings, "host_inventory.ips")
        data["_normalization_warnings"] = warnings
        return data




class Stage2PackageMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    package_manager: Optional[str] = None
    collected: Optional[bool] = None
    packages: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[Any] = Field(default_factory=list)


class Stage2IndicatorBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    collected: Optional[bool] = None
    searched_paths: list[str] = Field(default_factory=list)
    files: list[dict[str, Any]] = Field(default_factory=list)
    counts: dict[str, Any] = Field(default_factory=dict)
    errors: list[Any] = Field(default_factory=list)


class Stage2CertIndicators(BaseModel):
    model_config = ConfigDict(extra="allow")

    certificate_file_indicators: Optional[Stage2IndicatorBlock] = None
    config_file_indicators: Optional[Stage2IndicatorBlock] = None

class CryptoEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    openssl_available: bool = False
    openssl_version: Optional[str] = None
    ssh_config_path: Optional[str] = None
    known_crypto_files: list[str] = Field(default_factory=list)
    config_indicators: Optional[dict[str, Any]] = None
    cert_indicators: Optional[Stage2CertIndicators | dict[str, Any]] = None
    package_metadata: Optional[Stage2PackageMetadata | dict[str, Any]] = None
    normalization_warnings: list[str] = Field(default_factory=list, validation_alias=AliasChoices("_normalization_warnings", "normalization_warnings"), serialization_alias="_normalization_warnings")

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        data = dict(data)
        warnings: list[str] = list(data.get("_normalization_warnings") or [])

        if not isinstance(data.get("openssl_available"), bool):
            if data.get("openssl_available") is None:
                data["openssl_available"] = False
            else:
                warnings.append("crypto_evidence.openssl_available: coerced to bool default false")
                data["openssl_available"] = False

        data["openssl_version"] = _clean_optional_string(data.get("openssl_version"))
        data["ssh_config_path"] = _clean_optional_string(data.get("ssh_config_path"))
        data["known_crypto_files"] = _normalize_string_list(
            data.get("known_crypto_files"), warnings, "crypto_evidence.known_crypto_files"
        )

        for field_name in ("config_indicators", "cert_indicators", "package_metadata"):
            block = data.get(field_name)
            if block is not None and not isinstance(block, dict):
                warnings.append(f"crypto_evidence.{field_name}: expected object, dropped invalid value")
                data[field_name] = None

        package_metadata = data.get("package_metadata")
        if isinstance(package_metadata, dict):
            if "packages" in package_metadata and not isinstance(package_metadata.get("packages"), list):
                raise ValueError("crypto_evidence.package_metadata.packages must be an array when provided")
            if "packages" not in package_metadata:
                package_metadata["packages"] = []
        cert_indicators = data.get("cert_indicators")
        if isinstance(cert_indicators, dict):
            for field_name in ("certificate_file_indicators", "config_file_indicators"):
                block = cert_indicators.get(field_name)
                if isinstance(block, dict):
                    block.setdefault("searched_paths", [])
                    block.setdefault("files", [])
                    block.setdefault("errors", [])

        data["_normalization_warnings"] = warnings
        return data


class TLSEvidenceCertificate(BaseModel):
    model_config = ConfigDict(extra="allow")

    subject: Optional[str] = None
    issuer: Optional[str] = None
    not_before: Optional[str] = None
    not_after: Optional[str] = None
    signature_algorithm: Optional[str] = None
    public_key_algorithm: Optional[str] = None
    public_key_size: Optional[int] = None
    dns_names: list[str] = Field(default_factory=list)
    normalization_warnings: list[str] = Field(default_factory=list, validation_alias=AliasChoices("_normalization_warnings", "normalization_warnings"), serialization_alias="_normalization_warnings")

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        data = dict(data)
        warnings: list[str] = list(data.get("_normalization_warnings") or [])

        subject = data.get("subject")
        issuer = data.get("issuer")
        if isinstance(subject, dict):
            data["subject"] = _clean_optional_string(subject.get("display_dn"))
            warnings.append("tls_evidence.certificate.subject: normalized from stage2 object")
        else:
            data["subject"] = _clean_optional_string(subject)

        if isinstance(issuer, dict):
            data["issuer"] = _clean_optional_string(issuer.get("display_dn"))
            warnings.append("tls_evidence.certificate.issuer: normalized from stage2 object")
        else:
            data["issuer"] = _clean_optional_string(issuer)

        validity = data.get("validity")
        if isinstance(validity, dict):
            data["not_before"] = _clean_optional_string(validity.get("not_before"))
            data["not_after"] = _clean_optional_string(validity.get("not_after"))
            warnings.append("tls_evidence.certificate.validity: normalized from stage2 object")
        else:
            data["not_before"] = _clean_optional_string(data.get("not_before"))
            data["not_after"] = _clean_optional_string(data.get("not_after"))

        algorithms = data.get("algorithms")
        if isinstance(algorithms, dict):
            data["signature_algorithm"] = _clean_optional_string(algorithms.get("signature"))
            data["public_key_algorithm"] = _clean_optional_string(algorithms.get("public_key"))
            warnings.append("tls_evidence.certificate.algorithms: normalized from stage2 object")
        else:
            data["signature_algorithm"] = _clean_optional_string(data.get("signature_algorithm"))
            data["public_key_algorithm"] = _clean_optional_string(data.get("public_key_algorithm"))

        key_block = data.get("key")
        if isinstance(key_block, dict):
            data["public_key_size"] = key_block.get("size_bits")
            warnings.append("tls_evidence.certificate.key: normalized from stage2 object")

        san = data.get("san")
        if isinstance(san, dict):
            data["dns_names"] = _normalize_string_list(
                san.get("dns_names"), warnings, "tls_evidence.certificate.san.dns_names"
            )
            warnings.append("tls_evidence.certificate.san: normalized from stage2 object")
        else:
            data["dns_names"] = _normalize_string_list(
                data.get("dns_names"), warnings, "tls_evidence.certificate.dns_names"
            )

        data["_normalization_warnings"] = warnings
        return data


class TLSEvidence(BaseModel):
    model_config = ConfigDict(extra="allow")

    target: Optional[str] = None
    tls_version: Optional[str] = Field(default=None, validation_alias=AliasChoices("tls_version", "protocol_version"))
    cipher_suite: Optional[str] = None
    server_name: Optional[str] = None
    port: Optional[int] = None
    collected: Optional[bool] = None
    certificate: Optional[TLSEvidenceCertificate] = None
    certificate_chain: Optional[dict[str, Any]] = None
    normalization_warnings: list[str] = Field(default_factory=list, validation_alias=AliasChoices("_normalization_warnings", "normalization_warnings"), serialization_alias="_normalization_warnings")

    @model_validator(mode="before")
    @classmethod
    def normalize_payload(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        data = dict(data)
        warnings: list[str] = list(data.get("_normalization_warnings") or [])
        data["target"] = _clean_optional_string(data.get("target"))
        if "tls_version" not in data and "protocol_version" in data:
            data["tls_version"] = data.get("protocol_version")
        data["tls_version"] = _clean_optional_string(data.get("tls_version"))
        data["cipher_suite"] = _clean_optional_string(data.get("cipher_suite"))
        data["server_name"] = _clean_optional_string(data.get("server_name"))

        cert_chain_value = data.get("certificate_chain")
        if cert_chain_value is not None and not isinstance(cert_chain_value, dict):
            warnings.append("tls_evidence.certificate_chain: expected object, dropped invalid value")
            data["certificate_chain"] = None
        elif isinstance(cert_chain_value, dict):
            certificates_value = cert_chain_value.get("certificates")
            if certificates_value is not None and not isinstance(certificates_value, list):
                raise ValueError("tls_evidence.certificate_chain.certificates must be an array when provided")
            if "certificates" not in cert_chain_value:
                cert_chain_value["certificates"] = []
            cert_chain_value.setdefault("errors", [])

        if data.get("certificate") is None:
            warnings.append("tls_evidence.certificate: missing certificate block")
        elif data.get("collected") is None:
            # Stage2-structured network-scanner payloads carry a certificate
            # block but no explicit `collected` flag; a real certificate is
            # itself proof TLS collection succeeded.
            data["collected"] = True
            warnings.append("tls_evidence.collected: inferred true from a present certificate block")

        data["_normalization_warnings"] = warnings
        return data



    @field_validator("port", mode="before")
    @classmethod
    def validate_port_type(cls, value: Any) -> Any:
        if value is None:
            return value
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError("tls_evidence.port must be a number")
        return value

class SSHEvidence(BaseModel):
    """Deliberately permissive (extra="allow"): captures whatever
    network-scanner's SSH_MSG_KEXINIT parsing reports (target, port,
    collected, server_banner, kex_algorithms, server_host_key_algorithms,
    encryption_algorithms_*, mac_algorithms_*, errors) without a rigid
    schema. Forwarded to risk-engine on ingest (risk_mapper.py), which
    derives weak_ssh_kex_detected/legacy_ssh_host_key_detected/
    weak_ssh_cipher_detected/weak_ssh_mac_detected from it."""

    model_config = ConfigDict(extra="allow")

    target: Optional[str] = None
    collected: Optional[bool] = None


class IPsecEvidence(BaseModel):
    """Deliberately permissive (extra="allow"), same rationale as
    SSHEvidence: captures whatever network-scanner's IKEv2 IKE_SA_INIT probe
    reports (target, port, collected, ike_version, selected_encryption,
    selected_prf, selected_integrity, selected_dh_group, rejected_notify,
    errors) without a rigid schema. Forwarded to risk-engine on ingest
    (risk_mapper.py), which derives legacy_ipsec_dh_group_detected/
    weak_ipsec_encryption_detected/weak_ipsec_integrity_detected/
    weak_ipsec_prf_detected from it."""

    model_config = ConfigDict(extra="allow")

    target: Optional[str] = None
    collected: Optional[bool] = None


class ScanIngestRequest(BaseModel):
    source: Literal["host", "network", "repo", "manual"]
    assets: list[AssetCreate]
    host_inventory: Optional[HostInventory] = None
    crypto_evidence: Optional[CryptoEvidence] = None
    tls_evidence: Optional[TLSEvidence] = Field(default=None, validation_alias=AliasChoices("tls_evidence", "tls_metadata"), serialization_alias="tls_evidence")
    ssh_evidence: Optional[SSHEvidence] = Field(default=None, validation_alias=AliasChoices("ssh_evidence", "ssh_metadata"), serialization_alias="ssh_evidence")
    ipsec_evidence: Optional[IPsecEvidence] = Field(default=None, validation_alias=AliasChoices("ipsec_evidence", "ipsec_metadata"), serialization_alias="ipsec_evidence")
    stage2_notes: Optional[str] = None


class ScanIngestResponse(BaseModel):
    source: str
    created: int
    asset_ids: list[str]
    scan_id: str
    workspace_id: str


class ScanRecord(BaseModel):
    id: str
    source: str
    scanned_at: str
    workspace_id: Optional[str] = None
    host_inventory: Optional[dict[str, Any]] = None
    crypto_evidence: Optional[dict[str, Any]] = None
    tls_evidence: Optional[dict[str, Any]] = None
    ssh_evidence: Optional[dict[str, Any]] = None
    ipsec_evidence: Optional[dict[str, Any]] = None


class WorkspaceCreate(BaseModel):
    source: Optional[str] = Field(default=None, max_length=255)


class Workspace(BaseModel):
    id: str
    source: Optional[str] = None
    created_at: str


class ReportCreate(BaseModel):
    report_type: str = Field(default="operator", max_length=100)


class ReportRecord(BaseModel):
    id: str
    workspace_id: str
    report_type: str
    generated_at: str
    content: str


class RiskRecord(BaseModel):
    id: str
    scan_id: str
    contract_version: str = "stage1-v1"
    asset_name: str
    scenario: str
    scenario_multiplier: float
    base_score: float
    final_score: float
    normalized_score_100: float
    rating: str
    dependency_count: int = 0
    vendor_blocked: bool = False
    rationale: dict[str, Any]


class WorkspaceBundle(BaseModel):
    """A workspace's scan run(s), the findings from them, and any reports
    generated for it -- the "this is scan run X / these are its findings /
    this is its report" grouping the lightweight workspace model exists for."""

    workspace: Workspace
    scans: list[ScanRecord]
    risks: list[RiskRecord]
    reports: list[ReportRecord]


class ScanWithRisk(BaseModel):
    scan: ScanRecord
    risks: list[RiskRecord]


class AssetRiskHistoryPoint(BaseModel):
    scan_id: str
    scanned_at: str
    scenario: str
    rating: str
    normalized_score_100: float
    final_score: float


class AssetRiskHistory(BaseModel):
    asset_id: str
    asset_name: str
    points: list[AssetRiskHistoryPoint]
    first_score: Optional[float] = None
    latest_score: Optional[float] = None
    # Lower risk score = better posture. Direction of the latest vs first point.
    trend: Literal["improving", "worsening", "flat", "insufficient_data"] = "insufficient_data"
