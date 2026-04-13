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
    criticality: float = Field(..., ge=0, le=5)
    confidentiality_lifetime: float = Field(..., ge=0, le=5)
    quantum_exposure: float = Field(..., ge=0, le=5)
    blast_radius: float = Field(..., ge=0, le=5)
    vendor_lock_in: float = Field(..., ge=0, le=5)
    migration_difficulty: float = Field(..., ge=0, le=5)
    scenario: ScenarioName = "public_timeline"


class RiskOutput(BaseModel):
    scenario: str
    scenario_multiplier: float
    base_score: float
    final_score: float
    normalized_score_100: float
    rating: str
    rationale: dict[str, float]


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
    final_score = base_score * scenario_multiplier

    # base_score max is 5.0, scenario max multiplier here is 1.40
    # clamp to 100 for stable UI behavior
    normalized_score_100 = min((final_score / 5.0) * 100.0, 100.0)
    rating = classify_rating(normalized_score_100)

    return RiskOutput(
        scenario=data.scenario,
        scenario_multiplier=scenario_multiplier,
        base_score=round(base_score, 4),
        final_score=round(final_score, 4),
        normalized_score_100=round(normalized_score_100, 2),
        rating=rating,
        rationale={
            "criticality": data.criticality,
            "confidentiality_lifetime": data.confidentiality_lifetime,
            "quantum_exposure": data.quantum_exposure,
            "blast_radius": data.blast_radius,
            "vendor_lock_in": data.vendor_lock_in,
            "migration_difficulty": data.migration_difficulty,
        },
    )
