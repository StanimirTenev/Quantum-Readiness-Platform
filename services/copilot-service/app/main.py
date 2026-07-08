from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .clients.inventory import InventoryClient
from .clients.planner import PlannerClient
from .clients.retrieval import RetrievalClient
from .clients.workflow import WorkflowClient
from .discovery_analyst import build_discovery_summary
from .graph_snapshot import load_graph_snapshot
from .migration_planner import build_migration_plan_summary
from .providers import DISABLED_ANSWER, CopilotProviderRuntime
from .risk_narrator import narrate_asset_bundle
from .vendor_intelligence_analyst import build_vendor_intelligence_summary

app = FastAPI(title="Copilot Service", version="0.4.0")
retrieval = RetrievalClient()
planner = PlannerClient()
workflow = WorkflowClient()
inventory = InventoryClient()
provider_runtime = CopilotProviderRuntime()

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
    return provider_runtime.query(payload.metadata.get("request_id"))


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


@app.get("/narrate/{asset_name:path}")
def narrate_asset(asset_name: str) -> dict:
    """Risk Narrator: plain-language explanation of an asset's persisted risk.
    Deterministic (template rules over risk-engine's rationale), not an LLM
    call -- see app/risk_narrator.py."""
    try:
        asset_bundle = retrieval.get_asset(asset_name)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Narrate failed: {exc}") from exc

    return narrate_asset_bundle(asset_name, asset_bundle)


@app.get("/discover")
def discover() -> dict:
    """Discovery Analyst: deterministic synthesis of crypto dependencies found
    across host/network/repo scans, indexed documents, the dependency graph,
    and persisted risk records -- explicit findings, inferred context, and
    evidence gaps. No LLM call, read-only. See app/discovery_analyst.py."""
    try:
        scans = inventory.get_scans()
        risks = inventory.get_risks()
        documents = retrieval.get_documents().get("documents", [])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {exc}") from exc

    graph_snapshot = load_graph_snapshot()
    return build_discovery_summary(scans, documents, graph_snapshot, risks)


@app.get("/vendor-intelligence")
def vendor_intelligence() -> dict:
    """Vendor Intelligence Analyst: deterministic extraction of PQC readiness
    claims from indexed vendor documents, with a confidence/uncertainty
    classification -- roadmap language is flagged uncertain, not treated as
    fact. No LLM call, read-only. See app/vendor_intelligence_analyst.py."""
    try:
        documents = retrieval.get_documents().get("documents", [])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vendor intelligence failed: {exc}") from exc

    return build_vendor_intelligence_summary(documents)


@app.get("/migration-plan")
def migration_plan() -> dict:
    """Migration Planner: deterministic plain-language explanation of
    planner-service's wave/priority plan -- why each asset landed in its
    wave, plus document-level vendor readiness context from Vendor
    Intelligence Analyst. No LLM call, read-only. See app/migration_planner.py."""
    try:
        plan_data = planner.get_plan()
        documents = retrieval.get_documents().get("documents", [])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Migration plan failed: {exc}") from exc

    readiness_matrix = build_vendor_intelligence_summary(documents)["readiness_matrix"]
    return build_migration_plan_summary(plan_data, readiness_matrix)


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

    if "discover" in lowered or "dependencies" in lowered or "dependency" in lowered:
        return {"intent": "discover", "result": discover()}

    if "vendor" in lowered or "readiness matrix" in lowered or "roadmap" in lowered:
        return {"intent": "vendor_intelligence", "result": vendor_intelligence()}

    if "migration plan" in lowered or "sequencing" in lowered or "migration order" in lowered:
        return {"intent": "migration_plan", "result": migration_plan()}

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

    if ("why" in lowered or "explain" in lowered) and "asset " in lowered:
        remainder = question.split("asset ", 1)[1].strip()
        asset_name = remainder.split(" ", 1)[0].rstrip("?.,!")
        if asset_name:
            return {"intent": "narrate_asset", "result": narrate_asset(asset_name)}

    if "asset " in lowered:
        asset_name = question.split("asset ", 1)[1].strip()
        if asset_name:
            return {"intent": "asset_details", "result": asset_details(asset_name)}

    if "scan " in lowered:
        return {"intent": "search", "result": retrieval.search(question)}

    return {"intent": "search", "result": retrieval.search(question)}



def _risk_counts_from_top_risks(risks: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in risks:
        rating = item.get("rating", "unknown")
        counts[rating] = counts.get(rating, 0) + 1
    return counts
