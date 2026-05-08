from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(title="Policy Engine")

RULE_ID = "pqc-readiness-gate-v1"
RULE_VERSION = "1.0.0"


class PolicyEvaluationRequest(BaseModel):
    asset_id: str | None = None
    asset_name: str
    asset_type: str | None = None
    environment: str | None = None
    criticality: float = Field(ge=0, le=5)
    normalized_score_100: float = Field(ge=0, le=100)
    rating: str | None = None
    vendor_blocked: bool = False
    dependency_count: int = Field(default=0, ge=0)
    scenario: str = "public_timeline"


class PolicyEvaluationResponse(BaseModel):
    asset_name: str
    decision: str
    score: float = Field(ge=0, le=100)
    reasons: list[str]
    rule_id: str
    rule_version: str


def evaluate_policy(data: PolicyEvaluationRequest) -> PolicyEvaluationResponse:
    """Evaluate a policy decision from deterministic readiness inputs."""
    reasons: list[str] = []

    if data.vendor_blocked:
        decision = "deny"
        reasons.append("vendor_blocked")
    elif data.normalized_score_100 >= 80:
        decision = "deny"
        reasons.append("critical_risk_score")
    elif data.environment == "production" and data.criticality >= 4 and data.normalized_score_100 >= 60:
        decision = "review"
        reasons.append("high_risk_production_asset")
    elif data.dependency_count >= 5 and data.normalized_score_100 >= 50:
        decision = "review"
        reasons.append("dependency_complexity")
    else:
        decision = "allow"
        reasons.append("within_policy_threshold")

    return PolicyEvaluationResponse(
        asset_name=data.asset_name,
        decision=decision,
        score=data.normalized_score_100,
        reasons=reasons,
        rule_id=RULE_ID,
        rule_version=RULE_VERSION,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "policy-engine"}


@app.post("/evaluate", response_model=PolicyEvaluationResponse)
def evaluate(payload: PolicyEvaluationRequest) -> PolicyEvaluationResponse:
    return evaluate_policy(payload)
