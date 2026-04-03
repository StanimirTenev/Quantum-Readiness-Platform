from app.planner import build_plan


def test_build_plan() -> None:
    assets = [
        {"name": "google.com:443", "asset_type": "endpoint"},
        {"name": "stenly-Latitude-E6230", "asset_type": "server"},
    ]
    risks = [
        {"asset_name": "google.com:443", "rating": "high", "normalized_score_100": 68.0, "scenario": "public_timeline"},
        {"asset_name": "google.com:443", "rating": "high", "normalized_score_100": 65.0, "scenario": "public_timeline"},
        {"asset_name": "stenly-Latitude-E6230", "rating": "high", "normalized_score_100": 64.0, "scenario": "public_timeline"},
        {"asset_name": "low-item", "rating": "low", "normalized_score_100": 20.0, "scenario": "public_timeline"},
    ]

    plan = build_plan(assets, risks)

    assert plan["summary"]["total_assets"] == 2
    assert plan["summary"]["total_risks"] == 3
    assert len(plan["wave_1"]) == 1
    assert len(plan["wave_2"]) == 1
    assert len(plan["wave_3"]) == 1
    assert plan["wave_1"][0]["asset_name"] == "google.com:443"
