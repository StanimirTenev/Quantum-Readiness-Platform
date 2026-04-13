from fastapi import FastAPI

app = FastAPI(title="Scenario Engine")

SCENARIOS = {
    "public_timeline": 1.00,
    "early_break": 1.20,
    "hidden_capability": 1.35,
    "hndl_active_now": 1.40,
    "partial_break": 1.10,
    "vendor_lag": 1.15,
    "compliance_pressure": 1.18,
}

@app.get("/health")
def health():
    return {"status": "ok", "service": "scenario-engine"}

@app.get("/scenarios")
def scenarios():
    return SCENARIOS
