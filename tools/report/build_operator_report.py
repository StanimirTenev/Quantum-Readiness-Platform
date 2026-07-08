#!/usr/bin/env python3
"""Build an operator / executive migration report from an assessment bundle.

Pure and deterministic: input is a JSON bundle of per-asset entries, each
either an `/api/assess` result or (for a persisted Windows host) a
`persisted_risk` record from inventory-service; output is a Markdown
migration report (executive summary, migration waves, findings,
attribution/evidence chains, boundaries).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_VERSION = "operator-report-v1"
_RISK_ORDER = ["minimal", "low", "medium", "high", "critical"]

# Aggregate Windows host signals surfaced by risk-engine in risk.rationale
# (see services/risk-engine WINDOWS_SIGNAL_WEIGHTS). A domain controller or
# expired/weak-signature certificates are high-priority; a large certificate
# estate is medium-priority. Mirrors planner-service's own Windows wave-cap
# logic so a persisted host's report placement agrees with its planner wave.
HIGH_PRIORITY_WINDOWS_RATIONALE = (
    "windows_domain_controller",
    "windows_expired_certificates",
    "windows_weak_signature_certificates",
)
MEDIUM_PRIORITY_WINDOWS_RATIONALE = ("windows_large_certificate_estate",)


def _rank(rating: str | None) -> int:
    try:
        return _RISK_ORDER.index((rating or "minimal").lower())
    except ValueError:
        return 0


def windows_host_view(entry: dict[str, Any]) -> dict[str, Any]:
    """View for a persisted Windows host (source=host scan), whose risk comes
    from aggregate certificate-store signals rather than the crypto-fingerprint
    -> pqc-readiness -> attribution pipeline other assets go through."""
    risk = entry.get("persisted_risk") or {}
    rating = risk.get("rating")
    rationale = risk.get("rationale") or {}
    high_signals = [s for s in HIGH_PRIORITY_WINDOWS_RATIONALE if rationale.get(s)]
    medium_signals = [s for s in MEDIUM_PRIORITY_WINDOWS_RATIONALE if rationale.get(s)]
    signal_summary = ", ".join(high_signals + medium_signals)

    return {
        "asset_name": entry.get("asset_name") or "unknown",
        "application": entry.get("application"),
        "readiness": "unknown",  # not classified via crypto-fingerprint (aggregate host evidence, not per-algorithm)
        "risk": rating,
        "risk_rank": _rank(rating),
        "hndl": False,
        "quantum_vulnerable": 0,
        "pqc_ready": 0,
        "weak": 0,
        "top_vulnerability": f"Windows: {signal_summary}" if signal_summary else "-",
        "chain": [],
        "source": "windows_host",
        "windows_high_signals": high_signals,
        "windows_medium_signals": medium_signals,
        "windows_priority_score_100": risk.get("normalized_score_100"),
    }


def asset_view(entry: dict[str, Any]) -> dict[str, Any]:
    if "persisted_risk" in entry:
        return windows_host_view(entry)
    assess = entry.get("assess") or {}
    fp = (assess.get("fingerprint") or {}).get("summary") or {}
    readiness = (assess.get("pqc_readiness") or {}).get("readiness") or "unknown"
    risk = (assess.get("risk") or {}).get("rating")
    attribution = (assess.get("attribution") or {}).get("attributed_findings") or []

    top_vuln = None
    chain: list[str] = []
    for finding in attribution:
        vuln = finding.get("vulnerability") or {}
        if vuln.get("quantum_vulnerable"):
            top_vuln = f"{vuln.get('algorithm_family')} ({vuln.get('classification')})"
            chain = finding.get("chain") or []
            break
    if top_vuln is None and attribution:
        vuln = attribution[0].get("vulnerability") or {}
        top_vuln = f"{vuln.get('algorithm_family')} ({vuln.get('classification')})"
        chain = attribution[0].get("chain") or []

    return {
        "asset_name": entry.get("asset_name") or "unknown",
        "application": entry.get("application"),
        "readiness": readiness,
        "risk": risk,
        "risk_rank": _rank(risk),
        "hndl": bool(fp.get("hndl_exposure")),
        "quantum_vulnerable": int(fp.get("quantum_vulnerable_count") or 0),
        "pqc_ready": int(fp.get("pqc_ready_count") or 0),
        "weak": int(fp.get("weak_count") or 0),
        "top_vulnerability": top_vuln or "-",
        "chain": chain,
    }


def assign_windows_host_wave(view: dict[str, Any]) -> int:
    """Mirrors planner-service's Windows priority-score + wave-cap semantics
    (see services/planner-service/app/planner.py): +15 for a high-priority
    signal, +5 for a medium one, same 65/45 thresholds, and a high-priority
    signal caps the wave at 2 even if the boosted score still lands in 3."""
    score = float(view.get("windows_priority_score_100") or 0.0)
    if view["windows_high_signals"]:
        score += 15.0
    if view["windows_medium_signals"]:
        score += 5.0
    score = max(0.0, min(score, 100.0))

    if score >= 65:
        wave = 1
    elif score >= 45:
        wave = 2
    else:
        wave = 3
    if wave == 3 and view["windows_high_signals"]:
        wave = 2
    return wave


def assign_wave(view: dict[str, Any]) -> int:
    if view.get("source") == "windows_host":
        return assign_windows_host_wave(view)
    readiness = view["readiness"]
    if readiness == "pqc_ready":
        return 3
    if view["quantum_vulnerable"] == 0 and not view["hndl"]:
        return 3
    # urgent: high/critical risk that is exposed now (HNDL) or fully classical
    if view["risk_rank"] >= _rank("high") and (view["hndl"] or readiness == "classical_only"):
        return 1
    if readiness in ("classical_only", "hybrid_capable") and view["quantum_vulnerable"] > 0:
        return 2
    if readiness == "vendor_blocked":
        return 3
    return 2


_WAVE_TITLES = {
    1: "Wave 1 — urgent (harvest-now-decrypt-later / critical classical-only)",
    2: "Wave 2 — near-term (classical-only or hybrid, quantum-vulnerable)",
    3: "Wave 3 — planned (post-quantum ready, vendor-blocked, or low exposure)",
}


def build_report(bundle: dict[str, Any]) -> str:
    generated = bundle.get("generated_at") or datetime.now(timezone.utc).isoformat()
    environment = bundle.get("environment") or "unspecified"
    views = [asset_view(e) for e in (bundle.get("assets") or []) if isinstance(e, dict)]
    for v in views:
        v["wave"] = assign_wave(v)

    total = len(views)
    classical = sum(1 for v in views if v["readiness"] == "classical_only")
    hybrid = sum(1 for v in views if v["readiness"] == "hybrid_capable")
    pqc = sum(1 for v in views if v["readiness"] == "pqc_ready")
    vendor_blocked = sum(1 for v in views if v["readiness"] == "vendor_blocked")
    hndl = sum(1 for v in views if v["hndl"])
    weak = sum(v["weak"] for v in views)
    critical = sum(1 for v in views if v["risk"] and v["risk"].lower() == "critical")
    wave1 = [v for v in views if v["wave"] == 1]
    highest = max((v["risk"] for v in views if v["risk"]), key=_rank, default="minimal")

    if wave1:
        action = f"Begin Wave 1 now — {len(wave1)} asset(s) are quantum-vulnerable and exposed (HNDL or critical)."
    elif classical or hybrid:
        action = "Plan Wave 2 — classical/hybrid assets remain quantum-vulnerable but are not immediately exposed."
    else:
        action = "Posture is largely post-quantum ready; maintain monitoring and vendor tracking."

    L: list[str] = []
    L += [
        "# Quantum Readiness — Migration Assessment Report",
        "",
        "> Advisory report. QRP discovers, assesses and plans — it does not execute changes.",
        "> Local-first: evidence stays within the deployment boundary. Not a claim of",
        "> production readiness or certification.",
        "",
        f"- Report version: `{REPORT_VERSION}`",
        f"- Generated: {generated}",
        f"- Environment: {environment}",
        "",
        "## Executive Summary",
        "",
        f"- Assets assessed: **{total}**",
        f"- PQC readiness: **{classical} classical-only**, {hybrid} hybrid-capable, {pqc} pqc-ready, {vendor_blocked} vendor-blocked",
        f"- Harvest-now-decrypt-later exposure: **{hndl}** asset(s)",
        f"- Weak keys / deprecated primitives: **{weak}**",
        f"- Highest risk rating: **{highest}**" + (f" ({critical} critical)" if critical else ""),
        f"- Recommended action: **{action}**",
        "",
    ]

    L += ["## Migration Waves", ""]
    for wave in (1, 2, 3):
        items = [v for v in views if v["wave"] == wave]
        L += [f"### {_WAVE_TITLES[wave]}", ""]
        if not items:
            L += ["_No assets in this wave._", ""]
            continue
        L += ["| Asset | Application | Readiness | Risk | HNDL | Vulnerability |",
              "| --- | --- | --- | --- | --- | --- |"]
        for v in sorted(items, key=lambda x: (-x["risk_rank"], x["asset_name"])):
            L.append(f"| {v['asset_name']} | {v['application'] or '-'} | {v['readiness']} | {v['risk'] or '-'} | {'yes' if v['hndl'] else 'no'} | {v['top_vulnerability']} |")
        L.append("")

    L += ["## Findings by Asset", "",
          "| Asset | Readiness | Risk | Q-vulnerable | HNDL | Weak | Top vulnerability |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for v in sorted(views, key=lambda x: (-x["risk_rank"], x["asset_name"])):
        L.append(f"| {v['asset_name']} | {v['readiness']} | {v['risk'] or '-'} | {v['quantum_vulnerable']} | {'yes' if v['hndl'] else 'no'} | {v['weak']} | {v['top_vulnerability']} |")
    L.append("")

    L += ["## Attribution & Evidence Chains", "",
          "Each vulnerable finding is attributed as: vulnerability → location → service/application → asset → certificate/library/pipeline.", ""]
    any_chain = False
    for v in views:
        if v["chain"]:
            any_chain = True
            L.append(f"- **{v['asset_name']}**: " + " → ".join(str(c) for c in v["chain"]))
    if not any_chain:
        L.append("_No attributed vulnerability chains in this assessment._")
    L.append("")

    L += [
        "## Methodology & Boundaries",
        "",
        "- Deterministic analysis pipeline: crypto-fingerprint → pqc-readiness → finding-attribution → risk-engine.",
        "- Classical public-key algorithms (RSA, DSA, DH, ECDSA, ECDH, Ed25519) are quantum-vulnerable (Shor); ML-KEM / ML-DSA / SLH-DSA / Falcon are post-quantum.",
        "- Harvest-now-decrypt-later applies to confidentiality primitives (key exchange / transport), not signatures.",
        "- No production changes are made. Trust Zone 4 integrations (CA/KMS/HSM/signing) are approval-gated and currently dry-run only.",
        "- Migration waves are advisory; operator review and sign-off are required before any change.",
        "- Persisted Windows hosts (readiness `unknown`) are risk-scored from aggregate certificate-store/domain signals, not per-algorithm classification; their wave reflects the same signals the planner uses (domain controller, expired/weak-signature certificates, estate size).",
        "",
    ]
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an operator/exec migration report from an assessment bundle.")
    parser.add_argument("--input", required=True, help="Path to the assessment bundle JSON.")
    parser.add_argument("--out", required=True, help="Path to write the Markdown report.")
    args = parser.parse_args()

    bundle = json.loads(Path(args.input).read_text(encoding="utf-8"))
    report = build_report(bundle)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
