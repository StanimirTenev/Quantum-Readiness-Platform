"""Reads the JSON graph snapshot produced by tools/graph_projection, the same
file graph-service and api-gateway read via GRAPH_SNAPSHOT_PATH. Local file
only, best-effort: a missing/invalid snapshot is not an error, since the
graph is one of several evidence sources Discovery Analyst consults."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SNAPSHOT_PATH = REPO_ROOT / "reports" / "graph" / "latest" / "graph-snapshot.json"


def load_graph_snapshot() -> dict[str, Any] | None:
    raw_path = os.getenv("GRAPH_SNAPSHOT_PATH")
    if raw_path and raw_path.lower().startswith(("http://", "https://")):
        return None

    path = Path(raw_path) if raw_path else DEFAULT_SNAPSHOT_PATH
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
