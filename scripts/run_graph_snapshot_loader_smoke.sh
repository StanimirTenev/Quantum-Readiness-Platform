#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SNAPSHOT_PATH="$ROOT_DIR/reports/graph/latest/graph-snapshot.json"
REPORT_PATH="$ROOT_DIR/reports/graph/latest/graph-snapshot-loader-report.md"

if [[ ! -f "$SNAPSHOT_PATH" ]]; then
  echo "ERROR: required snapshot file is missing: $SNAPSHOT_PATH" >&2
  exit 1
fi

export ROOT_DIR SNAPSHOT_PATH REPORT_PATH

python - <<'PY'
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from tools.graph_projection.graph_snapshot_loader import load_graph_snapshot, summarize_graph_snapshot

root_dir = Path(os.environ["ROOT_DIR"])
snapshot_path = Path(os.environ["SNAPSHOT_PATH"])
report_path = Path(os.environ["REPORT_PATH"])

snapshot = load_graph_snapshot(snapshot_path)
summary = summarize_graph_snapshot(snapshot)

def _display_items(values: list[str]) -> str:
    return ", ".join(values) if values else "none"

report_lines = [
    "# Graph Snapshot Loader Smoke Report",
    "",
    f"- utc_timestamp: {datetime.now(timezone.utc).isoformat()}",
    f"- snapshot_path: {snapshot_path.relative_to(root_dir)}",
    f"- graph_schema_version: {summary['graph_schema_version']}",
    f"- node_count: {summary['node_count']}",
    f"- edge_count: {summary['edge_count']}",
    f"- warning_count: {summary['warning_count']}",
    f"- node_types: {_display_items(summary['node_types'])}",
    f"- edge_types: {_display_items(summary['edge_types'])}",
    "- result: PASS",
    "",
    "This smoke validates the read-only Graph Snapshot Loader helper only.",
    "",
    "This smoke does not implement or start a Graph API.",
    "",
]

report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\n".join(report_lines), encoding="utf-8")
PY

echo "Graph snapshot loader smoke complete."
echo "- $REPORT_PATH"
