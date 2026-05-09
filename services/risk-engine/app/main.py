from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Literal

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
    stage2_signals: dict[str, bool | int]
    stage2_adjustment: float
    rationale: dict[str, float | int | bool]


def extract_stage2_signals(data: RiskInput) -> dict[str, bool | int]:
    notes = (data.stage2_notes or "").lower()
    return {
        "has_hndl_signal": "hndl" in notes or "harvest now decrypt later" in notes,
        "has_pqc_plan_signal": "pqc plan" in notes or "migration plan" in notes,
        "high_dependency_pressure": data.dependency_count >= 10,
        "vendor_blocked": data.vendor_blocked,
        "dependency_count": data.dependency_count,
    }


def calculate_stage2_adjustment(signals: dict[str, bool | int]) -> float:
    adjustment = 0.0
    if signals["vendor_blocked"]:
        adjustment += 0.20
    if signals["high_dependency_pressure"]:
        adjustment += 0.15
    if signals["has_hndl_signal"]:
        adjustment += 0.10
    if signals["has_pqc_plan_signal"]:
        adjustment -= 0.10
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

    # base_score max is 5.0, scenario max multiplier here is 1.40
    # clamp to 100 for stable UI behavior
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
        },
    )
