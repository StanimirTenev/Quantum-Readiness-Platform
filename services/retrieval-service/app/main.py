from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .clients.inventory import InventoryClient
from .clients.planner import PlannerClient
from .clients.workflow import WorkflowClient
from .search import build_overview, get_asset_bundle, search_all

app = FastAPI(title="Retrieval Service", version="0.1.0")
inventory = InventoryClient()
planner = PlannerClient()
workflow = WorkflowClient()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "retrieval-service"}


@app.get("/overview")
def overview() -> dict:
    try:
        assets = inventory.get_assets()
        scans = inventory.get_scans()
        risks = inventory.get_risks()
        tasks = workflow.get_tasks()
        approvals = workflow.get_approvals()
        plan = planner.get_plan()
        return build_overview(assets, scans, risks, tasks, approvals, plan)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Overview failed: {exc}") from exc


@app.get("/asset")
def asset(asset_name: str = Query(..., min_length=1)) -> dict:
    try:
        assets = inventory.get_assets()
        scans = inventory.get_scans()
        risks = inventory.get_risks()
        tasks = workflow.get_tasks()
        return get_asset_bundle(asset_name, assets, scans, risks, tasks)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Asset lookup failed: {exc}") from exc


@app.post("/search")
def search(payload: SearchRequest) -> dict:
    try:
        assets = inventory.get_assets()
        scans = inventory.get_scans()
        risks = inventory.get_risks()
        tasks = workflow.get_tasks()
        return {
            "query": payload.query,
            "results": search_all(payload.query, assets, scans, risks, tasks),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc
