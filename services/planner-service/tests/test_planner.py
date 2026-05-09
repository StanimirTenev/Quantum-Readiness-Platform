from app.planner import build_plan


def test_build_plan_deduplicates_risks_and_splits_into_waves() -> None:
    assets = [
        {"name": "google.com:443", "asset_type": "endpoint"},
        {"name": "stenly-Latitude-E6230", "asset_type": "server"},
    ]
    risks = [
        {"contract_version": "stage1-v1", "asset_name": "google.com:443", "rating": "high", "normalized_score_100": 68.0, "scenario": "public_timeline"},
        {"contract_version": "stage1-v1", "asset_name": "google.com:443", "rating": "high", "normalized_score_100": 65.0, "scenario": "public_timeline"},
        {"contract_version": "stage1-v1", "asset_name": "stenly-Latitude-E6230", "rating": "high", "normalized_score_100": 64.0, "scenario": "public_timeline"},
        {"contract_version": "stage1-v1", "asset_name": "low-item", "rating": "low", "normalized_score_100": 20.0, "scenario": "public_timeline"},
    ]

    plan = build_plan(assets, risks)

    assert plan["summary"]["total_assets"] == 2
    assert plan["summary"]["total_risks"] == 3
    assert len(plan["wave_1"]) == 1
    assert len(plan["wave_2"]) == 1
    assert len(plan["wave_3"]) == 1
    assert plan["wave_1"][0]["asset_name"] == "google.com:443"
    assert plan["wave_1"][0]["contract_version"] == "stage1-v1"


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


def test_stage2_weak_public_key_detected_not_later_than_wave_2() -> None:
    plan = build_plan(
        assets=[],
        risks=[
            {
                "asset_name": "weak-key-host",
                "rating": "low",
                "normalized_score_100": 10.0,
                "stage2_signals": {"evidence_signals": {"weak_public_key_detected": True}},
            }
        ],
    )

    assert len(plan["wave_3"]) == 0
    assert len(plan["wave_2"]) == 1
    assert plan["wave_2"][0]["asset_name"] == "weak-key-host"
    assert "stage2_weak_public_key" in plan["wave_2"][0]["planning_reasons"]


def test_stage2_private_key_files_detected_not_later_than_wave_2() -> None:
    plan = build_plan(
        assets=[],
        risks=[
            {
                "asset_name": "private-key-host",
                "rating": "low",
                "normalized_score_100": 10.0,
                "stage2_signals": {"evidence_signals": {"private_key_files_detected": True}},
            }
        ],
    )

    assert len(plan["wave_3"]) == 0
    assert len(plan["wave_2"]) == 1
    assert plan["wave_2"][0]["asset_name"] == "private-key-host"
    assert "stage2_private_key_files" in plan["wave_2"][0]["planning_reasons"]


def test_stage2_expiring_certificate_adds_reason() -> None:
    plan = build_plan(
        assets=[],
        risks=[
            {
                "asset_name": "expiring-cert-endpoint",
                "rating": "medium",
                "normalized_score_100": 30.0,
                "stage2_signals": {"evidence_signals": {"expiring_certificate_detected": True}},
            }
        ],
    )

    assert "stage2_expiring_certificate" in plan["wave_2"][0]["planning_reasons"]


def test_stage2_certificate_chain_available_alone_does_not_increase_priority() -> None:
    base_risk = {
        "asset_name": "chain-info-only",
        "rating": "low",
        "normalized_score_100": 30.0,
    }
    plan_without_stage2 = build_plan(assets=[], risks=[base_risk])

    plan_with_informational_stage2 = build_plan(
        assets=[],
        risks=[
            {
                **base_risk,
                "stage2_signals": {"evidence_signals": {"certificate_chain_available": True}},
            }
        ],
    )

    assert plan_without_stage2["wave_3"][0]["priority_score_100"] == plan_with_informational_stage2["wave_3"][0]["priority_score_100"]


def test_stage2_missing_or_unknown_signals_do_not_fail() -> None:
    plan = build_plan(
        assets=[],
        risks=[
            {"asset_name": "missing-signals", "rating": "low", "normalized_score_100": 20.0},
            {
                "asset_name": "unknown-signals",
                "rating": "low",
                "normalized_score_100": 20.0,
                "stage2_signals": {"evidence_signals": {"unknown_flag": True}},
            },
        ],
    )

    assert plan["summary"]["total_risks"] == 2


def test_old_input_without_risk_dimensions_still_works_and_has_priority_score() -> None:
    plan = build_plan(
        assets=[],
        risks=[{"asset_name": "legacy-input", "rating": "medium", "normalized_score_100": 55.0}],
    )

    item = plan["wave_2"][0]
    assert item["priority_score"] == item["priority_score_100"]
    assert "priority_score_computed" in item["planning_reasons"]


def test_priority_score_increases_with_urgency_dimension() -> None:
    base_plan = build_plan(
        assets=[],
        risks=[{"asset_name": "base", "rating": "low", "normalized_score_100": 40.0}],
    )
    urgent_plan = build_plan(
        assets=[],
        risks=[
            {
                "asset_name": "urgent",
                "rating": "low",
                "normalized_score_100": 40.0,
                "risk_dimensions": {"urgency": 100},
            }
        ],
    )

    assert urgent_plan["wave_2"][0]["priority_score"] > base_plan["wave_3"][0]["priority_score"]


def test_high_confidence_adds_small_boost() -> None:
    low_conf = build_plan(
        assets=[],
        risks=[{"asset_name": "low-conf", "rating": "low", "normalized_score_100": 40.0, "confidence_score": 79}],
    )
    high_conf = build_plan(
        assets=[],
        risks=[{"asset_name": "high-conf", "rating": "low", "normalized_score_100": 40.0, "confidence_score": 80}],
    )

    assert high_conf["wave_2"][0]["priority_score"] - low_conf["wave_3"][0]["priority_score"] == 5.0


def test_low_confidence_applies_small_reduction() -> None:
    neutral = build_plan(
        assets=[],
        risks=[{"asset_name": "neutral", "rating": "low", "normalized_score_100": 40.0, "confidence_score": 50}],
    )
    low = build_plan(
        assets=[],
        risks=[{"asset_name": "low", "rating": "low", "normalized_score_100": 40.0, "confidence_score": 49}],
    )

    assert neutral["wave_3"][0]["priority_score"] - low["wave_3"][0]["priority_score"] == 5.0


def test_priority_score_capped_0_to_100() -> None:
    high = build_plan(
        assets=[{"name": "over", "dependency_count": 50, "vendor_blocked": True}],
        risks=[
            {
                "asset_name": "over",
                "normalized_score_100": 99,
                "risk_dimensions": {"urgency": 100, "exposure": 100, "impact": 100},
                "confidence_score": 100,
                "stage2_signals": {"evidence_signals": {"weak_public_key_detected": True}},
            }
        ],
    )
    low = build_plan(
        assets=[],
        risks=[{"asset_name": "under", "normalized_score_100": 1, "confidence_score": 0}],
    )

    assert high["wave_1"][0]["priority_score"] == 100.0
    assert low["wave_3"][0]["priority_score"] == 0.0
