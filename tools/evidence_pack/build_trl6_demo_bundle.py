from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    title: str
    path: str
    category: str
    required_for_review: bool
    notes: str


ARTIFACT_SPECS: list[ArtifactSpec] = [
    ArtifactSpec("trl6_readiness_report", "TRL6 Readiness Report", "reports/trl6/trl6-readiness-report.md", "trl6_readiness", True, "Primary TRL6 readiness validation report for operator review."),
    ArtifactSpec("trl6_operator_summary", "Operator Review Summary", "reports/trl6/operator-review-summary.md", "operator_review", True, "Prepared operator summary and review context."),
    ArtifactSpec("trl6_operator_checklist", "Operator Demo Checklist", "reports/trl6/operator-demo-checklist.md", "operator_review", True, "Operator checklist/sign-off procedure input."),
    ArtifactSpec("trl6_known_limitations", "Known Limitations", "reports/trl6/known-limitations.md", "limitations", True, "Current limitations that must be reviewed before sign-off."),
    ArtifactSpec("trl6_readiness_plan", "TRL6 Readiness Plan", "docs/trl6-readiness-plan.md", "trl6_readiness", False, "Planning reference for readiness scope."),
    ArtifactSpec("trl6_review_boundary", "TRL6 Operator Review Boundary", "docs/trl6-operator-review-boundary.md", "operator_review", True, "Operator review boundary statements and restrictions."),
    ArtifactSpec("evidence_pack_index_md", "Evidence Pack Index (Markdown)", "reports/evidence-pack/evidence-pack-index.md", "evidence_index", True, "Human-readable evidence pack index."),
    ArtifactSpec("evidence_pack_index_json", "Evidence Pack Index (JSON)", "reports/evidence-pack/evidence-pack-index.json", "evidence_index", True, "Machine-readable evidence pack index."),
    ArtifactSpec("graph_api_readonly_smoke", "Graph API Read-only Smoke Report", "reports/graph/latest/graph-api-readonly-smoke-report.md", "graph_validation", False, "Read-only graph API validation artifact."),
    ArtifactSpec("graph_snapshot_loader_smoke", "Graph Snapshot Loader Report", "reports/graph/latest/graph-snapshot-loader-report.md", "graph_validation", False, "Graph snapshot loader validation artifact."),
    ArtifactSpec("copilot_safety_contract_smoke", "Copilot Safety Contract Smoke Report", "reports/copilot/safety-contract-smoke-report.md", "copilot_validation", False, "Copilot disabled-safe safety contract artifact."),
    ArtifactSpec("stage2_inventory_smoke", "Stage 2 Inventory Smoke Report", "reports/stage2-inventory-smoke-report.md", "stage_validation", False, "Stage 2 inventory validation artifact."),
    ArtifactSpec("stage2_e2e_smoke", "Stage 2 E2E Smoke Report", "reports/stage2-e2e-smoke-report.md", "stage_validation", False, "Stage 2 end-to-end validation artifact."),
    ArtifactSpec("stage3_risk_planning_smoke", "Stage 3 Risk Planning Smoke Report", "reports/stage3-risk-planning-smoke-report.md", "stage_validation", False, "Stage 3 risk planning validation artifact."),
    ArtifactSpec("trl_validation_report", "TRL Validation Report", "reports/trl-validation-report.md", "trl6_readiness", True, "Cross-stage TRL validation status artifact."),
    ArtifactSpec("repository_checkpoint_status", "Repository Checkpoint Current Status", "docs/repository-checkpoint-current-status.md", "repository_status", True, "Current repository readiness/status context."),
]


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_status_hint(text: str) -> str:
    lines = text.splitlines()

    fail_patterns = [
        re.compile(r"\boverall\s+result\s*:\s*fail\b", re.IGNORECASE),
        re.compile(r"\bresult\s*:\s*fail\b", re.IGNORECASE),
        re.compile(r"\bstatus\s*:\s*fail\b", re.IGNORECASE),
        re.compile(r"\bsmoke\b.*\bfail\b", re.IGNORECASE),
    ]
    pass_patterns = [
        re.compile(r"\boverall\s+result\s*:\s*pass\b", re.IGNORECASE),
        re.compile(r"\bresult\s*:\s*pass\b", re.IGNORECASE),
        re.compile(r"\bstatus\s*:\s*pass\b", re.IGNORECASE),
        re.compile(r"\bsmoke\b.*\bpass\b", re.IGNORECASE),
    ]

    for line in lines:
        if any(p.search(line) for p in fail_patterns):
            return "FAIL"
    for line in lines:
        if any(p.search(line) for p in pass_patterns):
            return "PASS"
    return "UNKNOWN"


