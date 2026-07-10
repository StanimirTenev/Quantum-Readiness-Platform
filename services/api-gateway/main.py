from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from tools.graph_projection.graph_snapshot_loader import (
    GraphSnapshotLoaderError,
    load_graph_snapshot,
    summarize_graph_snapshot,
)

import demo_seed

app = FastAPI(title="API Gateway", version="0.2.0")

# Allow the local web-ui (a browser frontend) to call the gateway. Configurable
# via CORS_ALLOW_ORIGINS (comma-separated); defaults to permissive for local dev.
_cors_origins = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INVENTORY_BASE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://inventory-service:8000")
RISK_BASE_URL = os.getenv("RISK_ENGINE_URL", "http://risk-engine:8000")
COPILOT_BASE_URL = os.getenv("COPILOT_SERVICE_URL", "http://copilot-service:8000")
SCENARIO_ENGINE_BASE_URL = os.getenv("SCENARIO_ENGINE_URL", "http://scenario-engine:8000")
POLICY_ENGINE_BASE_URL = os.getenv("POLICY_ENGINE_URL", "http://policy-engine:8000")
CRYPTO_FINGERPRINT_BASE_URL = os.getenv("CRYPTO_FINGERPRINT_URL", "http://crypto-fingerprint-service:8000")
EVIDENCE_NORMALIZER_BASE_URL = os.getenv("EVIDENCE_NORMALIZER_URL", "http://evidence-normalizer:8000")
INTEGRATION_SERVICE_BASE_URL = os.getenv("INTEGRATION_SERVICE_URL", "http://integration-service:8000")
PQC_READINESS_BASE_URL = os.getenv("PQC_READINESS_URL", "http://pqc-readiness-service:8000")
GRAPH_SERVICE_BASE_URL = os.getenv("GRAPH_SERVICE_URL", "http://graph-service:8000")
FINDING_ATTRIBUTION_BASE_URL = os.getenv("FINDING_ATTRIBUTION_URL", "http://finding-attribution-service:8000")
GRAPH_SNAPSHOT_DEFAULT_PATH = "reports/graph/latest/graph-snapshot.json"


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


@app.post("/api/scans/windows")
def ingest_windows_scan(payload: dict[str, Any], scenario: str = Query(default="public_timeline")) -> dict[str, Any]:
    """Persist a Windows host evidence document (from the windows-host-agent).

    The raw redacted/aggregate document is forwarded as-is; the inventory service
    maps it to the ingest contract (source is fixed to "host" there)."""
    endpoint = f"{INVENTORY_BASE_URL}/scans/ingest/windows?{parse.urlencode({'scenario': scenario, 'auto_score': 'true'})}"
    return _request_json("POST", endpoint, payload=payload)


@app.post("/api/demo/load")
def demo_load() -> dict[str, Any]:
    """Seeds the small, realistic demo dataset (host/network/repo evidence +
    a vendor document) into the currently-running stack for the web-ui's
    "Load Demo" button. See demo_seed.py. Best-effort: each step is recorded
    independently so a single failure doesn't hide the others. Idempotent:
    an asset that's already present is skipped rather than re-ingested, so
    clicking "Load Demo" twice doesn't create duplicate scans/findings."""
    steps: list[dict[str, Any]] = []

    try:
        existing_assets = _request_json("GET", f"{INVENTORY_BASE_URL}/assets")
    except HTTPException:
        existing_assets = []
    existing_names = {a.get("name") for a in existing_assets} if isinstance(existing_assets, list) else set()

    for source, asset_name, payload in demo_seed.load_demo_scan_payloads():
        if asset_name in existing_names:
            steps.append({"step": f"ingest_{source}", "status": "skipped", "asset_name": asset_name, "detail": "already loaded"})
            continue
        try:
            _ingest_scan(source, payload, "public_timeline")
            steps.append({"step": f"ingest_{source}", "status": "ok", "asset_name": asset_name})
        except HTTPException as exc:
            steps.append({"step": f"ingest_{source}", "status": "error", "asset_name": asset_name, "detail": str(exc.detail)})

    try:
        demo_seed.write_demo_doc_index()
        steps.append({"step": "doc_index", "status": "ok"})
    except OSError as exc:
        steps.append({"step": "doc_index", "status": "error", "detail": str(exc)})

    graph_path = Path(os.getenv("GRAPH_SNAPSHOT_PATH", demo_seed.GRAPH_SNAPSHOT_DEFAULT_PATH))
    graph_ok, graph_message = demo_seed.build_demo_graph_snapshot(graph_path)
    steps.append({"step": "graph_snapshot", "status": "ok" if graph_ok else "error", "detail": graph_message})

    overall = "ok" if all(s["status"] in ("ok", "skipped") for s in steps) else "partial"
    return {"overall": overall, "steps": steps}


@app.get("/api/demo/status")
def demo_status() -> dict[str, Any]:
    """Whether the demo dataset (see /api/demo/load) currently appears
    loaded in the running stack -- used by the web-ui to decide whether to
    show "Load Demo" or a status summary."""
    try:
        assets = _request_json("GET", f"{INVENTORY_BASE_URL}/assets")
    except HTTPException:
        assets = []
    asset_names = {a.get("name") for a in assets} if isinstance(assets, list) else set()
    present = [name for name in demo_seed.DEMO_ASSET_NAMES if name in asset_names]
    missing = [name for name in demo_seed.DEMO_ASSET_NAMES if name not in asset_names]

    graph_path = Path(os.getenv("GRAPH_SNAPSHOT_PATH", demo_seed.GRAPH_SNAPSHOT_DEFAULT_PATH))
    return {
        "loaded": len(missing) == 0,
        "assets_present": present,
        "assets_missing": missing,
        "asset_count_total": len(asset_names),
        "graph_snapshot_present": graph_path.exists(),
        "doc_index_present": demo_seed.DOC_INDEX_DEFAULT_PATH.exists(),
    }


@app.get("/api/assets")
def list_assets() -> list[dict[str, Any]]:
    return _request_json("GET", f"{INVENTORY_BASE_URL}/assets")


@app.get("/api/assets/{asset_id}")
def get_asset(asset_id: str) -> dict[str, Any]:
    return _request_json("GET", f"{INVENTORY_BASE_URL}/assets/{asset_id}")


@app.get("/api/assets/{asset_id}/history")
def get_asset_history(asset_id: str) -> dict[str, Any]:
    """Chronological risk trend for an asset across persisted scans."""
    return _request_json("GET", f"{INVENTORY_BASE_URL}/assets/{asset_id}/history")


@app.get("/api/assets/{asset_id}/risk")
def get_asset_risk(asset_id: str, scenario: str = Query(default="public_timeline")) -> dict[str, Any]:
    asset = _request_json("GET", f"{INVENTORY_BASE_URL}/assets/{asset_id}")
    risk_payload = _build_risk_payload_from_asset(asset, scenario)
    score = _request_json("POST", f"{RISK_BASE_URL}/score", payload=risk_payload)
    return {"asset_id": asset_id, "asset_name": asset.get("name"), "risk": score}


@app.post("/api/scenarios/run")
def run_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{SCENARIO_ENGINE_BASE_URL}/run", payload=payload)


@app.get("/graph/snapshot")
def get_graph_snapshot() -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    response = {
        "graph_schema_version": snapshot["graph_schema_version"],
        "nodes": snapshot["nodes"],
        "edges": snapshot["edges"],
        "warnings": snapshot["warnings"],
    }
    if "metadata" in snapshot:
        response["metadata"] = snapshot["metadata"]
    return response


@app.get("/graph/summary")
def get_graph_summary() -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    return dict(summarize_graph_snapshot(snapshot))


@app.get("/graph/nodes")
def get_graph_nodes(node_type: str | None = Query(default=None)) -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    nodes = snapshot["nodes"]
    if node_type:
        nodes = [node for node in nodes if node.get("type") == node_type]
    return {"nodes": nodes}


@app.get("/graph/edges")
def get_graph_edges(edge_type: str | None = Query(default=None)) -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    edges = snapshot["edges"]
    if edge_type:
        edges = [edge for edge in edges if edge.get("type") == edge_type]
    return {"edges": edges}


@app.get("/graph/warnings")
def get_graph_warnings() -> dict[str, Any]:
    snapshot = _load_graph_snapshot_or_raise()
    return {"warnings": snapshot["warnings"]}




