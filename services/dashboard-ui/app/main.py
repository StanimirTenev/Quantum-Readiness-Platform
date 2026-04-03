from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

COPILOT_URL = os.getenv("COPILOT_SERVICE_URL", "http://127.0.0.1:8003").rstrip("/")
PLANNER_URL = os.getenv("PLANNER_SERVICE_URL", "http://127.0.0.1:8004").rstrip("/")
WORKFLOW_URL = os.getenv("WORKFLOW_SERVICE_URL", "http://127.0.0.1:8005").rstrip("/")
RETRIEVAL_URL = os.getenv("RETRIEVAL_SERVICE_URL", "http://127.0.0.1:8006").rstrip("/")

app = FastAPI(title="QRP Dashboard UI", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _raise(status_code: int, msg: str, exc: Exception | None = None) -> HTTPException:
    detail = msg if exc is None else f"{msg}: {exc}"
    return HTTPException(status_code=status_code, detail=detail)


async def fetch_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            if method == "GET":
                response = await client.get(url)
            elif method == "POST":
                response = await client.post(url, json=payload)
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as exc:
        raise _raise(exc.response.status_code, f"Upstream HTTP error for {url}", exc) from exc
    except Exception as exc:
        raise _raise(500, f"Upstream connection failed for {url}", exc) from exc


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def api_health() -> dict[str, str]:
    return {"status": "ok", "service": "dashboard-ui"}


@app.get("/api/summary")
async def api_summary() -> Any:
    return await fetch_json("GET", f"{COPILOT_URL}/summary")


@app.get("/api/operational-summary")
async def api_operational_summary() -> Any:
    return await fetch_json("GET", f"{COPILOT_URL}/operational-summary")


@app.get("/api/plan")
async def api_plan() -> Any:
    return await fetch_json("GET", f"{PLANNER_URL}/plan")


@app.get("/api/tasks")
async def api_tasks() -> Any:
    return await fetch_json("GET", f"{WORKFLOW_URL}/tasks")


@app.get("/api/approvals")
async def api_approvals() -> Any:
    return await fetch_json("GET", f"{WORKFLOW_URL}/approvals")


@app.get("/api/asset")
async def api_asset(asset_name: str) -> Any:
    return await fetch_json("GET", f"{RETRIEVAL_URL}/asset?asset_name={httpx.QueryParams({'asset_name': asset_name})['asset_name']}")


@app.post("/api/search")
async def api_search(request: Request) -> Any:
    payload = await request.json()
    return await fetch_json("POST", f"{RETRIEVAL_URL}/search", payload)


@app.post("/api/export-tasks")
async def api_export_tasks(request: Request) -> Any:
    payload = await request.json()
    return await fetch_json("POST", f"{PLANNER_URL}/export-tasks", payload)


@app.post("/api/copilot-query")
async def api_copilot_query(request: Request) -> Any:
    payload = await request.json()
    return await fetch_json("POST", f"{COPILOT_URL}/query", payload)
