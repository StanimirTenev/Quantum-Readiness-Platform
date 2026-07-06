from datetime import UTC, datetime, timedelta
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Any, Literal

app = FastAPI(title="Risk Engine", version="0.1.0")

ScenarioName = Literal[
    "public_timeline",
    "early_break",
    "hidden_capability",
    "hndl_active_now",
    "partial_break",
    "vendor_lag",
    "compliance_pressure",
]

SCENARIO_MULTIPLIERS: dict[str, float] = {
    "public_timeline": 1.00,
    "early_break": 1.20,
    "hidden_capability": 1.35,
    "hndl_active_now": 1.40,
    "partial_break": 1.10,
    "vendor_lag": 1.15,
    "compliance_pressure": 1.18,
}

EVIDENCE_SIGNAL_WEIGHTS: dict[str, float] = {
    "crypto_packages_detected": 3.0,
    "certificate_files_detected": 5.0,
    "private_key_files_detected": 10.0,
    "tls_config_detected": 4.0,
    "ssh_config_detected": 3.0,
    "tls_detected": 4.0,
    "weak_public_key_detected": 15.0,
    "expiring_certificate_detected": 8.0,
    "certificate_chain_available": 2.0,
}

# Aggregate Windows host signals (from inventory's windows_normalized_signals).
# Treated as a parallel evidence family to the Linux/network signals above.
WINDOWS_LARGE_ESTATE_THRESHOLD = 50

WINDOWS_SIGNAL_WEIGHTS: dict[str, float] = {
    "windows_expired_certificates": 8.0,
    "windows_weak_signature_certificates": 6.0,
    "windows_domain_controller": 5.0,
    "windows_large_certificate_estate": 3.0,
    "windows_crypto_services_present": 2.0,
}


class RiskInput(BaseModel):
    contract_version: str = "stage1-v1"
    asset_name: str = Field(..., min_length=1)
    criticality: float = Field(..., ge=0, le=5)
    confidentiality_lifetime: float = Field(..., ge=0, le=5)
    quantum_exposure: float = Field(..., ge=0, le=5)
    blast_radius: float = Field(..., ge=0, le=5)
    vendor_lock_in: float = Field(..., ge=0, le=5)
    migration_difficulty: float = Field(..., ge=0, le=5)
    dependency_count: int = Field(default=0, ge=0)
    environment: str | None = None
    vendor_blocked: bool = False
    scenario: ScenarioName = "public_timeline"
    stage2_notes: str | None = None
    crypto_evidence: dict[str, Any] | None = None
    tls_metadata: dict[str, Any] | None = None
    windows_signals: dict[str, Any] | None = None


class RiskOutput(BaseModel):
    contract_version: str
    asset_name: str
    scenario: str
    scenario_multiplier: float
    base_score: float
    final_score: float
    normalized_score_100: float
    rating: str
    dependency_count: int
    vendor_blocked: bool
    stage2_signals: dict[str, bool | int | dict[str, bool]]
    stage2_adjustment: float
    confidence_score: float
    risk_dimensions: dict[str, float]
    rationale: dict[str, float | int | bool | str]


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except (ValueError, TypeError):
        return None


def extract_windows_signals(data: RiskInput) -> dict[str, bool]:
    windows = data.windows_signals if isinstance(data.windows_signals, dict) else {}
    return {
        "windows_expired_certificates": _safe_int(windows.get("expired_certificates_count")) > 0,
        "windows_weak_signature_certificates": _safe_int(windows.get("weak_signature_indicators_count")) > 0,
        "windows_domain_controller": windows.get("domain_controller_role_observed") is True,
        "windows_large_certificate_estate": _safe_int(windows.get("certificates_observed_count"))
        >= WINDOWS_LARGE_ESTATE_THRESHOLD,
        "windows_crypto_services_present": _safe_int(windows.get("crypto_relevant_services_count")) > 0,
    }


