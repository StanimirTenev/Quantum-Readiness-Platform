from app.search import build_overview, get_asset_bundle, search_all


def test_build_overview() -> None:
    result = build_overview(
        assets=[{"name": "google.com:443"}],
        scans=[{"id": "scan-1"}],
        risks=[
            {"asset_name": "google.com:443", "normalized_score_100": 68.0},
            {"asset_name": "google.com:443", "normalized_score_100": 65.0},
        ],
        tasks=[{"status": "draft"}],
        approvals=[{"task_id": "1"}],
        plan={"summary": {"wave_1_count": 1}},
    )
    assert result["asset_count"] == 1
    assert result["risk_count"] == 1
    assert result["task_status_counts"]["draft"] == 1


def test_search_all() -> None:
    results = search_all(
        "google",
        assets=[{"name": "google.com:443", "asset_type": "endpoint"}],
        scans=[{"source": "network", "tls_evidence": {"target": "google.com:443"}}],
        risks=[{"asset_name": "google.com:443", "rating": "high", "scenario": "public_timeline", "normalized_score_100": 68.0}],
        tasks=[{"title": "Review google.com:443", "asset_name": "google.com:443", "status": "draft", "wave": "wave_1"}],
    )
    assert len(results["assets"]) == 1
    assert len(results["scans"]) == 1
    assert len(results["risks"]) == 1
    assert len(results["tasks"]) == 1


def test_asset_bundle() -> None:
    result = get_asset_bundle(
        "google.com:443",
        assets=[{"name": "google.com:443"}],
        scans=[{"tls_evidence": {"target": "google.com:443"}}],
        risks=[{"asset_name": "google.com:443", "normalized_score_100": 68.0}],
        tasks=[{"asset_name": "google.com:443"}],
    )
    assert len(result["assets"]) == 1
    assert len(result["risks"]) == 1
    assert len(result["tasks"]) == 1
