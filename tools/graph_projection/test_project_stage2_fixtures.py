import json
import re
from pathlib import Path

from tools.graph_projection import project_stage2_fixtures as projector


HOST_FIXTURE = Path("services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json")
NETWORK_FIXTURE = Path("services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json")


UUID_LIKE_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def _build_snapshot():
    host = json.loads(HOST_FIXTURE.read_text())
    network = json.loads(NETWORK_FIXTURE.read_text())

    nodes, edges, warnings = {}, {}, []
    projector.project_host(host, nodes, edges, warnings)
    projector.project_network(network, nodes, edges, warnings)

    fixture_refs = [str(HOST_FIXTURE), str(NETWORK_FIXTURE)]
    snapshot_material = "|".join(fixture_refs + sorted(nodes) + sorted(edges))
    return {
        "graph_schema_version": "0.1",
        "projection_version": "0.1.0",
        "graph_snapshot_id": projector.hashlib.sha256(snapshot_material.encode()).hexdigest()[:16],
        "generated_at": projector.iso_now(),
        "source": "stage2_fixture_projection_smoke",
        "inputs": {"fixtures": fixture_refs},
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "warnings": warnings,
    }


def test_snapshot_top_level_shape_and_collections():
    snapshot = _build_snapshot()

    for field in [
        "graph_schema_version",
        "projection_version",
        "graph_snapshot_id",
        "generated_at",
        "source",
        "inputs",
        "nodes",
        "edges",
        "warnings",
    ]:
        assert field in snapshot

    assert isinstance(snapshot["nodes"], list)
    assert isinstance(snapshot["edges"], list)
    assert isinstance(snapshot["warnings"], list)


def test_expected_graph_object_types_exist_from_stage2_fixtures():
    snapshot = _build_snapshot()
    node_types = {node["type"] for node in snapshot["nodes"]}

    assert "Asset" in node_types
    assert "Package" in node_types
    assert "ConfigFile" in node_types
    assert "Service" in node_types
    assert "Certificate" in node_types
    host = json.loads(HOST_FIXTURE.read_text())
    private_key_files = host.get("crypto_evidence", {}).get("private_key_files", [])
    if private_key_files:
        assert "CryptoFinding" in node_types


def test_deterministic_ids_and_no_uuid_like_ids():
    snapshot_a = _build_snapshot()
    snapshot_b = _build_snapshot()

    node_ids_a = {n["id"] for n in snapshot_a["nodes"]}
    node_ids_b = {n["id"] for n in snapshot_b["nodes"]}
    edge_ids_a = {e["id"] for e in snapshot_a["edges"]}
    edge_ids_b = {e["id"] for e in snapshot_b["edges"]}

    assert node_ids_a == node_ids_b
    assert edge_ids_a == edge_ids_b

    for id_value in list(node_ids_a) + list(edge_ids_a):
        assert not UUID_LIKE_RE.search(id_value)


def test_unique_ids_edge_references_and_confidence_bounds():
    snapshot = _build_snapshot()

    node_ids = [node["id"] for node in snapshot["nodes"]]
    edge_ids = [edge["id"] for edge in snapshot["edges"]]

    assert len(node_ids) == len(set(node_ids))
    assert len(edge_ids) == len(set(edge_ids))

    node_id_set = set(node_ids)
    for edge in snapshot["edges"]:
        assert edge["from"] in node_id_set
        assert edge["to"] in node_id_set

    for node in snapshot["nodes"]:
        assert 0.0 <= node["confidence"] <= 1.0
    for edge in snapshot["edges"]:
        assert 0.0 <= edge["confidence"] <= 1.0


def test_runs_edge_links_network_asset_to_service():
    snapshot = _build_snapshot()
    nodes_by_id = {n["id"]: n for n in snapshot["nodes"]}
    runs = [e for e in snapshot["edges"] if e["type"] == "RUNS"]

    assert runs, "expected at least one RUNS edge (Asset -> Service)"
    for e in runs:
        assert nodes_by_id[e["from"]]["type"] == "Asset"
        assert nodes_by_id[e["to"]]["type"] == "Service"


def test_weak_public_key_creates_service_finding():
    payload = {
        "assets": [{"name": "weak-endpoint", "asset_type": "endpoint"}],
        "tls_metadata": {
            "target": "weak.example",
            "port": 443,
            "certificate": {
                "subject": {"display_dn": "CN=weak.example"},
                "algorithms": {"public_key": "RSA"},
                "key": {"size_bits": 1024},
                "sha256_fingerprint": "deadbeef",
            },
        },
    }
    nodes, edges, warnings = {}, {}, []
    projector.project_network(payload, nodes, edges, warnings)

    findings = [n for n in nodes.values() if n["type"] == "CryptoFinding"]
    assert any(f["properties"].get("indicator") == "weak_public_key" for f in findings)
    assert any(e["type"] == "SERVICE_HAS_FINDING" for e in edges.values())
    finding_edge = next(e for e in edges.values() if e["type"] == "SERVICE_HAS_FINDING")
    assert nodes[finding_edge["from"]]["type"] == "Service"


def test_warning_shape_is_consistent():
    snapshot = _build_snapshot()

    for warning in snapshot["warnings"]:
        assert "code" in warning
        assert "severity" in warning
        assert "message" in warning
        assert "related_node_ids" in warning
        assert "related_edge_ids" in warning
        assert "evidence_ref" in warning


def test_config_file_path_hashing_is_not_raw_path_in_id_and_is_deterministic():
    snapshot = _build_snapshot()
    config_nodes = [n for n in snapshot["nodes"] if n["type"] == "ConfigFile"]

    assert config_nodes
    for cfg in config_nodes:
        cfg_id = cfg["id"]
        raw_path = cfg["properties"].get("path", "")
        assert raw_path not in cfg_id
        digest = cfg_id.split(":")[-1]
        assert len(digest) == 16
        assert all(c in "0123456789abcdef" for c in digest)

    snapshot_again = _build_snapshot()
    cfg_ids_a = sorted(n["id"] for n in config_nodes)
    cfg_ids_b = sorted(n["id"] for n in snapshot_again["nodes"] if n["type"] == "ConfigFile")
    assert cfg_ids_a == cfg_ids_b


def test_report_contains_pass_and_counts():
    import subprocess
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        snapshot_path = Path(tmpdir) / "snapshot.json"
        report_path = Path(tmpdir) / "report.md"

        subprocess.run([
            "python",
            "tools/graph_projection/project_stage2_fixtures.py",
            "--host",
            str(HOST_FIXTURE),
            "--network",
            str(NETWORK_FIXTURE),
            "--snapshot-out",
            str(snapshot_path),
            "--report-out",
            str(report_path),
        ], check=True)

        snapshot = json.loads(snapshot_path.read_text())
        report = report_path.read_text()

        assert "PASS" in report
        assert f"- node count: {len(snapshot['nodes'])}" in report
        assert f"- edge count: {len(snapshot['edges'])}" in report
        assert f"- warning count: {len(snapshot['warnings'])}" in report
