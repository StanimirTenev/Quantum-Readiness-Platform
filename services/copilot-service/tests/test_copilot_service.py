from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "copilot-service"}


def test_summary(monkeypatch) -> None:
    monkeypatch.setattr("app.main.inventory.get_assets", lambda: [{"id": "a1"}])
    monkeypatch.setattr("app.main.inventory.get_scans", lambda: [{"id": "s1"}])
    monkeypatch.setattr(
        "app.main.inventory.get_risks",
        lambda: [{"id": "r1", "rating": "high", "normalized_score_100": 65.0}],
    )

    response = client.get("/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["asset_count"] == 1
    assert data["scan_count"] == 1
    assert data["risk_count"] == 1
    assert data["risk_counts"]["high"] == 1


def test_query_top_risks(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.main.inventory.get_risks",
        lambda: [{"id": "r1", "rating": "high", "normalized_score_100": 65.0}],
    )
    monkeypatch.setattr("app.main.inventory.get_assets", lambda: [])
    monkeypatch.setattr("app.main.inventory.get_scans", lambda: [])

    response = client.post("/query", json={"question": "show top risks"})
    assert response.status_code == 200
    assert response.json()["intent"] == "top_risks"


def test_query_summary(monkeypatch) -> None:
    monkeypatch.setattr("app.main.inventory.get_assets", lambda: [])
    monkeypatch.setattr("app.main.inventory.get_scans", lambda: [])
    monkeypatch.setattr("app.main.inventory.get_risks", lambda: [])

    response = client.post("/query", json={"question": "give me a summary"})
    assert response.status_code == 200
    assert response.json()["intent"] == "summary"