def scan_artifact(repo_root: Path, spec: ArtifactSpec) -> dict[str, Any]:
    artifact_path = repo_root / spec.path
    record: dict[str, Any] = {
        "artifact_id": spec.artifact_id,
        "title": spec.title,
        "path": spec.path,
        "category": spec.category,
        "exists": artifact_path.exists(),
        "required_for_review": spec.required_for_review,
        "status_hint": "UNKNOWN",
        "notes": spec.notes,
    }
    if not artifact_path.exists():
        return record

    stat = artifact_path.stat()
    text = artifact_path.read_text(encoding="utf-8", errors="replace")
    record.update(
        {
            "size_bytes": stat.st_size,
            "sha256": compute_sha256(artifact_path),
            "modified_time_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "status_hint": detect_status_hint(text),
        }
    )
    return record


def build_index(repo_root: Path) -> dict[str, Any]:
    artifacts = [scan_artifact(repo_root, spec) for spec in ARTIFACT_SPECS]
    present = sum(1 for a in artifacts if a["exists"])
    required_present = sum(1 for a in artifacts if a["required_for_review"] and a["exists"])
    required_missing = sum(1 for a in artifacts if a["required_for_review"] and not a["exists"])

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Deterministic TRL6 demo evidence bundle for operator review/export without regenerating source evidence.",
        "summary": {
            "total_artifacts": len(artifacts),
            "present": present,
            "missing": len(artifacts) - present,
            "required_present": required_present,
            "required_missing": required_missing,
            "pass_hint_count": sum(1 for a in artifacts if a["status_hint"] == "PASS"),
            "fail_hint_count": sum(1 for a in artifacts if a["status_hint"] == "FAIL"),
            "unknown_hint_count": sum(1 for a in artifacts if a["status_hint"] == "UNKNOWN"),
        },
        "artifacts": artifacts,
    }


def build_markdown(index: dict[str, Any]) -> str:
    s = index["summary"]
    lines = [
        "# TRL6 Demo Evidence Bundle Index",
        "",
        f"UTC timestamp: {index['generated_at_utc']}",
        "",
        "## Purpose",
        index["purpose"],
        "",
        "## Bundle Summary",
        "",
        "| total artifacts | present | missing | required_present | required_missing | pass_hint_count | fail_hint_count | unknown_hint_count |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| {s['total_artifacts']} | {s['present']} | {s['missing']} | {s['required_present']} | {s['required_missing']} | {s['pass_hint_count']} | {s['fail_hint_count']} | {s['unknown_hint_count']} |",
        "",
        "## Artifact Table",
        "",
        "| category | artifact_id | path | required | exists | status_hint | sha256 short prefix |",
        "|---|---|---|---|---|---|---|",
    ]
    for artifact in index["artifacts"]:
        sha_prefix = artifact.get("sha256", "")[:12] if artifact["exists"] else ""
        lines.append(
            f"| {artifact['category']} | {artifact['artifact_id']} | `{artifact['path']}` | {artifact['required_for_review']} | {artifact['exists']} | {artifact['status_hint']} | `{sha_prefix}` |"
        )

    lines.extend(
        [
            "",
            "## Review Boundary Statements",
            "- This bundle supports TRL6 demo/operator review only.",
            "- TRL 6 achieved is not claimed by this bundle.",
            "- Production readiness is not claimed by this bundle.",
            "- This bundle does not run tests, start services, or regenerate evidence.",
            "",
            "## Next Review Action",
            "- operator must review readiness report",
            "- operator must review known limitations",
            "- operator must complete checklist/sign-off",
            "- relevant-environment demo evidence must be attached before TRL6 achieved wording is used",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(repo_root: Path, index: dict[str, Any]) -> None:
    out_dir = repo_root / "reports/trl6/demo-bundle"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "trl6-demo-bundle-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    (out_dir / "trl6-demo-bundle-index.md").write_text(build_markdown(index), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic TRL6 demo evidence bundle index from local artifacts.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    index = build_index(repo_root)
    write_outputs(repo_root, index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
