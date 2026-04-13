from app.planner import build_plan


def test_build_plan_deduplicates_risks_and_splits_into_waves() -> None:
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


def test_build_plan_prioritizes_dependency_heavy_and_vendor_blocked_assets() -> None:
    assets = [
        {"name": "vpn-gateway", "asset_type": "endpoint", "dependency_count": 6},
        {"name": "legacy-hsm", "asset_type": "server", "vendor_blocked": True},
    ]
    risks = [
        {"asset_name": "vpn-gateway", "rating": "medium", "normalized_score_100": 57.0, "scenario": "public_timeline"},
        {"asset_name": "legacy-hsm", "rating": "medium", "normalized_score_100": 58.0, "scenario": "vendor_lag"},
    ]

    plan = build_plan(assets, risks)

    assert plan["wave_1"][0]["asset_name"] == "legacy-hsm"
    assert plan["wave_1"][0]["vendor_blocked"] is True
    assert plan["wave_1"][0]["priority_score_100"] > plan["wave_1"][0]["normalized_score_100"]
    assert plan["wave_1"][1]["asset_name"] == "vpn-gateway"
    assert plan["wave_1"][1]["dependency_count"] == 6
