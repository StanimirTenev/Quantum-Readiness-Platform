#!/usr/bin/env python3
"""Build an operator / executive migration report from an assessment bundle.

Pure and deterministic: input is a JSON bundle of per-asset `/api/assess`
results; output is a Markdown migration report (executive summary, migration
waves, findings, attribution/evidence chains, boundaries).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_VERSION = "operator-report-v1"
_RISK_ORDER = ["minimal", "low", "medium", "high", "critical"]


def _rank(rating: str | None) -> int:
    try:
        return _RISK_ORDER.index((rating or "minimal").lower())
    except ValueError:
        return 0


def asset_view(entry: dict[str, Any]) -> dict[str, Any]:
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


def assign_wave(view: dict[str, Any]) -> int:
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
