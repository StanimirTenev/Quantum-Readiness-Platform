from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app import graph_engine

app = FastAPI(title="Graph Service", version="0.1.0")

CONTRACT_VERSION = "graph-query-v1"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SNAPSHOT = REPO_ROOT / "reports" / "graph" / "latest" / "graph-snapshot.json"


def load_snapshot(inline: dict[str, Any] | None) -> dict[str, Any]:
    """Use an inline snapshot if provided, else load from GRAPH_SNAPSHOT_PATH
    (or the default projected snapshot). Local files only."""
    if inline is not None:
        return inline

    raw_path = os.getenv("GRAPH_SNAPSHOT_PATH")
    if raw_path and raw_path.lower().startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail={"error": "graph_snapshot_unsafe_path"})

    path = Path(raw_path) if raw_path else DEFAULT_SNAPSHOT
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise HTTPException(status_code=404, detail={"error": "graph_snapshot_missing"})
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail={"error": "graph_snapshot_invalid_json"}) from exc


def _require_node(snapshot: dict[str, Any], node_id: str) -> None:
    if not graph_engine.has_node(snapshot, node_id):
        raise HTTPException(status_code=404, detail={"error": "node_not_found", "node_id": node_id})


class BlastRadiusRequest(BaseModel):
    node_id: str = Field(..., min_length=1)
    edge_types: list[str] | None = None
    max_depth: int | None = Field(default=None, ge=1)
    snapshot: dict[str, Any] | None = None


class TrustChainRequest(BaseModel):
    node_id: str = Field(..., min_length=1)
    snapshot: dict[str, Any] | None = None


class NeighborsRequest(BaseModel):
    node_id: str = Field(..., min_length=1)
    direction: str = Field(default="both", pattern="^(in|out|both)$")
    edge_types: list[str] | None = None
    snapshot: dict[str, Any] | None = None


class EvidencePathRequest(BaseModel):
    node_id: str = Field(..., min_length=1)
    snapshot: dict[str, Any] | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "graph-service"}


@app.get("/queries")
def queries() -> dict[str, Any]:
    return {
        "contract_version": CONTRACT_VERSION,
        "queries": [
            {"name": "blast-radius", "method": "POST", "path": "/blast-radius",
             "description": "Nodes affected if a node is compromised (transitive predecessors)."},
            {"name": "trust-chain", "method": "POST", "path": "/trust-chain",
             "description": "Certificate chain to root, following SIGNED_BY edges."},
            {"name": "neighbors", "method": "POST", "path": "/neighbors",
             "description": "Direct neighbours of a node, filtered by direction and edge type."},
            {"name": "evidence-path", "method": "POST", "path": "/evidence-path",
             "description": "Attribution chain: vulnerability -> service/location -> asset -> certificate/library/pipeline."},
        ],
    }


@app.post("/blast-radius")
def blast_radius(request: BlastRadiusRequest) -> dict[str, Any]:
    snapshot = load_snapshot(request.snapshot)
    _require_node(snapshot, request.node_id)
    affected, nodes = graph_engine.blast_radius(
        snapshot, request.node_id, edge_types=request.edge_types, max_depth=request.max_depth
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "node_id": request.node_id,
        "node": nodes.get(request.node_id),
        "affected_count": len(affected),
        "affected": affected,
        "affected_node_ids": [item["node_id"] for item in affected],
    }


@app.post("/trust-chain")
def trust_chain(request: TrustChainRequest) -> dict[str, Any]:
    snapshot = load_snapshot(request.snapshot)
    _require_node(snapshot, request.node_id)
    chain, nodes = graph_engine.trust_chain(snapshot, request.node_id)
    return {
        "contract_version": CONTRACT_VERSION,
        "node_id": request.node_id,
        "chain": chain,
        "length": len(chain),
        "root": chain[-1] if chain else None,
        "chain_nodes": [nodes.get(cid) for cid in chain],
    }


@app.post("/evidence-path")
def evidence_path(request: EvidencePathRequest) -> dict[str, Any]:
    snapshot = load_snapshot(request.snapshot)
    _require_node(snapshot, request.node_id)
    chain, _nodes = graph_engine.evidence_path(snapshot, request.node_id)
    return {
        "contract_version": CONTRACT_VERSION,
        "node_id": request.node_id,
        "length": len(chain),
        "chain": chain,
        "chain_labels": [f"{c['role']}: {c['label']}" for c in chain],
    }


@app.post("/neighbors")
def neighbors(request: NeighborsRequest) -> dict[str, Any]:
    snapshot = load_snapshot(request.snapshot)
    _require_node(snapshot, request.node_id)
    result = graph_engine.neighbors(
        snapshot, request.node_id, direction=request.direction, edge_types=request.edge_types
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "node_id": request.node_id,
        "direction": request.direction,
        "neighbor_count": len(result),
        "neighbors": result,
    }
