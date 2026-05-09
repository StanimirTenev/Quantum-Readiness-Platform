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
    vendor_blocked: bool = False
    scenario: ScenarioName = "public_timeline"
    stage2_notes: str | None = None
    crypto_evidence: dict[str, Any] | None = None
    tls_metadata: dict[str, Any] | None = None


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
    rationale: dict[str, float | int | bool]


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
        },
    )
