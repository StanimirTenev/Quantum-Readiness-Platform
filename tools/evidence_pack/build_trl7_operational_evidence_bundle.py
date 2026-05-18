from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    title: str
    path: str
    category: str
    required_for_review: bool
    notes: str


ARTIFACT_SPECS: list[ArtifactSpec] = [
    ArtifactSpec("trl7_operational_dry_run_report", "TRL7 Operational Dry-Run Report", "reports/trl7/trl7-operational-dry-run-report.md", "operational_dry_run", True, "Deterministic dry-run command/report orchestration artifact."),
    ArtifactSpec("trl7_operational_readiness_report", "TRL7 Operational Readiness Report", "reports/trl7/trl7-operational-readiness-report.md", "operational_readiness", True, "Operational readiness framing and constraints report."),
    ArtifactSpec("trl7_operational_pilot_checklist", "TRL7 Operational Pilot Checklist", "reports/trl7/trl7-operational-pilot-checklist.md", "operator_review", True, "Operator/reviewer checklist and sign-off preparation."),
    ArtifactSpec("trl7_operational_known_limitations", "TRL7 Operational Dry-Run Known Limitations", "reports/trl7/trl7-operational-dry-run-known-limitations.md", "limitations", True, "Known dry-run/pilot limitations to review before any claim language."),
    ArtifactSpec("repository_checkpoint_status", "Repository Checkpoint Current Status", "docs/repository-checkpoint-current-status.md", "repository_status", True, "Current checkpoint status and review boundaries."),
    ArtifactSpec("operational_evidence_safety_scan_report_md", "Operational Evidence Safety Scan Report (Markdown)", "reports/trl7/operational-evidence-safety-scan-report.md", "safety_scan", True, "Operational evidence safety scan summary; review before external sharing."),
    ArtifactSpec("operational_evidence_safety_scan_report_json", "Operational Evidence Safety Scan Report (JSON)", "reports/trl7/operational-evidence-safety-scan-report.json", "safety_scan", True, "Operational evidence safety scan structured findings for export/review."),
    ArtifactSpec("trl7_bundle_design", "TRL7 Operational Evidence Bundle Design", "docs/trl7-operational-evidence-bundle-design.md", "design_reference", False, "Design reference for deterministic indexing scope."),
]


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_status_hint(text: str) -> str:
    lines = text.splitlines()
    normalized_lines = [line.replace("**", "") for line in lines]
    fail_patterns = [re.compile(r"\boverall\s+result\s*:\s*fail\b", re.IGNORECASE), re.compile(r"\bresult\s*:\s*fail\b", re.IGNORECASE), re.compile(r"\bstatus\s*:\s*fail\b", re.IGNORECASE)]
    pass_patterns = [re.compile(r"\boverall\s+result\s*:\s*pass\b", re.IGNORECASE), re.compile(r"\bresult\s*:\s*pass\b", re.IGNORECASE), re.compile(r"\bstatus\s*:\s*pass\b", re.IGNORECASE)]
    review_required_patterns = [re.compile(r"\boverall\s+result\s*:\s*review_required\b", re.IGNORECASE), re.compile(r"\bresult\s*:\s*review_required\b", re.IGNORECASE), re.compile(r"\bstatus\s*:\s*review_required\b", re.IGNORECASE)]
    for line in normalized_lines:
        if any(p.search(line) for p in fail_patterns):
            return "FAIL"
    for line in normalized_lines:
        if any(p.search(line) for p in pass_patterns):
            return "PASS"
    for line in normalized_lines:
        if any(p.search(line) for p in review_required_patterns):
            return "REVIEW_REQUIRED"
    return "UNKNOWN"


