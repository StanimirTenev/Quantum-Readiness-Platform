from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .clients.inventory import InventoryClient
from .planner import build_plan

app = FastAPI(title="Planner Service", version="0.1.0")
inventory = InventoryClient()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "planner-service"}


@app.get("/plan")
def plan() -> dict:
    try:
        assets = inventory.get_assets()
        risks = inventory.get_risks()
        return build_plan(assets, risks)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {exc}") from exc


@app.get("/waves")
def waves() -> dict:
    try:
        assets = inventory.get_assets()
        risks = inventory.get_risks()
        plan_data = build_plan(assets, risks)
        return {
            "wave_1": plan_data["wave_1"],
            "wave_2": plan_data["wave_2"],
            "wave_3": plan_data["wave_3"],
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Wave generation failed: {exc}") from exc
