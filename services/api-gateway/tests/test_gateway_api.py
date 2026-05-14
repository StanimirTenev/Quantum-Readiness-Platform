from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import main

client = TestClient(main.app)


def test_post_api_scans_host_forces_host_source_and_forwards(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"scan_id": "scan-1", "created": 1}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.post(
        "/api/scans/host?scenario=hidden_capability",
        json={"assets": [{"asset_type": "server", "name": "host-1"}], "source": "manual"},
    )

    assert response.status_code == 200
    assert response.json()["scan_id"] == "scan-1"
    assert captured["method"] == "POST"
    assert "scenario=hidden_capability" in captured["url"]
    assert captured["payload"]["source"] == "host"


def test_get_api_assets_asset_id_risk_builds_payload_and_returns_wrapped_response(monkeypatch) -> None:
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        calls.append((method, url, payload))
        if url.endswith("/assets/asset-1"):
            return {
                "id": "asset-1",
                "name": "payments-api",
                "criticality": 5,
                "environment": "production",
                "vendor": "acme",
                "lifecycle_years": 10,
            }
        return {
            "scenario": "early_break",
            "normalized_score_100": 88.0,
            "rating": "critical",
        }

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/assets/asset-1/risk?scenario=early_break")

    assert response.status_code == 200
    data = response.json()
    assert data["asset_id"] == "asset-1"
    assert data["asset_name"] == "payments-api"
    assert data["risk"]["rating"] == "critical"

    assert len(calls) == 2
    assert calls[0][0] == "GET"
    assert calls[1][0] == "POST"
    assert calls[1][2]["scenario"] == "early_break"
    assert calls[1][2]["criticality"] == 5.0


def test_post_api_policies_evaluate_forwards_payload_and_returns_upstream(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {
            "asset_name": "payments-api",
            "decision": "review",
            "score": 65,
            "reasons": ["high_risk_production_asset"],
            "rule_id": "pqc-readiness-gate-v1",
            "rule_version": "1.0.0",
        }

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {
        "asset_id": "asset-1",
        "asset_name": "payments-api",
        "asset_type": "service",
        "environment": "production",
        "criticality": 5,
        "normalized_score_100": 65,
        "rating": "high",
        "vendor_blocked": False,
        "dependency_count": 3,
        "scenario": "public_timeline",
    }

    response = client.post("/api/policies/evaluate", json=payload)

    assert response.status_code == 200
    assert response.json()["decision"] == "review"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/evaluate")
    assert captured["payload"] == payload
    assert response.json() == {
        "asset_name": "payments-api",
        "decision": "review",
        "score": 65,
        "reasons": ["high_risk_production_asset"],
        "rule_id": "pqc-readiness-gate-v1",
        "rule_version": "1.0.0",
    }


def test_get_graph_summary_returns_expected_shape(monkeypatch) -> None:
    snapshot = {
        "graph_schema_version": "v1",
        "nodes": [{"id": "n1", "type": "asset"}],
        "edges": [{"from": "n1", "to": "n1", "type": "depends_on"}],
        "warnings": [{"code": "sample"}],
    }
    monkeypatch.setattr(main, "_load_graph_snapshot_or_raise", lambda: snapshot)

    response = client.get("/graph/summary")

    assert response.status_code == 200
    assert response.json() == {
        "graph_schema_version": "v1",
        "node_count": 1,
        "edge_count": 1,
        "warning_count": 1,
        "node_types": ["asset"],
        "edge_types": ["depends_on"],
    }


def test_get_graph_snapshot_returns_expected_shape(monkeypatch) -> None:
    snapshot = {
        "graph_schema_version": "v1",
        "nodes": [],
        "edges": [],
        "warnings": [],
        "metadata": {"generated_at": "2026-05-14T00:00:00Z"},
    }
    monkeypatch.setattr(main, "_load_graph_snapshot_or_raise", lambda: snapshot)

    response = client.get("/graph/snapshot")

    assert response.status_code == 200
    assert set(response.json().keys()) == {"graph_schema_version", "nodes", "edges", "warnings", "metadata"}


def test_get_graph_nodes_returns_list(monkeypatch) -> None:
    snapshot = {"graph_schema_version": "v1", "nodes": [{"id": "n1", "type": "asset"}], "edges": [], "warnings": []}
    monkeypatch.setattr(main, "_load_graph_snapshot_or_raise", lambda: snapshot)

    response = client.get("/graph/nodes")

    assert response.status_code == 200
    assert isinstance(response.json()["nodes"], list)


def test_get_graph_edges_returns_list(monkeypatch) -> None:
    snapshot = {"graph_schema_version": "v1", "nodes": [{"id": "n1", "type": "asset"}], "edges": [{"from": "n1", "to": "n1", "type": "depends_on"}], "warnings": []}
    monkeypatch.setattr(main, "_load_graph_snapshot_or_raise", lambda: snapshot)

    response = client.get("/graph/edges")

    assert response.status_code == 200
    assert isinstance(response.json()["edges"], list)


def test_get_graph_warnings_returns_list(monkeypatch) -> None:
    snapshot = {"graph_schema_version": "v1", "nodes": [], "edges": [], "warnings": [{"code": "w1"}]}
    monkeypatch.setattr(main, "_load_graph_snapshot_or_raise", lambda: snapshot)

    response = client.get("/graph/warnings")

    assert response.status_code == 200
    assert isinstance(response.json()["warnings"], list)


def test_graph_snapshot_missing_returns_structured_safe_error(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_SNAPSHOT_PATH", "reports/graph/latest/missing.json")
    response = client.get("/graph/summary")
    assert response.status_code == 400
    assert response.json() == {"detail": {"error": "graph_snapshot_missing"}}


def test_graph_snapshot_remote_path_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("GRAPH_SNAPSHOT_PATH", "https://example.com/graph-snapshot.json")
    response = client.get("/graph/summary")
    assert response.status_code == 400
    assert response.json() == {"detail": {"error": "graph_snapshot_unsafe_path"}}


def test_graph_api_has_no_mutation_methods() -> None:
    openapi = client.get("/openapi.json").json()
    for path, methods in openapi["paths"].items():
        if path.startswith("/graph/"):
            assert set(methods.keys()) == {"get"}
