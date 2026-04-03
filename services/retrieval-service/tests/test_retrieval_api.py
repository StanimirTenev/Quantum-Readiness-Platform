from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "retrieval-service"}


def test_overview(monkeypatch) -> None:
    monkeypatch.setattr("app.main.inventory.get_assets", lambda: [{"name": "google.com:443"}])
    monkeypatch.setattr("app.main.inventory.get_scans", lambda: [{"id": "scan-1"}])
    monkeypatch.setattr("app.main.inventory.get_risks", lambda: [{"asset_name": "google.com:443", "normalized_score_100": 68.0}])
    monkeypatch.setattr("app.main.workflow.get_tasks", lambda: [{"status": "draft"}])
    monkeypatch.setattr("app.main.workflow.get_approvals", lambda: [{"task_id": "1"}])
    monkeypatch.setattr("app.main.planner.get_plan", lambda: {"summary": {"wave_1_count": 1}})

    response = client.get("/overview")
    assert response.status_code == 200
    assert response.json()["asset_count"] == 1


def test_search(monkeypatch) -> None:
    monkeypatch.setattr("app.main.inventory.get_assets", lambda: [{"name": "google.com:443", "asset_type": "endpoint"}])
    monkeypatch.setattr("app.main.inventory.get_scans", lambda: [{"source": "network", "tls_evidence": {"target": "google.com:443"}}])
    monkeypatch.setattr("app.main.inventory.get_risks", lambda: [{"asset_name": "google.com:443", "rating": "high", "scenario": "public_timeline", "normalized_score_100": 68.0}])
    monkeypatch.setattr("app.main.workflow.get_tasks", lambda: [{"title": "Review google.com:443", "asset_name": "google.com:443", "status": "draft", "wave": "wave_1"}])

    response = client.post("/search", json={"query": "google"})
    assert response.status_code == 200
    assert len(response.json()["results"]["assets"]) == 1