def extract_stage2_signals(data: RiskInput) -> dict[str, bool | int | dict[str, bool]]:
    notes = (data.stage2_notes or "").lower()

    notes_signals = {
        "has_hndl_signal": "hndl" in notes or "harvest now decrypt later" in notes,
        "has_pqc_plan_signal": "pqc plan" in notes or "migration plan" in notes,
    }

    cert_file_counts = (
        (data.crypto_evidence or {})
        .get("cert_indicators", {})
        .get("certificate_file_indicators", {})
        .get("counts", {})
    )
    config_counts = (
        (data.crypto_evidence or {})
        .get("cert_indicators", {})
        .get("config_file_indicators", {})
        .get("counts", {})
    )

    packages = ((data.crypto_evidence or {}).get("package_metadata", {}) or {}).get("packages", [])
    packages_len = len(packages) if isinstance(packages, list) else 0

    certificate = ((data.tls_metadata or {}).get("certificate", {}) or {})
    certificate_chain = ((data.tls_metadata or {}).get("certificate_chain", {}) or {})

    public_key_algorithm = str(certificate.get("public_key_algorithm", "")).upper()
    public_key_size = _safe_int(certificate.get("public_key_size"))

    not_after = _parse_iso_datetime(certificate.get("not_after"))
    now_utc = datetime.now(UTC)
    expiration_deadline = now_utc + timedelta(days=90)

    evidence_signals = {
        "crypto_packages_detected": packages_len > 0,
        "certificate_files_detected": _safe_int(cert_file_counts.get("certificate")) > 0,
        "private_key_files_detected": _safe_int(cert_file_counts.get("key")) > 0,
        "tls_config_detected": _safe_int(config_counts.get("tls_server_config")) > 0,
        "ssh_config_detected": _safe_int(config_counts.get("ssh_server_config")) > 0,
        "tls_detected": bool((data.tls_metadata or {}).get("collected") is True),
        "weak_public_key_detected": public_key_algorithm == "RSA" and 0 < public_key_size < 2048,
        "expiring_certificate_detected": bool(
            not_after is not None and now_utc <= not_after <= expiration_deadline
        ),
        "certificate_chain_available": bool(
            certificate_chain.get("available") is True and _safe_int(certificate_chain.get("length")) > 0
        ),
    }

    return {
        "stage2_notes_signals": notes_signals,
        "evidence_signals": evidence_signals,
        "windows_signals": extract_windows_signals(data),
        "windows_evidence_present": isinstance(data.windows_signals, dict) and len(data.windows_signals) > 0,
        "high_dependency_pressure": data.dependency_count >= 10,
        "vendor_blocked": data.vendor_blocked,
        "dependency_count": data.dependency_count,
    }


def calculate_stage2_adjustment(signals: dict[str, bool | int | dict[str, bool]]) -> float:
    adjustment = 0.0

    if bool(signals.get("vendor_blocked")):
        adjustment += 0.20
    if bool(signals.get("high_dependency_pressure")):
        adjustment += 0.15

    notes_signals = signals.get("stage2_notes_signals", {})
    if isinstance(notes_signals, dict):
        if bool(notes_signals.get("has_hndl_signal")):
            adjustment += 0.10
        if bool(notes_signals.get("has_pqc_plan_signal")):
            adjustment -= 0.10

    evidence_signals = signals.get("evidence_signals", {})
    if isinstance(evidence_signals, dict):
        for signal_name, weight in EVIDENCE_SIGNAL_WEIGHTS.items():
            if bool(evidence_signals.get(signal_name)):
                adjustment += weight

    windows_signals = signals.get("windows_signals", {})
    if isinstance(windows_signals, dict):
        for signal_name, weight in WINDOWS_SIGNAL_WEIGHTS.items():
            if bool(windows_signals.get(signal_name)):
                adjustment += weight

    return max(adjustment, 0.0)