@app.post("/api/policies/evaluate")
def evaluate_policy(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{POLICY_ENGINE_BASE_URL}/evaluate", payload=payload)


@app.get("/api/algorithms")
def list_algorithms() -> dict[str, Any]:
    return _request_json("GET", f"{CRYPTO_FINGERPRINT_BASE_URL}/algorithms")


@app.post("/api/fingerprint")
def fingerprint(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{CRYPTO_FINGERPRINT_BASE_URL}/fingerprint", payload=payload)


@app.post("/api/normalize")
def normalize_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{EVIDENCE_NORMALIZER_BASE_URL}/normalize", payload=payload)


@app.get("/api/readiness-states")
def readiness_states() -> dict[str, Any]:
    return _request_json("GET", f"{PQC_READINESS_BASE_URL}/readiness-states")


@app.post("/api/pqc-readiness")
def pqc_readiness(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{PQC_READINESS_BASE_URL}/classify", payload=payload)


@app.post("/api/assess")
def assess(payload: dict[str, Any]) -> dict[str, Any]:
    """Chain the deterministic analysis pipeline for one asset:
    crypto-fingerprint -> pqc-readiness -> (optional) risk-engine."""
    asset_name = payload.get("asset_name") or "asset"

    fingerprint_request: dict[str, Any] = {"asset_name": asset_name}
    for key in ("algorithms", "tls_metadata", "crypto_evidence"):
        if key in payload:
            fingerprint_request[key] = payload[key]
    fingerprint = _request_json(
        "POST", f"{CRYPTO_FINGERPRINT_BASE_URL}/fingerprint", payload=fingerprint_request
    )

    readiness = _request_json(
        "POST",
        f"{PQC_READINESS_BASE_URL}/classify",
        payload={
            "asset_name": asset_name,
            "findings": fingerprint.get("findings", []),
            "vendor_blocked": payload.get("vendor_blocked", False),
            "hybrid_supported": payload.get("hybrid_supported", False),
        },
    )

    result: dict[str, Any] = {
        "asset_name": asset_name,
        "fingerprint": {"summary": fingerprint.get("summary"), "findings": fingerprint.get("findings", [])},
        "pqc_readiness": readiness,
        "risk": None,
        "pipeline": ["crypto-fingerprint-service", "pqc-readiness-service"],
    }

    attribution_request: dict[str, Any] = {
        "asset_name": asset_name,
        "application": payload.get("application"),
        "findings": fingerprint.get("findings", []),
    }
    for key in ("tls_metadata", "crypto_evidence", "network_evidence", "host_evidence"):
        if key in payload:
            attribution_request[key] = payload[key]
    attribution = _request_json(
        "POST", f"{FINDING_ATTRIBUTION_BASE_URL}/attribute", payload=attribution_request
    )
    result["attribution"] = attribution
    result["pipeline"].append("finding-attribution-service")

    risk_factors = payload.get("risk_factors")
    if isinstance(risk_factors, dict) and risk_factors:
        risk_request: dict[str, Any] = {"asset_name": asset_name, "vendor_blocked": payload.get("vendor_blocked", False)}
        risk_request.update(risk_factors)
        for key in ("tls_metadata", "crypto_evidence", "scenario", "dependency_count", "environment"):
            if key in payload:
                risk_request[key] = payload[key]
        result["risk"] = _request_json("POST", f"{RISK_BASE_URL}/score", payload=risk_request)
        result["pipeline"].append("risk-engine")

    return result


@app.post("/api/attribute")
def attribute_findings(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{FINDING_ATTRIBUTION_BASE_URL}/attribute", payload=payload)


@app.get("/api/graph/queries")
def graph_queries() -> dict[str, Any]:
    return _request_json("GET", f"{GRAPH_SERVICE_BASE_URL}/queries")


@app.post("/api/graph/blast-radius")
def graph_blast_radius(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{GRAPH_SERVICE_BASE_URL}/blast-radius", payload=payload)


@app.post("/api/graph/trust-chain")
def graph_trust_chain(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{GRAPH_SERVICE_BASE_URL}/trust-chain", payload=payload)


@app.post("/api/graph/neighbors")
def graph_neighbors(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{GRAPH_SERVICE_BASE_URL}/neighbors", payload=payload)


@app.post("/api/graph/evidence-path")
def graph_evidence_path(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{GRAPH_SERVICE_BASE_URL}/evidence-path", payload=payload)


@app.get("/api/integrations")
def list_integrations() -> dict[str, Any]:
    return _request_json("GET", f"{INTEGRATION_SERVICE_BASE_URL}/integrations")


@app.post("/api/integrations/dry-run")
def integrations_dry_run(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{INTEGRATION_SERVICE_BASE_URL}/dry-run", payload=payload)

@app.post("/api/copilot/query")
def copilot_query(payload: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{COPILOT_BASE_URL}/query", payload=payload)


@app.get("/api/copilot/narrate/{asset_name:path}")
def copilot_narrate(asset_name: str) -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/narrate/{asset_name}")


@app.get("/api/copilot/change-plan/{asset_name:path}")
def copilot_change_plan(asset_name: str) -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/change-plan/{asset_name}")


@app.get("/api/copilot/discover")
def copilot_discover() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/discover")


@app.get("/api/copilot/vendor-intelligence")
def copilot_vendor_intelligence() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/vendor-intelligence")


@app.get("/api/copilot/migration-plan")
def copilot_migration_plan() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/migration-plan")


@app.get("/api/copilot/plan-summary")
def copilot_plan_summary() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/plan-summary")


@app.get("/api/copilot/workflow-summary")
def copilot_workflow_summary() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/workflow-summary")


@app.get("/api/copilot/operational-summary")
def copilot_operational_summary() -> dict[str, Any]:
    return _request_json("GET", f"{COPILOT_BASE_URL}/operational-summary")


def _load_graph_snapshot_or_raise() -> dict[str, Any]:
    snapshot_path = os.getenv("GRAPH_SNAPSHOT_PATH", GRAPH_SNAPSHOT_DEFAULT_PATH)
    try:
        return load_graph_snapshot(snapshot_path)
    except GraphSnapshotLoaderError as exc:
        raise HTTPException(status_code=400, detail={"error": exc.code}) from exc


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
