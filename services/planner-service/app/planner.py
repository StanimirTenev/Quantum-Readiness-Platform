from __future__ import annotations

from typing import Any

HIGH_PRIORITY_STAGE2_SIGNALS = {
    "private_key_files_detected": "stage2_private_key_files",
    "weak_public_key_detected": "stage2_weak_public_key",
    "expiring_certificate_detected": "stage2_expiring_certificate",
}

MEDIUM_PRIORITY_STAGE2_SIGNALS = {
    "certificate_files_detected": "stage2_certificate_files",
    "tls_config_detected": "stage2_tls_config",
    "ssh_config_detected": "stage2_ssh_config",
    "tls_detected": "stage2_tls_detected",
    "crypto_packages_detected": "stage2_crypto_packages",
}

# Aggregate Windows host signals surfaced by the risk-engine in risk.rationale.
# A domain controller (domain trust anchor) or expired/weak certificates warrant
# an earlier remediation wave; a large certificate estate is a medium signal.
HIGH_PRIORITY_WINDOWS_SIGNALS = {
    "windows_domain_controller": "windows_domain_controller",
    "windows_expired_certificates": "windows_expired_certificates",
    "windows_weak_signature_certificates": "windows_weak_signature_certificates",
}

MEDIUM_PRIORITY_WINDOWS_SIGNALS = {
    "windows_large_certificate_estate": "windows_large_certificate_estate",
}


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
            "priority_score": _priority_score(asset, risk),
            "scenario": risk.get("scenario"),
            "dependency_count": _dependency_count(asset, risk),
            "vendor_blocked": _vendor_blocked(asset, risk),
            "recommended_action": recommend_action(asset, risk),
            "planning_reasons": _planning_reasons(risk),
        }

        score = item["priority_score_100"]
        if score >= 65:
            wave_1.append(item)
        elif score >= 45:
            wave_2.append(item)
        else:
            wave_3.append(item)

    _enforce_stage2_wave_caps(wave_1, wave_2, wave_3)

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
    base_score = _base_score(risk)
    risk_dimensions = risk.get("risk_dimensions", {})
    urgency = _dimension_score(risk_dimensions, "urgency")
    exposure = _dimension_score(risk_dimensions, "exposure")
    impact = _dimension_score(risk_dimensions, "impact")
    confidence_score = _safe_float(risk.get("confidence_score"))

    dimension_boost = (urgency * 0.10) + (exposure * 0.05) + (impact * 0.05)
    confidence_adjustment = 0.0
    if confidence_score is not None and confidence_score >= 80:
        confidence_adjustment = 5.0
    elif confidence_score is not None and confidence_score < 50:
        confidence_adjustment = -5.0

    dependency_boost = min(_dependency_count(asset, risk), 10) * 1.5
    vendor_boost = 8.0 if _vendor_blocked(asset, risk) else 0.0
    stage2_boost = _stage2_priority_boost(risk)
    windows_boost = _windows_priority_boost(risk)
    score = base_score + dimension_boost + confidence_adjustment + dependency_boost + vendor_boost + stage2_boost + windows_boost
    return max(0.0, min(score, 100.0))


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


def _evidence_signals(risk: dict[str, Any]) -> dict[str, Any]:
    stage2_signals = risk.get("stage2_signals", {})
    if not isinstance(stage2_signals, dict):
        return {}
    evidence_signals = stage2_signals.get("evidence_signals", {})
    if not isinstance(evidence_signals, dict):
        return {}
    return evidence_signals


def _stage2_priority_boost(risk: dict[str, Any]) -> float:
    evidence_signals = _evidence_signals(risk)
    if not evidence_signals:
        return 0.0

    boost = 0.0
    if any(bool(evidence_signals.get(signal)) for signal in HIGH_PRIORITY_STAGE2_SIGNALS):
        boost += 15.0
    if any(bool(evidence_signals.get(signal)) for signal in MEDIUM_PRIORITY_STAGE2_SIGNALS):
        boost += 5.0
    return boost


def _windows_flags(risk: dict[str, Any]) -> dict[str, Any]:
    rationale = risk.get("rationale", {})
    return rationale if isinstance(rationale, dict) else {}


