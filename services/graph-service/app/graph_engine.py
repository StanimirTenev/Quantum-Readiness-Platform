"""Deterministic in-memory graph traversal over a QRP graph snapshot.

No graph database, no Neo4j -- pure Python over the existing JSON snapshot
(nodes: id/type/label/properties; edges: from/to/type). Implements the queries
the architecture (section 5) calls out: blast radius, trust chain, neighbors.
"""
from __future__ import annotations

from collections import deque
from typing import Any


def build_index(
    snapshot: dict[str, Any],
) -> tuple[dict[str, dict], dict[str, list[dict]], dict[str, list[dict]]]:
    """Return (nodes_by_id, outgoing_edges_by_from, incoming_edges_by_to)."""
    nodes: dict[str, dict] = {}
    for node in snapshot.get("nodes", []) or []:
        if isinstance(node, dict) and "id" in node:
            nodes[node["id"]] = node

    outgoing: dict[str, list[dict]] = {}
    incoming: dict[str, list[dict]] = {}
    for edge in snapshot.get("edges", []) or []:
        if not isinstance(edge, dict):
            continue
        src, dst = edge.get("from"), edge.get("to")
        if src is None or dst is None:
            continue
        outgoing.setdefault(src, []).append(edge)
        incoming.setdefault(dst, []).append(edge)

    return nodes, outgoing, incoming


def has_node(snapshot: dict[str, Any], node_id: str) -> bool:
    nodes, _, _ = build_index(snapshot)
    return node_id in nodes


def neighbors(
    snapshot: dict[str, Any],
    node_id: str,
    direction: str = "both",
    edge_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    nodes, outgoing, incoming = build_index(snapshot)
    wanted = set(edge_types) if edge_types else None
    results: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    def add(edge: dict, neighbor_id: str, way: str) -> None:
        if wanted is not None and edge.get("type") not in wanted:
            return
        key = (edge.get("type"), neighbor_id, way)
        if key in seen:
            return
        seen.add(key)
        results.append(
            {
                "edge_type": edge.get("type"),
                "direction": way,
                "node_id": neighbor_id,
                "node": nodes.get(neighbor_id),
            }
        )

    if direction in ("out", "both"):
        for edge in outgoing.get(node_id, []):
            add(edge, edge["to"], "out")
    if direction in ("in", "both"):
        for edge in incoming.get(node_id, []):
            add(edge, edge["from"], "in")

    return results


def blast_radius(
    snapshot: dict[str, Any],
    node_id: str,
    edge_types: list[str] | None = None,
    max_depth: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, dict]]:
    """Nodes affected if ``node_id`` is compromised = its transitive predecessors
    (things that depend on it), reached by walking edges backwards.

    Returns (affected[], nodes_by_id). Each affected entry has node_id, depth, node.
    """
    nodes, _outgoing, incoming = build_index(snapshot)
    wanted = set(edge_types) if edge_types else None

    depth: dict[str, int] = {}
    queue: deque[tuple[str, int]] = deque([(node_id, 0)])
    seen: set[str] = {node_id}

    while queue:
        current, current_depth = queue.popleft()
        if max_depth is not None and current_depth >= max_depth:
            continue
        for edge in incoming.get(current, []):
            if wanted is not None and edge.get("type") not in wanted:
                continue
            predecessor = edge["from"]
            next_depth = current_depth + 1
            if predecessor not in seen:
                seen.add(predecessor)
                depth[predecessor] = next_depth
                queue.append((predecessor, next_depth))
            elif predecessor in depth and depth[predecessor] > next_depth:
                depth[predecessor] = next_depth

    affected = [
        {"node_id": nid, "depth": depth[nid], "node": nodes.get(nid)}
        for nid in depth
    ]
    affected.sort(key=lambda item: (item["depth"], item["node_id"]))
    return affected, nodes


def evidence_path(
    snapshot: dict[str, Any],
    node_id: str,
) -> tuple[list[dict[str, Any]], dict[str, dict]]:
    """Resolve the attribution chain around a node:

        vulnerability -> location/service -> asset -> certificate/library/pipeline

    Returns an ordered list of {role, node_id, type, label, location} plus the
    node index. Works best starting from a CryptoFinding, but also from a
    Service / Asset / Certificate / Package.
    """
    nodes, outgoing, incoming = build_index(snapshot)
    if node_id not in nodes:
        return [], nodes

    def preds(nid: str, etype: str) -> list[str]:
        return [e["from"] for e in incoming.get(nid, []) if e.get("type") == etype]

    def succs(nid: str, etype: str) -> list[str]:
        return [e["to"] for e in outgoing.get(nid, []) if e.get("type") == etype]

    def first(items: list[str]) -> str | None:
        return items[0] if items else None

    finding = service = asset = crypto = None
    start_type = nodes[node_id].get("type")

    if start_type == "CryptoFinding":
        finding = node_id
        service = first(preds(node_id, "SERVICE_HAS_FINDING"))
        asset = first(preds(node_id, "HAS_FINDING"))
    elif start_type == "Service":
        service = node_id
    elif start_type == "Asset":
        asset = node_id
    elif start_type == "Certificate":
        crypto = node_id
        service = first(preds(node_id, "USES_CERTIFICATE"))
    elif start_type in ("Package", "Library"):
        crypto = node_id
        asset = first(preds(node_id, "HAS_PACKAGE"))
    elif start_type == "Pipeline":
        crypto = node_id

    if service and not asset:
        asset = first(preds(service, "RUNS"))
    if asset and not service:
        service = first(succs(asset, "RUNS"))
    if service and not crypto:
        crypto = first(succs(service, "USES_CERTIFICATE"))
    if asset and not crypto:
        crypto = first(succs(asset, "HAS_PACKAGE"))

    location = None
    if service and service in nodes:
        location = nodes[service].get("label")
    elif crypto and crypto in nodes:
        location = nodes[crypto].get("label")

    ordered = [("vulnerability", finding), ("service", service), ("asset", asset), ("crypto_object", crypto)]
    chain: list[dict[str, Any]] = []
    for role, nid in ordered:
        if nid and nid in nodes:
            n = nodes[nid]
            chain.append({
                "role": role,
                "node_id": nid,
                "type": n.get("type"),
                "label": n.get("label"),
                "location": location if role == "service" else None,
            })
    return chain, nodes


def trust_chain(
    snapshot: dict[str, Any],
    node_id: str,
) -> tuple[list[str], dict[str, dict]]:
    """Follow SIGNED_BY edges forward from a certificate to its root."""
    nodes, outgoing, _incoming = build_index(snapshot)
    chain = [node_id]
    seen = {node_id}
    current = node_id

    while True:
        signed_by = [e for e in outgoing.get(current, []) if e.get("type") == "SIGNED_BY"]
        if not signed_by:
            break
        issuer = signed_by[0]["to"]
        if issuer in seen:  # cycle guard
            break
        chain.append(issuer)
        seen.add(issuer)
        current = issuer

    return chain, nodes
