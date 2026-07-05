from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import app.main as main

client = TestClient(main.app)

# A small graph: asset -RUNS-> service -USES_CERTIFICATE-> leaf -SIGNED_BY-> root
SNAPSHOT = {
    "graph_schema_version": "0.1",
    "nodes": [
        {"id": "asset:a", "type": "Asset", "label": "asset-a"},
        {"id": "service:s", "type": "Service", "label": "svc"},
        {"id": "cert:leaf", "type": "Certificate", "label": "leaf"},
        {"id": "cert:root", "type": "Certificate", "label": "root-ca"},
        {"id": "pkg:x", "type": "Package", "label": "openssl"},
    ],
    "edges": [
        {"from": "asset:a", "to": "service:s", "type": "RUNS"},
        {"from": "service:s", "to": "cert:leaf", "type": "USES_CERTIFICATE"},
        {"from": "cert:leaf", "to": "cert:root", "type": "SIGNED_BY"},
        {"from": "asset:a", "to": "pkg:x", "type": "HAS_PACKAGE"},
    ],
    "warnings": [],
}


def _post(path, node_id, **extra):
    return client.post(path, json={"node_id": node_id, "snapshot": SNAPSHOT, **extra})


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "graph-service"}


def test_queries_lists_supported_queries() -> None:
    response = client.get("/queries")
    assert response.status_code == 200
    names = {q["name"] for q in response.json()["queries"]}
    assert names == {"blast-radius", "trust-chain", "neighbors"}


def test_blast_radius_of_root_ca_reaches_asset() -> None:
    response = _post("/blast-radius", "cert:root")
    assert response.status_code == 200
    data = response.json()
    ids = data["affected_node_ids"]
    # compromise the root CA -> leaf, service and asset are all affected
    assert set(ids) == {"cert:leaf", "service:s", "asset:a"}
    depth = {item["node_id"]: item["depth"] for item in data["affected"]}
    assert depth["cert:leaf"] == 1
    assert depth["service:s"] == 2
    assert depth["asset:a"] == 3


def test_blast_radius_edge_type_filter() -> None:
    response = _post("/blast-radius", "cert:root", edge_types=["SIGNED_BY"])
    assert response.status_code == 200
    assert response.json()["affected_node_ids"] == ["cert:leaf"]


def test_blast_radius_max_depth() -> None:
    response = _post("/blast-radius", "cert:root", max_depth=1)
    assert response.status_code == 200
    assert response.json()["affected_node_ids"] == ["cert:leaf"]


def test_blast_radius_leaf_asset_has_no_predecessors() -> None:
    response = _post("/blast-radius", "asset:a")
    assert response.status_code == 200
    assert response.json()["affected_count"] == 0


def test_trust_chain_follows_signed_by_to_root() -> None:
    response = _post("/trust-chain", "cert:leaf")
    assert response.status_code == 200
    data = response.json()
    assert data["chain"] == ["cert:leaf", "cert:root"]
    assert data["root"] == "cert:root"
    assert data["length"] == 2


def test_neighbors_both_directions() -> None:
    response = _post("/neighbors", "service:s")
    assert response.status_code == 200
    data = response.json()
    assert data["neighbor_count"] == 2
    pairs = {(n["direction"], n["node_id"]) for n in data["neighbors"]}
    assert ("out", "cert:leaf") in pairs
    assert ("in", "asset:a") in pairs


def test_neighbors_out_only() -> None:
    response = _post("/neighbors", "asset:a", direction="out")
    assert response.status_code == 200
    ids = {n["node_id"] for n in response.json()["neighbors"]}
    assert ids == {"service:s", "pkg:x"}


def test_unknown_node_returns_404() -> None:
    response = _post("/blast-radius", "does:not:exist")
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "node_not_found"


def test_missing_snapshot_path_returns_404(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_SNAPSHOT_PATH", "reports/graph/latest/does-not-exist.json")
    response = client.post("/blast-radius", json={"node_id": "x"})
    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "graph_snapshot_missing"


def test_remote_snapshot_path_rejected(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_SNAPSHOT_PATH", "http://example.com/snap.json")
    response = client.post("/trust-chain", json={"node_id": "x"})
    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "graph_snapshot_unsafe_path"
