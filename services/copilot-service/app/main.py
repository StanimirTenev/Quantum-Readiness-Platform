from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .clients.inventory import InventoryClient

app = FastAPI(title="Copilot Service", version="0.1.0")
inventory = InventoryClient()


class QueryRequest(BaseModel):
    question: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "copilot-service"}


@app.get("/summary")
def summary() -> dict:
    assets = inventory.get_assets()
    scans = inventory.get_scans()
    risks = inventory.get_risks()

    risk_counts: dict[str, int] = {}
    for item in risks:
        rating = item.get("rating", "unknown")
        risk_counts[rating] = risk_counts.get(rating, 0) + 1

    top_risks = sorted(
        risks,
        key=lambda x: x.get("normalized_score_100", 0),
        reverse=True,
    )[:5]

    return {
        "asset_count": len(assets),
        "scan_count": len(scans),
        "risk_count": len(risks),
        "risk_counts": risk_counts,
        "top_risks": top_risks,
    }


@app.get("/top-risks")
def top_risks(limit: int = 5) -> dict:
    risks = inventory.get_risks()
    ordered = sorted(
        risks,
        key=lambda x: x.get("normalized_score_100", 0),
        reverse=True,
    )[:limit]
    return {"count": len(ordered), "items": ordered}


@app.get("/scan/{scan_id}")
def scan_details(scan_id: str) -> dict:
    try:
        return inventory.get_scan(scan_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Scan lookup failed: {exc}") from exc


@app.post("/query")
def query(payload: QueryRequest) -> dict:
    question = payload.question.strip().lower()

    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty")

    if "summary" in question or "overview" in question:
        return {"intent": "summary", "result": summary()}

    if "top risk" in question or "highest risk" in question:
        return {"intent": "top_risks", "result": top_risks()}

    if "scan " in question:
        parts = question.split()
        for part in parts:
            if "-" in part and len(part) >= 8:
                return {"intent": "scan_details", "result": scan_details(part)}
        return {"intent": "scan_details", "result": "No scan_id found in question."}

    risks = inventory.get_risks()
    assets = inventory.get_assets()
    scans = inventory.get_scans()

    return {
        "intent": "fallback",
        "result": {
            "message": "Query not specifically mapped yet. Returning high-level platform snapshot.",
            "asset_count": len(assets),
            "scan_count": len(scans),
            "risk_count": len(risks),
        },
    }
