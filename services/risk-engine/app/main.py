from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Risk Engine")

class RiskInput(BaseModel):
    criticality: float
    confidentiality_lifetime: float
    quantum_exposure: float
    blast_radius: float
    vendor_lock_in: float
    migration_difficulty: float
    scenario_multiplier: float = 1.0

@app.get("/health")
def health():
    return {"status": "ok", "service": "risk-engine"}

@app.post("/score")
def score(data: RiskInput):
    base = (
        data.criticality * 0.25 +
        data.confidentiality_lifetime * 0.20 +
        data.quantum_exposure * 0.20 +
        data.blast_radius * 0.15 +
        data.vendor_lock_in * 0.10 +
        data.migration_difficulty * 0.10
    )
    return {"base_score": base, "final_score": base * data.scenario_multiplier}
