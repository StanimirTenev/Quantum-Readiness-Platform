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


def test_get_api_asset_history_proxies_to_inventory(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        return {"asset_id": "a1", "asset_name": "host-x", "points": [], "trend": "insufficient_data"}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/assets/a1/history")

    assert response.status_code == 200
    assert response.json()["trend"] == "insufficient_data"
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/assets/a1/history")


def test_post_api_scans_windows_forwards_document_to_windows_ingest(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"scan_id": "scan-win-1", "created": 1, "source": "host"}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    document = {
        "asset": {"asset_id": "a1", "asset_type": "endpoint", "platform": "windows", "name": "redacted-windows-host"},
        "windows_evidence": {"certificate_store_indicators": {"certificates_observed_count": 3}},
    }
    response = client.post("/api/scans/windows?scenario=hidden_capability", json=document)

    assert response.status_code == 200
    assert response.json()["scan_id"] == "scan-win-1"
    assert captured["method"] == "POST"
    assert "/scans/ingest/windows" in captured["url"]
    assert "scenario=hidden_capability" in captured["url"]
    # The raw evidence document is forwarded as-is (no "source" injection here).
    assert captured["payload"] == document


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


def test_post_api_assess_chains_fingerprint_readiness_and_risk(monkeypatch) -> None:
    calls: list[str] = []

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        calls.append(url)
        if url.endswith("/fingerprint"):
            return {
                "summary": {"pqc_readiness": "hybrid_partial"},
                "findings": [
                    {"classification": "classical_vulnerable"},
                    {"classification": "pqc_ready"},
                ],
            }
        if url.endswith("/classify"):
            # findings from fingerprint must be forwarded to pqc-readiness
            assert len(payload["findings"]) == 2
            return {"readiness": "hybrid_capable", "confidence": "medium"}
        if url.endswith("/attribute"):
            assert len(payload["findings"]) == 2
            return {"contract_version": "attr-v1", "attributed_findings": [], "summary": {"total": 2}}
        if url.endswith("/score"):
            assert payload["asset_name"] == "payments-api"
            assert payload["criticality"] == 5
            return {"normalized_score_100": 72.0, "rating": "high"}
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {
        "asset_name": "payments-api",
        "algorithms": ["RSA", "ML-KEM-768"],
        "risk_factors": {
            "criticality": 5,
            "confidentiality_lifetime": 4,
            "quantum_exposure": 3,
            "blast_radius": 4,
            "vendor_lock_in": 3,
            "migration_difficulty": 3,
        },
    }
    response = client.post("/api/assess", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["fingerprint"]["summary"]["pqc_readiness"] == "hybrid_partial"
    assert data["pqc_readiness"]["readiness"] == "hybrid_capable"
    assert data["attribution"]["contract_version"] == "attr-v1"
    assert data["risk"]["rating"] == "high"
    assert data["pipeline"] == [
        "crypto-fingerprint-service", "pqc-readiness-service", "finding-attribution-service", "risk-engine"
    ]
    assert any(u.endswith("/fingerprint") for u in calls)
    assert any(u.endswith("/classify") for u in calls)
    assert any(u.endswith("/attribute") for u in calls)
    assert any(u.endswith("/score") for u in calls)


def test_post_api_assess_without_risk_factors_skips_risk(monkeypatch) -> None:
    def fake_request_json(method: str, url: str, payload: dict | None = None):
        if url.endswith("/fingerprint"):
            return {"summary": {"pqc_readiness": "classical_only"}, "findings": [{"classification": "classical_vulnerable"}]}
        if url.endswith("/classify"):
            return {"readiness": "classical_only"}
        if url.endswith("/attribute"):
            return {"contract_version": "attr-v1", "attributed_findings": []}
        raise AssertionError(f"unexpected url {url}")

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.post("/api/assess", json={"asset_name": "a", "algorithms": ["RSA"]})

    assert response.status_code == 200
    data = response.json()
    assert data["risk"] is None
    assert data["pipeline"] == [
        "crypto-fingerprint-service", "pqc-readiness-service", "finding-attribution-service"
    ]


def test_post_api_attribute_forwards_to_attribution_service(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["url"] = url
        captured["payload"] = payload
        return {"contract_version": "attr-v1", "attributed_findings": []}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {"asset_name": "a", "findings": [{"source": "tls_certificate"}]}
    response = client.post("/api/attribute", json=payload)

    assert response.status_code == 200
    assert response.json()["contract_version"] == "attr-v1"
    assert captured["url"].endswith("/attribute")
    assert captured["payload"] == payload


def test_post_api_graph_blast_radius_forwards(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"contract_version": "graph-query-v1", "affected_count": 3, "affected_node_ids": ["a", "b", "c"]}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    payload = {"node_id": "cert:root"}
    response = client.post("/api/graph/blast-radius", json=payload)

    assert response.status_code == 200
    assert response.json()["affected_count"] == 3
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/blast-radius")
    assert captured["payload"] == payload


def test_post_api_graph_evidence_path_forwards(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["url"] = url
        return {"contract_version": "graph-query-v1", "chain": [{"role": "vulnerability"}]}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.post("/api/graph/evidence-path", json={"node_id": "finding:v"})

    assert response.status_code == 200
    assert response.json()["chain"][0]["role"] == "vulnerability"
    assert captured["url"].endswith("/evidence-path")


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


def test_get_api_copilot_narrate_proxies_to_copilot_service(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        return {"asset_name": "payments-api", "narrative": "Asset 'payments-api' is rated critical."}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/copilot/narrate/payments-api")

    assert response.status_code == 200
    assert response.json()["asset_name"] == "payments-api"
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/narrate/payments-api")


def test_get_api_copilot_discover_proxies_to_copilot_service(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        return {"narrative": "Discovered 2 explicit crypto finding(s)...", "explicit_findings": [], "inferred_context": [], "evidence_gaps": []}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/copilot/discover")

    assert response.status_code == 200
    assert "narrative" in response.json()
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/discover")


def test_get_api_copilot_vendor_intelligence_proxies_to_copilot_service(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        return {"narrative": "Extracted 1 PQC readiness claim...", "claims": [], "readiness_matrix": []}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/copilot/vendor-intelligence")

    assert response.status_code == 200
    assert "narrative" in response.json()
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/vendor-intelligence")


def test_get_api_copilot_migration_plan_proxies_to_copilot_service(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        return {"narrative": "Migration plan covers 0 asset(s)...", "waves": [], "vendor_readiness_context": {}}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/copilot/migration-plan")

    assert response.status_code == 200
    assert "narrative" in response.json()
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/migration-plan")


def test_get_api_copilot_plan_summary_proxies_to_copilot_service(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        return {"summary": {"wave_1_count": 1}}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/copilot/plan-summary")

    assert response.status_code == 200
    assert captured["method"] == "GET"
    assert captured["url"].endswith("/plan-summary")


def test_get_api_copilot_workflow_summary_proxies_to_copilot_service(monkeypatch) -> None:
    def fake_request_json(method: str, url: str, payload: dict | None = None):
        return {"task_count": 0}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/copilot/workflow-summary")
    assert response.status_code == 200
    assert response.json()["task_count"] == 0


def test_get_api_copilot_operational_summary_proxies_to_copilot_service(monkeypatch) -> None:
    def fake_request_json(method: str, url: str, payload: dict | None = None):
        return {"platform": {}, "planning": {}, "workflow": {}}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.get("/api/copilot/operational-summary")
    assert response.status_code == 200


def test_post_api_copilot_query_proxies_to_copilot_service(monkeypatch) -> None:
    captured: dict = {}

    def fake_request_json(method: str, url: str, payload: dict | None = None):
        captured["method"] = method
        captured["url"] = url
        captured["payload"] = payload
        return {"intent": "search", "result": {}}

    monkeypatch.setattr(main, "_request_json", fake_request_json)

    response = client.post("/api/copilot/query", json={"question": "top risks"})

    assert response.status_code == 200
    assert captured["method"] == "POST"
    assert captured["url"].endswith("/query")
    assert captured["payload"]["question"] == "top risks"


def test_old_dead_copilot_routes_are_gone() -> None:
    assert client.post("/api/copilot/explain-risk", json={}).status_code == 404
    assert client.post("/api/copilot/generate-wave-plan", json={}).status_code == 404
