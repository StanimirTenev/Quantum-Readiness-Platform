from __future__ import annotations

from typing import Any


def normalize_text(value: str) -> str:
    return value.strip().lower()


def dedupe_risks_by_asset(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best: dict[str, dict[str, Any]] = {}
    for risk in risks:
        asset_name = risk.get("asset_name", "unknown")
        current = best.get(asset_name)
        if current is None or risk.get("normalized_score_100", 0) > current.get("normalized_score_100", 0):
            best[asset_name] = risk
    return list(best.values())


def build_overview(
    assets: list[dict[str, Any]],
    scans: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    deduped_risks = sorted(
        dedupe_risks_by_asset(risks),
        key=lambda x: x.get("normalized_score_100", 0),
        reverse=True,
    )

    task_status_counts: dict[str, int] = {}
    for task in tasks:
        status = task.get("status", "unknown")
        task_status_counts[status] = task_status_counts.get(status, 0) + 1

    return {
        "asset_count": len(assets),
        "scan_count": len(scans),
        "risk_count": len(deduped_risks),
        "task_count": len(tasks),
        "approval_count": len(approvals),
        "top_risks": deduped_risks[:5],
        "plan_summary": plan.get("summary", {}),
        "task_status_counts": task_status_counts,
    }


def search_all(
    query: str,
    assets: list[dict[str, Any]],
    scans: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    q = normalize_text(query)

    matched_assets = [
        item for item in assets
        if q in normalize_text(item.get("name", "")) or q in normalize_text(item.get("asset_type", ""))
    ]

    matched_scans = [
        item for item in scans
        if q in normalize_text(item.get("source", ""))
        or q in normalize_text(item.get("id", ""))
        or q in normalize_text(str(item.get("host_inventory", "")))
        or q in normalize_text(str(item.get("tls_evidence", "")))
    ]

    matched_risks = [
        item for item in dedupe_risks_by_asset(risks)
        if q in normalize_text(item.get("asset_name", ""))
        or q in normalize_text(item.get("rating", ""))
        or q in normalize_text(item.get("scenario", ""))
    ]

    matched_tasks = [
        item for item in tasks
        if q in normalize_text(item.get("title", ""))
        or q in normalize_text(item.get("asset_name", ""))
        or q in normalize_text(item.get("status", ""))
        or q in normalize_text(item.get("wave", ""))
    ]

    return {
        "assets": matched_assets,
        "scans": matched_scans,
        "risks": matched_risks,
        "tasks": matched_tasks,
    }


def get_asset_bundle(
    asset_name: str,
    assets: list[dict[str, Any]],
    scans: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> dict[str, Any]:
    q = normalize_text(asset_name)

    asset_matches = [a for a in assets if normalize_text(a.get("name", "")) == q]
    scan_matches = [
        s for s in scans
        if q in normalize_text(str(s.get("host_inventory", "")))
        or q in normalize_text(str(s.get("tls_evidence", "")))
    ]
    risk_matches = [r for r in dedupe_risks_by_asset(risks) if normalize_text(r.get("asset_name", "")) == q]
    task_matches = [t for t in tasks if normalize_text(t.get("asset_name", "")) == q]

    return {
        "assets": asset_matches,
        "scans": scan_matches,
        "risks": risk_matches,
        "tasks": task_matches,
    }
