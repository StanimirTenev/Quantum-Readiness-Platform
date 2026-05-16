#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="$ROOT_DIR/reports/graph/latest/graph-api-readonly-smoke-report.md"
SNAPSHOT_PATH="${GRAPH_SNAPSHOT_PATH:-$ROOT_DIR/reports/graph/latest/graph-snapshot.json}"

export ROOT_DIR REPORT_PATH SNAPSHOT_PATH

python - <<'PY'
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
import sys

from fastapi.testclient import TestClient

root_dir = Path(os.environ["ROOT_DIR"])
report_path = Path(os.environ["REPORT_PATH"])
snapshot_path = Path(os.environ["SNAPSHOT_PATH"])
os.environ["GRAPH_SNAPSHOT_PATH"] = str(snapshot_path)

sys.path.append(str(root_dir / "services" / "api-gateway"))
import main

client = TestClient(main.app)

results = {}
for path in ["/graph/snapshot", "/graph/summary", "/graph/nodes", "/graph/edges", "/graph/warnings"]:
    response = client.get(path)
    results[path] = response.status_code
    if response.status_code != 200:
        raise SystemExit(f"Smoke failed for {path}: {response.status_code} {response.text}")

summary = client.get("/graph/summary").json()
nodes = client.get("/graph/nodes").json()["nodes"]
edges = client.get("/graph/edges").json()["edges"]

if nodes:
    sample_node_type = nodes[0].get("type")
    if sample_node_type:
        filtered_nodes = client.get(f"/graph/nodes?node_type={sample_node_type}")
        if filtered_nodes.status_code != 200:
            raise SystemExit(f"Smoke failed for /graph/nodes filter: {filtered_nodes.status_code} {filtered_nodes.text}")
        if any(node.get("type") != sample_node_type for node in filtered_nodes.json().get("nodes", [])):
            raise SystemExit("Smoke failed: /graph/nodes filter returned non-matching node types")

if edges:
    sample_edge_type = edges[0].get("type")
    if sample_edge_type:
        filtered_edges = client.get(f"/graph/edges?edge_type={sample_edge_type}")
        if filtered_edges.status_code != 200:
            raise SystemExit(f"Smoke failed for /graph/edges filter: {filtered_edges.status_code} {filtered_edges.text}")
        if any(edge.get("type") != sample_edge_type for edge in filtered_edges.json().get("edges", [])):
            raise SystemExit("Smoke failed: /graph/edges filter returned non-matching edge types")

for method, path in [
    ("post", "/graph/snapshot"),
    ("put", "/graph/snapshot"),
    ("patch", "/graph/snapshot"),
    ("delete", "/graph/snapshot"),
    ("post", "/graph/nodes"),
    ("delete", "/graph/nodes"),
]:
    mutation_response = client.request(method.upper(), path, json={})
    if 200 <= mutation_response.status_code < 300:
        raise SystemExit(f"Smoke failed: mutation endpoint unexpectedly succeeded: {method.upper()} {path}")

report_lines = [
    "# Graph API Read-only Smoke Report",
    "",
    f"- utc_timestamp: {datetime.now(timezone.utc).isoformat()}",
    f"- snapshot_path: {snapshot_path}",
    f"- graph_schema_version: {summary['graph_schema_version']}",
    f"- node_count: {summary['node_count']}",
    f"- edge_count: {summary['edge_count']}",
    f"- warning_count: {summary['warning_count']}",
    "- endpoints_checked: /graph/snapshot, /graph/summary, /graph/nodes, /graph/edges, /graph/warnings",
    "- result: PASS",
    "",
    "Graph API remains read-only over the local JSON snapshot.",
    "No graph database, Neo4j, traversal engine, blast-radius engine, or mutation endpoint is used.",
    "",
]

report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\n".join(report_lines), encoding="utf-8")
PY

echo "Graph API read-only smoke complete."
echo "- $REPORT_PATH"