def _has_high_priority_windows_signal(risk: dict[str, Any]) -> bool:
    flags = _windows_flags(risk)
    return any(bool(flags.get(signal)) for signal in HIGH_PRIORITY_WINDOWS_SIGNALS)


def _windows_priority_boost(risk: dict[str, Any]) -> float:
    flags = _windows_flags(risk)
    if not flags:
        return 0.0

    boost = 0.0
    if _has_high_priority_windows_signal(risk):
        boost += 15.0
    if any(bool(flags.get(signal)) for signal in MEDIUM_PRIORITY_WINDOWS_SIGNALS):
        boost += 5.0
    return boost


def _planning_reasons(risk: dict[str, Any]) -> list[str]:
    evidence_signals = _evidence_signals(risk)
    reasons: list[str] = ["priority_score_computed"]
    base_reason = _base_score_reason(risk)
    if base_reason:
        reasons.append(base_reason)

    risk_dimensions = risk.get("risk_dimensions", {})
    if _dimension_score(risk_dimensions, "urgency") > 0:
        reasons.append("priority_from_urgency_dimension")
    if _dimension_score(risk_dimensions, "exposure") > 0:
        reasons.append("priority_from_exposure_dimension")
    if _dimension_score(risk_dimensions, "impact") > 0:
        reasons.append("priority_from_impact_dimension")

    confidence_score = _safe_float(risk.get("confidence_score"))
    if confidence_score is not None and confidence_score >= 80:
        reasons.append("priority_from_high_confidence")
    elif confidence_score is not None and confidence_score < 50:
        reasons.append("priority_reduced_low_confidence")

    for signal, reason in HIGH_PRIORITY_STAGE2_SIGNALS.items():
        if bool(evidence_signals.get(signal)):
            reasons.append(reason)
            if signal == "weak_public_key_detected":
                reasons.append("wave_cap_from_weak_public_key")
            if signal == "private_key_files_detected":
                reasons.append("wave_cap_from_private_key_files")
            if signal == "expiring_certificate_detected":
                reasons.append("wave_reason_expiring_certificate")

    for signal, reason in MEDIUM_PRIORITY_STAGE2_SIGNALS.items():
        if bool(evidence_signals.get(signal)):
            reasons.append(reason)

    windows_flags = _windows_flags(risk)
    for signal, reason in HIGH_PRIORITY_WINDOWS_SIGNALS.items():
        if bool(windows_flags.get(signal)):
            reasons.append(reason)
            reasons.append("wave_cap_from_windows_high_signal")
    for signal, reason in MEDIUM_PRIORITY_WINDOWS_SIGNALS.items():
        if bool(windows_flags.get(signal)):
            reasons.append(reason)

    return reasons


def _base_score(risk: dict[str, Any]) -> float:
    for key in ("normalized_score_100", "final_score", "score"):
        value = _safe_float(risk.get(key))
        if value is not None:
            return value
    return 0.0


def _base_score_reason(risk: dict[str, Any]) -> str | None:
    if _safe_float(risk.get("normalized_score_100")) is not None:
        return "priority_from_normalized_score"
    if _safe_float(risk.get("final_score")) is not None:
        return "priority_from_final_score"
    if _safe_float(risk.get("score")) is not None:
        return "priority_from_score"
    return None


def _dimension_score(risk_dimensions: Any, key: str) -> float:
    if not isinstance(risk_dimensions, dict):
        return 0.0
    value = _safe_float(risk_dimensions.get(key))
    return value if value is not None else 0.0


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _enforce_stage2_wave_caps(
    wave_1: list[dict[str, Any]], wave_2: list[dict[str, Any]], wave_3: list[dict[str, Any]]
) -> None:
    cap_reasons = {
        "stage2_private_key_files",
        "stage2_weak_public_key",
        "wave_cap_from_windows_high_signal",
    }
    remaining_wave_3: list[dict[str, Any]] = []
    for item in wave_3:
        reasons = set(item.get("planning_reasons", []))
        if reasons & cap_reasons:
            wave_2.append(item)
        else:
            remaining_wave_3.append(item)

    wave_3[:] = remaining_wave_3
