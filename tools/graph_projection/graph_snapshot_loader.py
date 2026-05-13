"""Read-only loader for local graph snapshot JSON files."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from urllib.parse import urlparse

REQUIRED_TOP_LEVEL_KEYS = {"graph_schema_version", "nodes", "edges", "warnings"}


class GraphSnapshotLoaderError(ValueError):
    code = "graph_snapshot_loader_error"

    def __init__(self, message: str):
        super().__init__(f"{self.code}: {message}")


class GraphSnapshotUnsafePathError(GraphSnapshotLoaderError):
    code = "graph_snapshot_unsafe_path"


class GraphSnapshotMissingError(GraphSnapshotLoaderError):
    code = "graph_snapshot_missing"


class GraphSnapshotInvalidJsonError(GraphSnapshotLoaderError):
    code = "graph_snapshot_invalid_json"


class GraphSnapshotMissingRequiredKeysError(GraphSnapshotLoaderError):
    code = "graph_snapshot_missing_required_keys"


class GraphSnapshotDuplicateNodeIdError(GraphSnapshotLoaderError):
    code = "graph_snapshot_duplicate_node_id"


class GraphSnapshotInvalidEdgeReferenceError(GraphSnapshotLoaderError):
    code = "graph_snapshot_invalid_edge_reference"


def _ensure_local_path(path: str | Path) -> Path:
    path_text = str(path)
    parsed = urlparse(path_text)
    if parsed.scheme in {"http", "https"}:
        raise GraphSnapshotUnsafePathError("remote URLs are not supported")
    return Path(path)


def load_graph_snapshot(path: str | Path) -> dict:
    """Load and validate a graph snapshot JSON file from local filesystem."""
    snapshot_path = _ensure_local_path(path)

    if not snapshot_path.exists():
        raise GraphSnapshotMissingError(f"snapshot file does not exist: {snapshot_path}")

    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GraphSnapshotInvalidJsonError("snapshot is not valid JSON") from exc

    if not isinstance(snapshot, dict):
        raise GraphSnapshotMissingRequiredKeysError("top-level object must be a JSON object")

    missing_keys = sorted(REQUIRED_TOP_LEVEL_KEYS - set(snapshot.keys()))
    if missing_keys:
        raise GraphSnapshotMissingRequiredKeysError("missing " + ", ".join(missing_keys))

    if not isinstance(snapshot["nodes"], list) or not isinstance(snapshot["edges"], list) or not isinstance(snapshot["warnings"], list):
        raise GraphSnapshotMissingRequiredKeysError("nodes, edges, and warnings must be lists")

    node_ids: list[str] = []
    for node in snapshot["nodes"]:
        if not isinstance(node, dict) or "id" not in node or "type" not in node:
            raise GraphSnapshotMissingRequiredKeysError("each node must contain id and type")
        node_id = node["id"]
        if node_id in node_ids:
            raise GraphSnapshotDuplicateNodeIdError(f"duplicate node id: {node_id}")
        node_ids.append(node_id)

    node_id_set = set(node_ids)
    for edge in snapshot["edges"]:
        if not isinstance(edge, dict) or "type" not in edge:
            raise GraphSnapshotMissingRequiredKeysError("each edge must contain source/target and type")

        edge_source = edge.get("from", edge.get("source"))
        edge_target = edge.get("to", edge.get("target"))
        if edge_source is None or edge_target is None:
            raise GraphSnapshotMissingRequiredKeysError("each edge must contain source/target and type")

        if edge_source not in node_id_set or edge_target not in node_id_set:
            raise GraphSnapshotInvalidEdgeReferenceError("edge references missing node id")

    return snapshot


def summarize_graph_snapshot(snapshot: dict) -> dict:
    """Build a compact summary for a previously loaded graph snapshot."""
    summary = {
        "graph_schema_version": snapshot["graph_schema_version"],
        "node_count": len(snapshot["nodes"]),
        "edge_count": len(snapshot["edges"]),
        "warning_count": len(snapshot["warnings"]),
        "node_types": sorted({node.get("type") for node in snapshot["nodes"]}),
        "edge_types": sorted({edge.get("type") for edge in snapshot["edges"]}),
    }
    return MappingProxyType(summary)
