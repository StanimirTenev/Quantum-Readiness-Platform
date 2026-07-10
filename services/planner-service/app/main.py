from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Literal

from .clients.inventory import InventoryClient
from .clients.workflow import WorkflowClient
from .planner import build_plan

app = FastAPI(title="Planner Service", version="0.2.0")
inventory = InventoryClient()
workflow = WorkflowClient()


class ExportRequest(BaseModel):
    waves: list[Literal["wave_1", "wave_2", "wave_3"]] = Field(default_factory=lambda: ["wave_1"])
    auto_submit: bool = False
    requested_by: str = Field(..., min_length=1, max_length=255)


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


@app.post("/export-tasks")
def export_tasks(payload: ExportRequest) -> dict:
    try:
        assets = inventory.get_assets()
        risks = inventory.get_risks()
        plan_data = build_plan(assets, risks)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Plan generation failed: {exc}") from exc

    created_tasks: list[dict] = []

    for wave_name in payload.waves:
        for item in plan_data[wave_name]:
            priority = _priority_from_rating(item.get("rating", "medium"))
            task_payload = {
                "title": f"Review {item['asset_name']}",
                "asset_name": item["asset_name"],
                "wave": wave_name,
                "priority": priority,
                "description": f"Planned remediation for {item['asset_name']} in {wave_name}.",
                "recommended_action": item.get("recommended_action"),
                "requested_by": payload.requested_by,
            }

            try:
                created = workflow.create_task(task_payload)
                created_tasks.append(created)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Task export failed: {exc}") from exc

    return {
        "exported_waves": payload.waves,
        "created_count": len(created_tasks),
        "tasks": created_tasks,
    }


def _priority_from_rating(rating: str) -> str:
    mapping = {
        "critical": "critical",
        "high": "high",
        "medium": "medium",
        "low": "low",
        "minimal": "low",
    }
    return mapping.get(rating, "medium")
