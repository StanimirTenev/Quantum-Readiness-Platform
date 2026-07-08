from fastapi.testclient import TestClient

from app.main import DISABLED_ANSWER, app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "copilot-service"}


def test_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.retrieval.get_overview",
        lambda: {
            "asset_count": 1,
            "scan_count": 1,
            "risk_count": 1,
            "top_risks": [{"asset_name": "google.com:443", "rating": "high"}],
        },
    )

    response = client.get("/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["asset_count"] == 1
    assert data["risk_count"] == 1
    assert data["risk_counts"]["high"] == 1


def test_query_top_risks(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.retrieval.get_overview",
        lambda: {
            "asset_count": 1,
            "scan_count": 1,
            "risk_count": 1,
            "top_risks": [{"asset_name": "google.com:443", "rating": "high"}],
        },
    )

    response = client.post("/query", json={"question": "show top risks"})
    assert response.status_code == 200
    assert response.json()["intent"] == "top_risks"


def test_narrate_asset_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.retrieval.get_asset",
        lambda asset_name: {"risks": [{"rating": "high", "normalized_score_100": 70.0, "scenario": "public_timeline", "scenario_multiplier": 1.0, "rationale": {"weak_public_key_detected": True}}]},
    )

    response = client.get("/narrate/payments-api")
    assert response.status_code == 200
    data = response.json()
    assert data["asset_name"] == "payments-api"
    assert "weak public key" in data["narrative"]


def test_query_why_asset_routes_to_narrate(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.retrieval.get_asset",
        lambda asset_name: {"risks": [{"rating": "critical", "normalized_score_100": 90.0, "scenario": "public_timeline", "scenario_multiplier": 1.0, "rationale": {}}]},
    )

    response = client.post("/query", json={"question": "why is asset payments-api risky?"})
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "narrate_asset"
    assert data["result"]["asset_name"] == "payments-api"


def test_operational_summary(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.retrieval.get_overview",
        lambda: {
            "asset_count": 1,
            "scan_count": 1,
            "risk_count": 1,
            "top_risks": [{"asset_name": "google.com:443", "rating": "high"}],
        },
    )
    monkeypatch.setattr(
        "app.main.planner.get_plan",
        lambda: {"summary": {"wave_1_count": 1, "wave_2_count": 0, "wave_3_count": 0}},
    )
    monkeypatch.setattr(
        "app.main.workflow.get_tasks",
        lambda: [{"id": "t1", "status": "draft"}, {"id": "t2", "status": "approved"}],
    )
    monkeypatch.setattr("app.main.workflow.get_approvals", lambda: [{"task_id": "t2"}])

    response = client.get("/operational-summary")
    assert response.status_code == 200
    data = response.json()
    assert data["platform"]["asset_count"] == 1
    assert data["planning"]["wave_1_count"] == 1
    assert data["workflow"]["task_count"] == 2


def test_query_search(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.retrieval.search",
        lambda query: {"query": query, "results": {"assets": [{"name": "google.com:443"}]}},
    )

    response = client.post("/query", json={"question": "google"})
    assert response.status_code == 200
    assert response.json()["intent"] == "search"


def test_copilot_query_missing_provider_defaults_disabled(monkeypatch) -> None:
    monkeypatch.delenv("COPILOT_PROVIDER", raising=False)
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["used_external_provider"] is False
    assert "copilot_provider_disabled" in data["warnings"]
    assert data["metadata"]["requested_provider"] == "missing"
    assert data["citations"] == []
    assert data["redaction_applied"] is False


def test_copilot_query_explicit_disabled(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "disabled")
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["used_external_provider"] is False
    assert data["metadata"]["provider_name"] == "disabled"
    assert "copilot_provider_disabled" in data["warnings"]
    assert data["metadata"]["requested_provider"] == "disabled"


def test_copilot_query_unknown_provider_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "unexpected")
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["used_external_provider"] is False
    assert data["metadata"]["provider_name"] == "disabled"
    assert "copilot_provider_disabled" in data["warnings"]
    assert "copilot_provider_unknown" in data["warnings"]
    assert data["metadata"]["provider_config_reason"] == "copilot_provider_unknown"
    assert data["citations"] == []


def test_copilot_query_local_missing_url_fails_safely(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "local")
    monkeypatch.delenv("COPILOT_LOCAL_URL", raising=False)
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["metadata"]["provider_name"] == "disabled"
    assert data["used_external_provider"] is False
    assert "copilot_provider_disabled" in data["warnings"]
    assert "copilot_local_url_rejected" in data["warnings"]
    assert data["metadata"]["local_url_validation_reason"] == "url_missing"


def test_copilot_query_local_public_url_rejected(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "local")
    monkeypatch.setenv("COPILOT_LOCAL_URL", "https://example.com/infer")
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["used_external_provider"] is False
    assert "copilot_local_url_rejected" in data["warnings"]
    assert data["metadata"]["local_url_validation_reason"] == "host_not_local"


def test_copilot_query_local_malformed_url_rejected(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "local")
    monkeypatch.setenv("COPILOT_LOCAL_URL", "localhost:11434")
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["used_external_provider"] is False
    assert "copilot_local_url_rejected" in data["warnings"]
    assert data["metadata"]["local_url_validation_reason"] == "scheme_missing"


def test_copilot_query_local_allowed_url_still_not_implemented(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "local")
    monkeypatch.setenv("COPILOT_LOCAL_URL", "http://localhost:11434/api")
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["used_external_provider"] is False
    assert "copilot_local_provider_not_implemented" in data["warnings"]
    assert data["metadata"]["local_url_validation_reason"] == "allowed"


def test_copilot_query_external_not_implemented_fails_safely(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "external")
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["used_external_provider"] is False
    assert data["metadata"]["provider_name"] == "disabled"
    assert "copilot_provider_disabled" in data["warnings"]
    assert "copilot_external_provider_not_implemented" in data["warnings"]


def test_copilot_query_request_id_preserved_and_no_api_key_required(monkeypatch) -> None:
    monkeypatch.delenv("COPILOT_EXTERNAL_API_KEY", raising=False)
    response = client.post(
        "/copilot/query",
        json={"query": "hello", "metadata": {"request_id": "req-123"}},
    )
    data = response.json()
    assert response.status_code == 200
    assert data["metadata"]["request_id"] == "req-123"
    assert data["answer"] == DISABLED_ANSWER
    assert data["citations"] == []
    assert data["redaction_applied"] is False
