from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from .clients.inventory import InventoryClient
from .clients.planner import PlannerClient
from .clients.workflow import WorkflowClient
from .document_index import load_document_index, search_documents
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


@app.get("/documents")
def documents() -> dict:
    """Full loaded document index (not search-filtered) -- used by consumers
    that need to walk every ingested document, e.g. the Discovery Analyst
    Copilot subagent, rather than a single keyword query."""
    return load_document_index()


@app.post("/search")
def search(payload: SearchRequest) -> dict:
    try:
        assets = inventory.get_assets()
        scans = inventory.get_scans()
        risks = inventory.get_risks()
        tasks = workflow.get_tasks()
        results = search_all(payload.query, assets, scans, risks, tasks)
        results["documents"] = search_documents(payload.query, load_document_index()["documents"])
        return {"query": payload.query, "results": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc
