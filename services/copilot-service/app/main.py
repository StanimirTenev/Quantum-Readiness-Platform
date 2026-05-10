from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .clients.planner import PlannerClient
from .clients.retrieval import RetrievalClient
from .clients.workflow import WorkflowClient

app = FastAPI(title="Copilot Service", version="0.4.0")
retrieval = RetrievalClient()
planner = PlannerClient()
workflow = WorkflowClient()
DISABLED_ANSWER = (
    "Copilot provider is disabled. The deterministic QRP core remains available. "
    "Configure a local provider for offline analysis."
)


class QueryRequest(BaseModel):
    question: str


class CopilotSensitivity(BaseModel):
    contains_sensitive_data: bool | None = None
    allowed_external: bool | None = None


class CopilotRequest(BaseModel):
    query: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    sensitivity: CopilotSensitivity | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "copilot-service"}


@app.post("/copilot/query")
def copilot_query(payload: CopilotRequest) -> dict[str, Any]:
    return _disabled_copilot_response(payload.metadata.get("request_id"))


@app.get("/summary")
def summary() -> dict:
    try:
        overview = retrieval.get_overview()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Summary failed: {exc}") from exc

    return {
        "asset_count": overview["asset_count"],
        "scan_count": overview["scan_count"],
        "risk_count": overview["risk_count"],
        "risk_counts": _risk_counts_from_top_risks(overview.get("top_risks", [])),
        "top_risks": overview.get("top_risks", []),
    }


@app.get("/top-risks")
def top_risks(limit: int = 5) -> dict:
    try:
        overview = retrieval.get_overview()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Top risks failed: {exc}") from exc

    items = overview.get("top_risks", [])[:limit]
    return {"count": len(items), "items": items}


@app.get("/asset/{asset_name:path}")
def asset_details(asset_name: str) -> dict:
    try:
        return retrieval.get_asset(asset_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Asset lookup failed: {exc}") from exc


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
        overview = retrieval.get_overview()
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
        "platform": {
            "asset_count": overview["asset_count"],
            "scan_count": overview["scan_count"],
            "risk_count": overview["risk_count"],
            "risk_counts": _risk_counts_from_top_risks(overview.get("top_risks", [])),
            "top_risks": overview.get("top_risks", []),
        },
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
    question = payload.question.strip()
    lowered = question.lower()

    if not lowered:
        raise HTTPException(status_code=400, detail="Question must not be empty")

    if "operational" in lowered or "operations" in lowered:
        return {"intent": "operational_summary", "result": operational_summary()}

    if "workflow" in lowered or "tasks" in lowered or "approvals" in lowered:
        return {"intent": "workflow_summary", "result": workflow_summary()}

    if "plan" in lowered or "wave" in lowered:
        return {"intent": "plan_summary", "result": plan_summary()}

    if "summary" in lowered or "overview" in lowered:
        return {"intent": "summary", "result": summary()}

    if "top risk" in lowered or "highest risk" in lowered:
        return {"intent": "top_risks", "result": top_risks()}

    if "asset " in lowered:
        asset_name = question.split("asset ", 1)[1].strip()
        if asset_name:
            return {"intent": "asset_details", "result": asset_details(asset_name)}

    if "scan " in lowered:
        return {"intent": "search", "result": retrieval.search(question)}

    return {"intent": "search", "result": retrieval.search(question)}


def _resolve_provider_mode() -> str:
    provider_mode = os.getenv("COPILOT_PROVIDER", "disabled").strip().lower()
    if provider_mode not in {"disabled", "local", "external"}:
        return "disabled"
    return provider_mode


def _disabled_copilot_response(request_id: str | None) -> dict[str, Any]:
    _ = _resolve_provider_mode()
    resolved_request_id = request_id or f"copilot-disabled-{uuid.uuid4().hex[:12]}"
    return {
        "answer": DISABLED_ANSWER,
        "provider_mode": "disabled",
        "citations": [],
        "warnings": ["copilot_provider_disabled"],
        "used_external_provider": False,
        "redaction_applied": False,
        "metadata": {
            "request_id": resolved_request_id,
            "provider_name": "disabled",
        },
    }


def _risk_counts_from_top_risks(risks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in risks:
        rating = item.get("rating", "unknown")
        counts[rating] = counts.get(rating, 0) + 1
    return counts