def calculate_base_score(data: RiskInput) -> float:
    return (
        data.criticality * 0.25
        + data.confidentiality_lifetime * 0.20
        + data.quantum_exposure * 0.20
        + data.blast_radius * 0.15
        + data.vendor_lock_in * 0.10
        + data.migration_difficulty * 0.10
    )


def _cap_score(value: float) -> float:
    return max(0.0, min(value, 100.0))


def calculate_confidence_score(data: RiskInput, stage2_signals: dict[str, bool | int | dict[str, bool]]) -> float:
    confidence_score = 50.0
    if data.criticality > 0:
        confidence_score += 10.0
    if bool((data.environment or "").strip()):
        confidence_score += 10.0

    evidence_signals = stage2_signals.get("evidence_signals", {})
    has_enriched_signal = isinstance(evidence_signals, dict) and any(bool(v) for v in evidence_signals.values())
    if has_enriched_signal:
        confidence_score += 10.0

    if bool((data.tls_metadata or {}).get("collected") is True):
        confidence_score += 10.0
    if data.crypto_evidence is not None:
        confidence_score += 10.0
    if bool(stage2_signals.get("windows_evidence_present")):
        confidence_score += 10.0
    if bool((evidence_signals or {}).get("certificate_chain_available")):
        confidence_score += 5.0
    if bool((data.stage2_notes or "").strip()):
        confidence_score += 5.0

    return _cap_score(confidence_score)


def calculate_risk_dimensions(data: RiskInput, stage2_signals: dict[str, bool | int | dict[str, bool]]) -> dict[str, float]:
    evidence_signals = stage2_signals.get("evidence_signals", {})
    evidence = evidence_signals if isinstance(evidence_signals, dict) else {}
    windows_evidence = stage2_signals.get("windows_signals", {})
    windows = windows_evidence if isinstance(windows_evidence, dict) else {}

    exposure = (data.quantum_exposure / 5.0) * 100.0
    if bool(evidence.get("tls_detected")):
        exposure += 10.0
    if bool(evidence.get("tls_config_detected")):
        exposure += 8.0
    if bool(evidence.get("ssh_config_detected")):
        exposure += 6.0
    if bool(windows.get("windows_domain_controller")):
        exposure += 10.0

    impact = (data.criticality / 5.0) * 100.0
    if (data.environment or "").strip().lower() == "production":
        impact += 10.0
    if bool(windows.get("windows_domain_controller")):
        impact += 10.0

    urgency = 0.0
    if bool(evidence.get("expiring_certificate_detected")):
        urgency += 45.0
    if bool(evidence.get("weak_public_key_detected")):
        urgency += 30.0
    if bool(evidence.get("private_key_files_detected")):
        urgency += 25.0
    if bool(windows.get("windows_expired_certificates")):
        urgency += 40.0
    if bool(windows.get("windows_weak_signature_certificates")):
        urgency += 25.0

    migration_complexity = min((data.dependency_count * 4.0), 70.0)
    if bool(evidence.get("certificate_files_detected")):
        migration_complexity += 10.0
    if bool(evidence.get("private_key_files_detected")):
        migration_complexity += 15.0
    if data.vendor_blocked:
        migration_complexity += 20.0
    if bool(windows.get("windows_large_certificate_estate")):
        migration_complexity += 15.0
    if bool(windows.get("windows_domain_controller")):
        migration_complexity += 10.0

    return {
        "exposure": _cap_score(exposure),
        "impact": _cap_score(impact),
        "urgency": _cap_score(urgency),
        "migration_complexity": _cap_score(migration_complexity),
    }


def classify_rating(normalized_score_100: float) -> str:
    if normalized_score_100 >= 80:
        return "critical"
    if normalized_score_100 >= 60:
        return "high"
    if normalized_score_100 >= 40:
        return "medium"
    if normalized_score_100 >= 20:
        return "low"
    return "minimal"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "risk-engine"}


