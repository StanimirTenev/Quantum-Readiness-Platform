from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import app.main as main

client = TestClient(main.app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "scenario-engine"}


def test_scenarios_lists_multipliers() -> None:
    response = client.get("/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert data["public_timeline"] == 1.00
    assert data["hndl_active_now"] == 1.40


def test_run_public_timeline_keeps_base_score() -> None:
    response = client.post(
        "/run",
        json={"scenario": "public_timeline", "assets": [{"asset_name": "a", "base_score": 3.0}]},
    )
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["scenario_multiplier"] == 1.0
    assert result["final_score"] == 3.0
    assert result["normalized_score_100"] == 60.0
    assert result["rating"] == "high"


def test_run_hndl_scenario_raises_score_and_rating() -> None:
    response = client.post(
        "/run",
        json={"scenario": "hndl_active_now", "assets": [{"asset_name": "a", "base_score": 3.0}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["scenario_multiplier"] == 1.40
    result = data["results"][0]
    assert result["final_score"] == 4.2
    assert result["normalized_score_100"] == 84.0
    assert result["rating"] == "critical"
    assert data["highest_rating"] == "critical"


def test_run_sorts_results_by_normalized_score_desc() -> None:
    response = client.post(
        "/run",
        json={
            "scenario": "public_timeline",
            "assets": [
                {"asset_name": "low", "base_score": 1.0},
                {"asset_name": "high", "base_score": 4.0},
                {"asset_name": "mid", "base_score": 2.5},
            ],
        },
    )
    assert response.status_code == 200
    order = [item["asset_name"] for item in response.json()["results"]]
    assert order == ["high", "mid", "low"]


def test_run_caps_normalized_score_at_100() -> None:
    response = client.post(
        "/run",
        json={"scenario": "hidden_capability", "assets": [{"asset_name": "a", "base_score": 5.0}]},
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["normalized_score_100"] == 100.0


def test_run_empty_assets_returns_minimal_highest_rating() -> None:
    response = client.post("/run", json={"scenario": "early_break", "assets": []})
    assert response.status_code == 200
    data = response.json()
    assert data["asset_count"] == 0
    assert data["highest_rating"] == "minimal"
    assert data["results"] == []


def test_run_unknown_scenario_returns_422() -> None:
    response = client.post(
        "/run",
        json={"scenario": "does_not_exist", "assets": [{"asset_name": "a", "base_score": 1.0}]},
    )
    assert response.status_code == 422


def test_run_base_score_over_range_returns_422() -> None:
    response = client.post(
        "/run",
        json={"scenario": "public_timeline", "assets": [{"asset_name": "a", "base_score": 6.0}]},
    )
    assert response.status_code == 422