def scan_artifact(repo_root: Path, spec: ArtifactSpec) -> dict[str, Any]:
    artifact_path = repo_root / spec.path
    record: dict[str, Any] = {
        "artifact_id": spec.artifact_id,
        "title": spec.title,
        "path": spec.path,
        "category": spec.category,
        "exists": artifact_path.exists(),
        "present": artifact_path.exists(),
        "required_for_review": spec.required_for_review,
        "required_for_trl7_review": spec.required_for_review,
        "contains_secrets_expected": False,
        "reviewed_by_operator": False,
        "status_hint": "UNKNOWN",
        "notes": spec.notes,
    }
    if not artifact_path.exists():
        return record

    stat = artifact_path.stat()
    text = artifact_path.read_text(encoding="utf-8", errors="replace")
    record.update({
        "size_bytes": stat.st_size,
        "sha256": compute_sha256(artifact_path),
        "modified_time_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        "status_hint": detect_status_hint(text),
    })
    return record


def build_index(repo_root: Path) -> dict[str, Any]:
    artifacts = [scan_artifact(repo_root, spec) for spec in ARTIFACT_SPECS]
    present = sum(1 for a in artifacts if a["exists"])
    required_present = sum(1 for a in artifacts if a["required_for_review"] and a["exists"])
    required_missing = sum(1 for a in artifacts if a["required_for_review"] and not a["exists"])
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Deterministic TRL7 operational evidence bundle indexing/preparation from local dry-run and pilot-preparation artifacts.",
        "summary": {
            "total_artifacts": len(artifacts),
            "present": present,
            "missing": len(artifacts) - present,
            "required_present": required_present,
            "required_missing": required_missing,
            "pass_hint_count": sum(1 for a in artifacts if a["status_hint"] == "PASS"),
            "fail_hint_count": sum(1 for a in artifacts if a["status_hint"] == "FAIL"),
            "unknown_hint_count": sum(1 for a in artifacts if a["status_hint"] == "UNKNOWN"),
            "review_required_count": sum(1 for a in artifacts if a["required_for_review"] and a["status_hint"] != "PASS"),
        },
        "artifacts": artifacts,
    }


def build_markdown(index: dict[str, Any]) -> str:
    s = index["summary"]
    lines = [
        "# TRL7 Operational Evidence Bundle Index",
        "",
        f"UTC timestamp: {index['generated_at_utc']}",
        "",
        "## Purpose",
        index["purpose"],
        "",
        "## Bundle Summary",
        "",
        "| total artifacts | present | missing | required_present | required_missing | pass_hint_count | fail_hint_count | unknown_hint_count | review_required_count |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| {s['total_artifacts']} | {s['present']} | {s['missing']} | {s['required_present']} | {s['required_missing']} | {s['pass_hint_count']} | {s['fail_hint_count']} | {s['unknown_hint_count']} | {s['review_required_count']} |",
        "",
        "## Artifact Table",
        "",
        "| category | artifact_id | path | required | exists | status_hint | sha256 short prefix |",
        "|---|---|---|---|---|---|---|",
    ]
    for artifact in index["artifacts"]:
        sha_prefix = artifact.get("sha256", "")[:12] if artifact["exists"] else ""
        lines.append(f"| {artifact['category']} | {artifact['artifact_id']} | `{artifact['path']}` | {artifact['required_for_review']} | {artifact['exists']} | {artifact['status_hint']} | `{sha_prefix}` |")
    lines.extend([
        "",
        "## Review Boundary Statements",
        "- This bundle supports TRL7 operational pilot preparation only.",
        "- TRL 7 achieved is not claimed by this bundle.",
        "- Production readiness is not claimed by this bundle.",
        "- This bundle does not run tests, start services, regenerate evidence, or perform remediation.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(repo_root: Path, index: dict[str, Any]) -> None:
    out_dir = repo_root / "reports/trl7/operational-evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "trl7-operational-evidence-bundle-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    (out_dir / "trl7-operational-evidence-bundle-index.md").write_text(build_markdown(index), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic TRL7 operational evidence bundle index from local artifacts.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    index = build_index(repo_root)
    write_outputs(repo_root, index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
