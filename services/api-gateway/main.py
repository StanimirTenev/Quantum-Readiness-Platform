from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, parse, request

from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="API Gateway", version="0.2.0")

INVENTORY_BASE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8000")
RISK_BASE_URL = os.getenv("RISK_ENGINE_URL", "http://risk-engine:8000")
COPILOT_BASE_URL = os.getenv("COPILOT_SERVICE_URL", "http://copilot-service:8000")
SCENARIO_ENGINE_BASE_URL = os.getenv("SCENARIO_ENGINE_URL", "http://scenario-engine:8000")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "api-gateway"}


@app.post("/api/scans/host")
def ingest_host_scan(payload: dict[str, Any], scenario: str = Query(default="public_timeline")) -> dict[str, Any]:
    return _ingest_scan("host", payload, scenario)


@app.post("/api/scans/network")
def ingest_network_scan(payload: dict[str, Any], scenario: str = Query(default="public_timeline")) -> dict[str, Any]:
    return _ingest_scan("network", payload, scenario)


@app.post("/api/scans/repo")
def ingest_repo_scan(payload: dict[str, Any], scenario: str = Query(default="public_timeline")) -> dict[str, Any]:
    return _ingest_scan("repo", payload, scenario)


@app.get("/api/assets")
def list_assets() -> list[dict[str, Any]]:
    return _request_json("GET", f"{INVENTORY_BASE_URL}/assets")


@app.get("/api/assets/{asset_id}")
def get_asset(asset_id: str) -> dict[str, Any]:
    return _request_json("GET", f"{INVENTORY_BASE_URL}/assets/{asset_id}")


@app.get("/api/assets/{asset_id}/risk")
def get_asset_risk(asset_id: str, scenario: str = Query(default="public_timeline")) -> dict[str, Any]:
    asset = _request_json("GET", f"{INVENTORY_BASE_URL}/assets/{asset_id}")
    risk_payload = _build_risk_payload_from_asset(asset, scenario)
    score = _request_json("POST", f"{RISK_BASE_URL}/score", payload=risk_payload)
    return {"asset_id": asset_id, "asset_name": asset.get("name"), "risk": score}


@app.post("/api/scenarios/run")
def run_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{SCENARIO_ENGINE_BASE_URL}/run", payload=payload)


@app.post("/api/copilot/query")
def copilot_query(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{COPILOT_BASE_URL}/query", payload=payload)


@app.post("/api/copilot/explain-risk")
def copilot_explain_risk(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{COPILOT_BASE_URL}/explain-risk", payload=payload)


@app.post("/api/copilot/generate-wave-plan")
def copilot_generate_wave_plan(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{COPILOT_BASE_URL}/generate-wave-plan", payload=payload)


def _ingest_scan(source: str, payload: dict[str, Any], scenario: str) -> dict[str, Any]:
    request_payload = dict(payload)
    request_payload["source"] = source
    endpoint = f"{INVENTORY_BASE_URL}/scans/ingest?{parse.urlencode({'scenario': scenario, 'auto_score': 'true'})}"
    return _request_json("POST", endpoint, payload=request_payload)


def _build_risk_payload_from_asset(asset: dict[str, Any], scenario: str) -> dict[str, Any]:
    criticality = float(asset.get("criticality") or 3)
    vendor_lock_in = 3.0 if asset.get("vendor") else 1.0
    confidentiality_lifetime = 4.0 if (asset.get("lifecycle_years") or 0) >= 7 else 3.0
    blast_radius = 4.0 if asset.get("environment") == "production" else 3.0

    return {
        "criticality": criticality,
        "confidentiality_lifetime": confidentiality_lifetime,
        "quantum_exposure": 3.0,
        "blast_radius": blast_radius,
        "vendor_lock_in": vendor_lock_in,
        "migration_difficulty": 3.0,
        "scenario": scenario,
    }


def _request_json(method: str, url: str, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers = {"Accept": "application/json"}

    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url=url, method=method, data=body, headers=headers)

    try:
        with request.urlopen(req, timeout=10) as response:
            data = response.read().decode("utf-8")
            return json.loads(data) if data else {}
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise HTTPException(status_code=exc.code, detail=detail or "Upstream service error") from exc
    except error.URLError as exc:
        raise HTTPException(status_code=502, detail=f"Upstream unavailable: {exc.reason}") from exc
