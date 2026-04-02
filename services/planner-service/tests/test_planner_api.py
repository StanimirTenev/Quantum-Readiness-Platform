from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "planner-service"}


def test_plan(monkeypatch) -> None:
    monkeypatch.setattr("app.main.inventory.get_assets", lambda: [
        {"name": "google.com:443", "asset_type": "endpoint"},
        {"name": "stenly-Latitude-E6230", "asset_type": "server"},
    ])
    monkeypatch.setattr("app.main.inventory.get_risks", lambda: [
        {"asset_name": "google.com:443", "rating": "high", "normalized_score_100": 68.0, "scenario": "public_timeline"},
        {"asset_name": "stenly-Latitude-E6230", "rating": "high", "normalized_score_100": 64.0, "scenario": "public_timeline"},
    ])

    response = client.get("/plan")
    assert response.status_code == 200
    data = response.json()
    assert "summary" in data
    assert "wave_1" in data


def test_waves(monkeypatch) -> None:
    monkeypatch.setattr("app.main.inventory.get_assets", lambda: [
        {"name": "google.com:443", "asset_type": "endpoint"},
    ])
    monkeypatch.setattr("app.main.inventory.get_risks", lambda: [
        {"asset_name": "google.com:443", "rating": "high", "normalized_score_100": 68.0, "scenario": "public_timeline"},
    ])

    response = client.get("/waves")
    assert response.status_code == 200
    data = response.json()
    assert len(data["wave_1"]) == 1
