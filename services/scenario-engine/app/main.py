from __future__ import annotations

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Scenario Engine", version="0.1.0")

ScenarioName = Literal[
    "public_timeline",
    "early_break",
    "hidden_capability",
    "hndl_active_now",
    "partial_break",
    "vendor_lag",
    "compliance_pressure",
]

# Scenario risk multipliers (aligned with risk-engine SCENARIO_MULTIPLIERS).
SCENARIOS: dict[str, float] = {
    "public_timeline": 1.00,
    "early_break": 1.20,
    "hidden_capability": 1.35,
    "hndl_active_now": 1.40,
    "partial_break": 1.10,
    "vendor_lag": 1.15,
    "compliance_pressure": 1.18,
}


class ScenarioAssetInput(BaseModel):
    asset_name: str = Field(..., min_length=1)
    base_score: float = Field(..., ge=0, le=5, description="Pre-scenario base risk score (0-5).")
    asset_type: str | None = None
    environment: str | None = None
    dependency_count: int = Field(default=0, ge=0)
    vendor_blocked: bool = False


class ScenarioRunRequest(BaseModel):
    scenario: ScenarioName = "public_timeline"
    assets: list[ScenarioAssetInput] = Field(default_factory=list)


class ScenarioAssetResult(BaseModel):
    asset_name: str
    base_score: float
    scenario: str
    scenario_multiplier: float
    final_score: float
    normalized_score_100: float
    rating: str


class ScenarioRunResponse(BaseModel):
    scenario: str
    scenario_multiplier: float
    asset_count: int
    highest_rating: str
    results: list[ScenarioAssetResult]


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


def apply_scenario(request: ScenarioRunRequest) -> ScenarioRunResponse:
    multiplier = SCENARIOS[request.scenario]

    results: list[ScenarioAssetResult] = []
    for asset in request.assets:
        final_score = asset.base_score * multiplier
        normalized = min((final_score / 5.0) * 100.0, 100.0)
        results.append(
            ScenarioAssetResult(
                asset_name=asset.asset_name,
                base_score=round(asset.base_score, 4),
                scenario=request.scenario,
                scenario_multiplier=multiplier,
                final_score=round(final_score, 4),
                normalized_score_100=round(normalized, 2),
                rating=classify_rating(normalized),
            )
        )

    results.sort(key=lambda item: item.normalized_score_100, reverse=True)
    highest_rating = results[0].rating if results else "minimal"

    return ScenarioRunResponse(
        scenario=request.scenario,
        scenario_multiplier=multiplier,
        asset_count=len(results),
        highest_rating=highest_rating,
        results=results,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "scenario-engine"}


@app.get("/scenarios")
def scenarios() -> dict[str, float]:
    return SCENARIOS


@app.post("/run", response_model=ScenarioRunResponse)
def run(request: ScenarioRunRequest) -> ScenarioRunResponse:
    return apply_scenario(request)
