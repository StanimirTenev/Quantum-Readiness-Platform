from __future__ import annotations

from typing import Any


def build_plan(assets: list[dict[str, Any]], risks: list[dict[str, Any]]) -> dict[str, Any]:
    asset_map = {asset["name"]: asset for asset in assets}

    # keep only highest-score risk per asset_name
    deduped: dict[str, dict[str, Any]] = {}
    for risk in risks:
        asset_name = risk.get("asset_name", "unknown")
        current = deduped.get(asset_name)
        if current is None or risk.get("normalized_score_100", 0) > current.get("normalized_score_100", 0):
            deduped[asset_name] = risk

    ordered_risks = sorted(
        deduped.values(),
        key=lambda risk: _ordering_tuple(
            asset_map.get(risk.get("asset_name", "unknown"), {}), risk
        ),
        reverse=True,
    )

    wave_1: list[dict[str, Any]] = []
    wave_2: list[dict[str, Any]] = []
    wave_3: list[dict[str, Any]] = []

    for risk in ordered_risks:
        asset_name = risk.get("asset_name", "unknown")
        asset = asset_map.get(asset_name, {"name": asset_name, "asset_type": "unknown"})

        item = {
            "contract_version": risk.get("contract_version", "stage1-v1"),
            "asset_name": asset_name,
            "asset_type": asset.get("asset_type", "unknown"),
            "rating": risk.get("rating"),
            "normalized_score_100": risk.get("normalized_score_100"),
            "priority_score_100": _priority_score(asset, risk),
            "scenario": risk.get("scenario"),
            "dependency_count": _dependency_count(asset, risk),
            "vendor_blocked": _vendor_blocked(asset, risk),
            "recommended_action": recommend_action(asset, risk),
        }

        score = item["priority_score_100"]
        if score >= 65:
            wave_1.append(item)
        elif score >= 45:
            wave_2.append(item)
        else:
            wave_3.append(item)

    return {
        "summary": {
            "total_assets": len(assets),
            "total_risks": len(ordered_risks),
            "wave_1_count": len(wave_1),
            "wave_2_count": len(wave_2),
            "wave_3_count": len(wave_3),
        },
        "wave_1": wave_1,
        "wave_2": wave_2,
        "wave_3": wave_3,
        "execution_plan": {
            "phase_1": "Address highest-risk externally exposed endpoints and critical host assets.",
            "phase_2": "Validate crypto dependencies, inventory gaps, and migration blockers.",
            "phase_3": "Prepare staged migration, retesting, and documentation updates.",
        },
    }


def recommend_action(asset: dict[str, Any], risk: dict[str, Any]) -> str:
    asset_type = asset.get("asset_type", "unknown")
    rating = risk.get("rating", "unknown")
    dependency_count = _dependency_count(asset, risk)
    vendor_blocked = _vendor_blocked(asset, risk)

    if vendor_blocked:
        return "Vendor readiness blocker detected. Initiate vendor escalation and tracked exception path."
    if dependency_count >= 5:
        return "High dependency depth detected. Start migration design and sequencing in wave 1."

    if asset_type == "endpoint":
        return "Review TLS configuration, certificate algorithms, and PQC migration path."
    if asset_type == "server":
        return "Review host crypto stack, OpenSSL usage, SSH posture, and long-term exposure."
    if rating == "critical":
        return "Escalate immediately and schedule wave 1 migration."
    if rating == "high":
        return "Include in near-term migration wave."
    return "Track and reassess after higher-priority items."


def _priority_score(asset: dict[str, Any], risk: dict[str, Any]) -> float:
    base_score = float(risk.get("normalized_score_100", 0))
    dependency_boost = min(_dependency_count(asset, risk), 10) * 1.5
    vendor_boost = 8.0 if _vendor_blocked(asset, risk) else 0.0
    return min(base_score + dependency_boost + vendor_boost, 100.0)


def _ordering_tuple(asset: dict[str, Any], risk: dict[str, Any]) -> tuple[float, int, int]:
    return (
        _priority_score(asset, risk),
        int(_vendor_blocked(asset, risk)),
        _dependency_count(asset, risk),
    )


def _dependency_count(asset: dict[str, Any], risk: dict[str, Any]) -> int:
    raw = asset.get("dependency_count", risk.get("dependency_count", 0))
    try:
        return max(int(raw), 0)
    except (TypeError, ValueError):
        return 0


def _vendor_blocked(asset: dict[str, Any], risk: dict[str, Any]) -> bool:
    return bool(asset.get("vendor_blocked", risk.get("vendor_blocked", False)))
