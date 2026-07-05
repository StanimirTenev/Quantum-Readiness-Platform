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


def test_post_api_pqc_readiness_forwards_to_classify(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"contract_version": "pqr-v1", "readiness": "classical_only"}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {"asset_name": "a", "findings": [{"classification": "classical_vulnerable"}]}
    response = client.post("/api/pqc-readiness", json=payload)

    assert response.status_code == 200
    assert response.json()["readiness"] == "classical_only"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/classify")
    assert captured["payload"] == payload


def test_cors_headers_present_for_browser_origin() -> None:
    response = client.get("/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ("*", "http://127.0.0.1:5173")


def test_post_api_integrations_dry_run_forwards_payload(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"mode": "dry_run_disabled", "executed": False, "would_execute_if_enabled": False}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {"action": "rotate_certificate", "target_type": "ca", "asset_name": "a"}
    response = client.post("/api/integrations/dry-run", json=payload)

    assert response.status_code == 200
    assert response.json()["executed"] is False
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/dry-run")
    assert captured["payload"] == payload


def test_post_api_scenarios_run_forwards_payload_to_scenario_engine(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"scenario": "hidden_capability", "scenario_multiplier": 1.35, "asset_count": 1, "highest_rating": "high", "results": []}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {"scenario": "hidden_capability", "assets": [{"asset_name": "a", "base_score": 3.0}]}
    response = client.post("/api/scenarios/run", json=payload)

    assert response.status_code == 200
    assert response.json()["scenario_multiplier"] == 1.35
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/run")
    assert captured["payload"] == payload


def test_post_api_fingerprint_forwards_payload_to_crypto_service(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {
            "contract_version": "cfp-v1",
            "asset_name": "api.example.internal:443",
            "findings": [],
            "summary": {"pqc_readiness": "classical_only"},
        }

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {"asset_name": "api.example.internal:443", "algorithms": ["RSA"]}
    response = client.post("/api/fingerprint", json=payload)

    assert response.status_code == 200
    assert response.json()["summary"]["pqc_readiness"] == "classical_only"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/fingerprint")
    assert captured["payload"] == payload


def test_get_api_algorithms_forwards_to_crypto_service(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        return {"algorithms": [{"family": "RSA", "classification": "classical_vulnerable"}]}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/algorithms")

    assert response.status_code == 200
    assert response.json()["algorithms"][0]["family"] == "RSA"
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/algorithms")


def test_post_api_normalize_forwards_payload_to_evidence_normalizer(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"contract_version": "evn-v1", "source": "network", "assets": [], "warnings": []}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {"source": "network", "assets": [], "tls_metadata": {"collected": True}}
    response = client.post("/api/normalize", json=payload)

    assert response.status_code == 200
    assert response.json()["contract_version"] == "evn-v1"
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/normalize")
    assert captured["payload"] == payload


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
    data = response.json()
    assert {"graph_schema_version", "nodes", "edges", "warnings"}.issubset(data.keys())


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
    for unsafe_path in ("http://example.com/graph-snapshot.json", "https://example.com/graph-snapshot.json"):
        monkeypatch.setenv("GRAPH_SNAPSHOT_PATH", unsafe_path)
        response = client.get("/graph/summary")
        assert response.status_code == 400
        assert response.json() == {"detail": {"error": "graph_snapshot_unsafe_path"}}


def test_graph_nodes_filter_returns_only_matching_type_and_empty_for_unknown(monkeypatch) -> None:
    snapshot = {
        "graph_schema_version": "v1",
        "nodes": [{"id": "n1", "type": "asset"}, {"id": "n2", "type": "supplier"}],
        "edges": [],
        "warnings": [],
    }
    monkeypatch.setattr(main, "_load_graph_snapshot_or_raise", lambda: snapshot)

    filtered = client.get("/graph/nodes?node_type=asset")
    assert filtered.status_code == 200
    filtered_nodes = filtered.json()["nodes"]
    assert isinstance(filtered_nodes, list)
    assert all(node.get("type") == "asset" for node in filtered_nodes)

    unknown = client.get("/graph/nodes?node_type=unknown_type")
    assert unknown.status_code == 200
    assert unknown.json()["nodes"] == []


def test_graph_edges_filter_returns_only_matching_type_and_empty_for_unknown(monkeypatch) -> None:
    snapshot = {
        "graph_schema_version": "v1",
        "nodes": [{"id": "n1", "type": "asset"}, {"id": "n2", "type": "supplier"}],
        "edges": [
            {"from": "n1", "to": "n2", "type": "depends_on"},
            {"from": "n2", "to": "n1", "type": "owned_by"},
        ],
        "warnings": [],
    }
    monkeypatch.setattr(main, "_load_graph_snapshot_or_raise", lambda: snapshot)

    filtered = client.get("/graph/edges?edge_type=depends_on")
    assert filtered.status_code == 200
    filtered_edges = filtered.json()["edges"]
    assert isinstance(filtered_edges, list)
    assert all(edge.get("type") == "depends_on" for edge in filtered_edges)

    unknown = client.get("/graph/edges?edge_type=unknown_type")
    assert unknown.status_code == 200
    assert unknown.json()["edges"] == []


def test_graph_snapshot_responses_do_not_include_graph_db_or_traversal_indicators(monkeypatch) -> None:
    snapshot = {
        "graph_schema_version": "v1",
        "nodes": [{"id": "n1", "type": "asset"}],
        "edges": [{"from": "n1", "to": "n1", "type": "depends_on"}],
        "warnings": [{"code": "w1"}],
    }
    monkeypatch.setattr(main, "_load_graph_snapshot_or_raise", lambda: snapshot)

    disallowed_terms = {
        "neo4j",
        "cypher",
        "database_url",
        "graph_db",
        "blast_radius",
        "traversal_result",
        "path_query",
    }

    for path in ("/graph/snapshot", "/graph/summary", "/graph/nodes", "/graph/edges", "/graph/warnings"):
        response = client.get(path)
        assert response.status_code == 200
        payload_lower = response.text.lower()
        assert all(term not in payload_lower for term in disallowed_terms)


def test_graph_api_has_no_mutation_methods() -> None:
    openapi = client.get("/openapi.json").json()
    for path, methods in openapi["paths"].items():
        if path.startswith("/graph/"):
            assert set(methods.keys()) == {"get"}


def test_graph_mutation_requests_are_not_successful() -> None:
    mutation_requests = [
        ("post", "/graph/snapshot"),
        ("put", "/graph/snapshot"),
        ("patch", "/graph/snapshot"),
        ("delete", "/graph/snapshot"),
        ("post", "/graph/nodes"),
        ("delete", "/graph/nodes"),
    ]

    for method, path in mutation_requests:
        response = client.request(method.upper(), path, json={})
        assert response.status_code < 200 or response.status_code >= 300
