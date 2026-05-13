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


def test_copilot_query_unknown_provider_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "unexpected")
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["used_external_provider"] is False
    assert data["metadata"]["provider_name"] == "disabled"
    assert "copilot_provider_disabled" in data["warnings"]
    assert data["citations"] == []


def test_copilot_query_local_not_implemented_fails_safely(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "local")
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["metadata"]["provider_name"] == "disabled"
    assert data["used_external_provider"] is False
    assert "copilot_provider_disabled" in data["warnings"]


def test_copilot_query_external_not_implemented_fails_safely(monkeypatch) -> None:
    monkeypatch.setenv("COPILOT_PROVIDER", "external")
    response = client.post("/copilot/query", json={"query": "hello"})
    data = response.json()
    assert response.status_code == 200
    assert data["provider_mode"] == "disabled"
    assert data["used_external_provider"] is False
    assert data["metadata"]["provider_name"] == "disabled"
    assert "copilot_provider_disabled" in data["warnings"]


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