@app.get("/scenarios")
def get_scenarios() -> dict[str, float]:
    return SCENARIO_MULTIPLIERS


@app.post("/score", response_model=RiskOutput)
def score(data: RiskInput) -> RiskOutput:
    base_score = calculate_base_score(data)
    scenario_multiplier = SCENARIO_MULTIPLIERS[data.scenario]
    stage2_signals = extract_stage2_signals(data)
    stage2_adjustment = calculate_stage2_adjustment(stage2_signals)
    final_score = (base_score * scenario_multiplier) + stage2_adjustment
    confidence_score = calculate_confidence_score(data, stage2_signals)
    risk_dimensions = calculate_risk_dimensions(data, stage2_signals)

    normalized_score_100 = min((final_score / 5.0) * 100.0, 100.0)
    rating = classify_rating(normalized_score_100)

    return RiskOutput(
        contract_version=data.contract_version,
        asset_name=data.asset_name,
        scenario=data.scenario,
        scenario_multiplier=scenario_multiplier,
        base_score=round(base_score, 4),
        final_score=round(final_score, 4),
        normalized_score_100=round(normalized_score_100, 2),
        rating=rating,
        dependency_count=data.dependency_count,
        vendor_blocked=data.vendor_blocked,
        stage2_signals=stage2_signals,
        stage2_adjustment=round(stage2_adjustment, 4),
        confidence_score=round(confidence_score, 2),
        risk_dimensions={k: round(v, 2) for k, v in risk_dimensions.items()},
        rationale={
            "criticality": data.criticality,
            "confidentiality_lifetime": data.confidentiality_lifetime,
            "quantum_exposure": data.quantum_exposure,
            "blast_radius": data.blast_radius,
            "vendor_lock_in": data.vendor_lock_in,
            "migration_difficulty": data.migration_difficulty,
            "dependency_count": data.dependency_count,
            "vendor_blocked": data.vendor_blocked,
            "crypto_packages_detected": bool(stage2_signals["evidence_signals"].get("crypto_packages_detected")),
            "certificate_files_detected": bool(stage2_signals["evidence_signals"].get("certificate_files_detected")),
            "private_key_files_detected": bool(stage2_signals["evidence_signals"].get("private_key_files_detected")),
            "tls_config_detected": bool(stage2_signals["evidence_signals"].get("tls_config_detected")),
            "ssh_config_detected": bool(stage2_signals["evidence_signals"].get("ssh_config_detected")),
            "tls_detected": bool(stage2_signals["evidence_signals"].get("tls_detected")),
            "weak_public_key_detected": bool(stage2_signals["evidence_signals"].get("weak_public_key_detected")),
            "expiring_certificate_detected": bool(stage2_signals["evidence_signals"].get("expiring_certificate_detected")),
            "certificate_chain_available": bool(stage2_signals["evidence_signals"].get("certificate_chain_available")),
            "confidence_score_computed": "yes",
            "risk_dimensions_computed": "yes",
            "exposure_dimension_from_tls": bool(stage2_signals["evidence_signals"].get("tls_detected")),
            "impact_dimension_from_criticality": True,
            "urgency_dimension_from_expiring_certificate": bool(
                stage2_signals["evidence_signals"].get("expiring_certificate_detected")
            ),
            "migration_complexity_from_private_key_files": bool(
                stage2_signals["evidence_signals"].get("private_key_files_detected")
            ),
            "windows_evidence_present": bool(stage2_signals.get("windows_evidence_present")),
            "windows_expired_certificates": bool(stage2_signals["windows_signals"].get("windows_expired_certificates")),
            "windows_weak_signature_certificates": bool(
                stage2_signals["windows_signals"].get("windows_weak_signature_certificates")
            ),
            "windows_domain_controller": bool(stage2_signals["windows_signals"].get("windows_domain_controller")),
            "windows_large_certificate_estate": bool(
                stage2_signals["windows_signals"].get("windows_large_certificate_estate")
            ),
        },
    )
