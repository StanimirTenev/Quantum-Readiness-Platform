from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .clients.inventory import InventoryClient
from .clients.planner import PlannerClient
from .clients.workflow import WorkflowClient

app = FastAPI(title="Copilot Service", version="0.3.0")
inventory = InventoryClient()
planner = PlannerClient()
workflow = WorkflowClient()


class QueryRequest(BaseModel):
    question: str


def dedupe_risks_by_asset(risks: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for risk in risks:
        asset_name = risk.get("asset_name", "unknown")
        current = best.get(asset_name)
        if current is None or risk.get("normalized_score_100", 0) > current.get("normalized_score_100", 0):
            best[asset_name] = risk
    return sorted(best.values(), key=lambda x: x.get("normalized_score_100", 0), reverse=True)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "copilot-service"}


@app.get("/summary")
def summary() -> dict:
    assets = inventory.get_assets()
    scans = inventory.get_scans()
    risks = dedupe_risks_by_asset(inventory.get_risks())

    risk_counts: dict[str, int] = {}
    for item in risks:
        rating = item.get("rating", "unknown")
        risk_counts[rating] = risk_counts.get(rating, 0) + 1

    top_risks = risks[:5]

    return {
        "asset_count": len(assets),
        "scan_count": len(scans),
        "risk_count": len(risks),
        "risk_counts": risk_counts,
        "top_risks": top_risks,
    }


@app.get("/top-risks")
def top_risks(limit: int = 5) -> dict:
    risks = dedupe_risks_by_asset(inventory.get_risks())[:limit]
    return {"count": len(risks), "items": risks}


@app.get("/scan/{scan_id}")
def scan_details(scan_id: str) -> dict:
    try:
        return inventory.get_scan(scan_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Scan lookup failed: {exc}") from exc


@app.get("/plan-summary")
def plan_summary() -> dict:
    try:
        return planner.get_plan()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plan summary failed: {exc}") from exc


@app.get("/workflow-summary")
def workflow_summary() -> dict:
    try:
        tasks = workflow.get_tasks()
        approvals = workflow.get_approvals()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Workflow summary failed: {exc}") from exc

    status_counts: dict[str, int] = {}
    for task in tasks:
        status = task.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "task_count": len(tasks),
        "approval_count": len(approvals),
        "status_counts": status_counts,
        "recent_tasks": tasks[:5],
    }


@app.get("/operational-summary")
def operational_summary() -> dict:
    try:
        summary_data = summary()
        plan_data = planner.get_plan()
        tasks = workflow.get_tasks()
        approvals = workflow.get_approvals()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Operational summary failed: {exc}") from exc

    task_status_counts: dict[str, int] = {}
    for task in tasks:
        status = task.get("status", "unknown")
        task_status_counts[status] = task_status_counts.get(status, 0) + 1

    return {
        "platform": summary_data,
        "planning": {
            "wave_1_count": plan_data["summary"]["wave_1_count"],
            "wave_2_count": plan_data["summary"]["wave_2_count"],
            "wave_3_count": plan_data["summary"]["wave_3_count"],
        },
        "workflow": {
            "task_count": len(tasks),
            "approval_count": len(approvals),
            "status_counts": task_status_counts,
        },
    }


@app.post("/query")
def query(payload: QueryRequest) -> dict:
    question = payload.question.strip().lower()

    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty")

    if "operational" in question or "operations" in question:
        return {"intent": "operational_summary", "result": operational_summary()}

    if "workflow" in question or "tasks" in question or "approvals" in question:
        return {"intent": "workflow_summary", "result": workflow_summary()}

    if "plan" in question or "wave" in question:
        return {"intent": "plan_summary", "result": plan_summary()}

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

    risks = dedupe_risks_by_asset(inventory.get_risks())
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
