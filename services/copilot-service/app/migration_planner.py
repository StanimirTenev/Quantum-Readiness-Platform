"""Migration Planner: the fourth deterministic Copilot subagent. Turns
planner-service's algorithmic wave/priority plan (services/planner-service/
app/planner.py) into a plain-language migration narrative -- why each wave
is ordered as it is, what's driving each asset's placement, and whether any
analyzed vendor documents raise a readiness blocker planners should account
for. No LLM call, read-only synthesis over already-computed planner-service
output plus Vendor Intelligence Analyst's readiness matrix, same safety
boundary as the other subagents.

Deliberately does NOT try to join planner-service's per-asset items against
Vendor Intelligence Analyst's per-document readiness_matrix by name --
there is no reliable asset<->vendor-document key in the current data model,
and a fuzzy name match would risk a misleading false-positive link (the
same failure mode fixed in vendor_intelligence_analyst.py's word-boundary
and confidence-attribution bugs). Vendor readiness is surfaced as
document-level context instead: "N vendor document(s) reviewed have
readiness blockers", not attributed to a specific asset.
"""

from __future__ import annotations

from typing import Any

# (planning_reasons code, human-readable phrase). Codes mirror
# services/planner-service/app/planner.py::_planning_reasons. Purely
# internal bookkeeping codes (priority_score_computed, priority_from_*_score,
# wave_cap_from_*) are intentionally omitted -- they describe *how* the
# score was computed, not a fact worth narrating to a human.
PLANNING_REASON_PHRASES: list[tuple[str, str]] = [
    ("stage2_private_key_files", "private key files were found"),
    ("stage2_weak_public_key", "a weak/undersized public key was detected"),
    ("stage2_expiring_certificate", "a certificate close to expiry was found"),
    ("windows_domain_controller", "the host is a domain controller"),
    ("windows_expired_certificates", "expired certificates were found in the certificate store"),
    ("windows_weak_signature_certificates", "certificates with a weak signature algorithm were found"),
    ("stage2_certificate_files", "certificate files are present"),
    ("stage2_tls_config", "TLS configuration was found"),
    ("stage2_ssh_config", "SSH configuration was found"),
    ("stage2_tls_detected", "TLS was observed"),
    ("stage2_crypto_packages", "crypto-related packages are installed"),
    ("windows_large_certificate_estate", "the host has a large certificate store"),
    ("priority_from_urgency_dimension", "elevated urgency"),
    ("priority_from_exposure_dimension", "external exposure"),
    ("priority_from_impact_dimension", "high potential impact"),
]

WAVE_LABELS = {
    "wave_1": "Wave 1 (urgent)",
    "wave_2": "Wave 2 (near-term)",
    "wave_3": "Wave 3 (planned)",
}


def _item_reasons_text(item: dict[str, Any]) -> str:
    reasons = set(item.get("planning_reasons") or [])
    phrases = [phrase for code, phrase in PLANNING_REASON_PHRASES if code in reasons]
    if item.get("vendor_blocked"):
        phrases.append("a vendor readiness blocker is in effect")
    if not phrases:
        return "no specific evidence signals were flagged; placement reflects the base risk score"
    return "; ".join(phrases)


def _narrate_item(item: dict[str, Any]) -> str:
    asset_name = item.get("asset_name", "unknown")
    rating = item.get("rating", "unknown")
    score = item.get("priority_score_100")
    score_text = f"{score:.1f}/100" if isinstance(score, (int, float)) else "an unscored"
    reasons_text = _item_reasons_text(item)
    action = item.get("recommended_action") or "Review and reassess as needed."
    return (
        f"'{asset_name}' ({rating}, priority {score_text}): {reasons_text}. {action}"
    )


def _narrate_wave(wave_key: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    label = WAVE_LABELS.get(wave_key, wave_key)
    if not items:
        summary = f"{label}: no assets currently placed here."
    else:
        blocked = sum(1 for item in items if item.get("vendor_blocked"))
        blocked_clause = f", {blocked} blocked by vendor readiness" if blocked else ""
        summary = f"{label}: {len(items)} asset(s){blocked_clause}."

    return {
        "wave": wave_key,
        "label": label,
        "summary": summary,
        "assets": [
            {
                "asset_name": item.get("asset_name"),
                "rating": item.get("rating"),
                "priority_score_100": item.get("priority_score_100"),
                "vendor_blocked": bool(item.get("vendor_blocked")),
                "narrative": _narrate_item(item),
            }
            for item in items
        ],
    }


def _vendor_readiness_context(readiness_matrix: list[dict[str, Any]]) -> dict[str, Any]:
    blocked_docs = [entry for entry in readiness_matrix if entry.get("has_migration_blocker")]
    if not readiness_matrix:
        note = "No vendor documents have been analyzed by Vendor Intelligence Analyst yet."
    elif blocked_docs:
        names = ", ".join(entry.get("product_hint", entry.get("doc_id", "unknown")) for entry in blocked_docs)
        note = (
            f"{len(blocked_docs)} of {len(readiness_matrix)} analyzed vendor document(s) raise a migration "
            f"blocker: {names}. Confirm whether affected products are in scope before committing to a wave "
            "timeline; this is document-level context, not attributed to a specific asset."
        )
    else:
        note = f"{len(readiness_matrix)} vendor document(s) analyzed; no migration blockers found."

    return {"note": note, "blocked_document_count": len(blocked_docs), "documents_reviewed": len(readiness_matrix)}


def build_migration_plan_summary(plan_data: dict[str, Any], readiness_matrix: list[dict[str, Any]]) -> dict[str, Any]:
    waves = [_narrate_wave(key, plan_data.get(key, [])) for key in ("wave_1", "wave_2", "wave_3")]
    vendor_context = _vendor_readiness_context(readiness_matrix)

    summary = plan_data.get("summary", {})
    narrative_parts = [
        f"Migration plan covers {summary.get('total_assets', 0)} asset(s) with {summary.get('total_risks', 0)} "
        f"scored risk(s): {summary.get('wave_1_count', 0)} in Wave 1, {summary.get('wave_2_count', 0)} in "
        f"Wave 2, {summary.get('wave_3_count', 0)} in Wave 3.",
        vendor_context["note"],
    ]

    return {
        "narrative": " ".join(narrative_parts),
        "summary": summary,
        "waves": waves,
        "vendor_readiness_context": vendor_context,
    }
