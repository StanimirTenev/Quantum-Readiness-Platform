from __future__ import annotations

import argparse
import hashlib
import json
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
    notes: str


ARTIFACT_SPECS: list[ArtifactSpec] = [
    ArtifactSpec("trl_validation", "TRL Validation Report", "reports/trl-validation-report.md", "core_trl", "Core TRL validation evidence."),
    ArtifactSpec("stage2_inventory_smoke", "Stage 2 Inventory Smoke Report", "reports/stage2-inventory-smoke-report.md", "stage2_evidence", "Stage 2 inventory validation artifact."),
    ArtifactSpec("stage2_e2e_smoke", "Stage 2 E2E Smoke Report", "reports/stage2-e2e-smoke-report.md", "stage2_evidence", "Stage 2 end-to-end validation artifact."),
    ArtifactSpec("stage3_risk_planning_smoke", "Stage 3 Risk Planning Smoke Report", "reports/stage3-risk-planning-smoke-report.md", "stage3_risk_planning", "Stage 3 risk/planning validation artifact."),
    ArtifactSpec("graph_projection", "Graph Projection Report", "reports/graph/latest/graph-projection-report.md", "graph", "Graph projection validation artifact."),
    ArtifactSpec("graph_snapshot_loader", "Graph Snapshot Loader Report", "reports/graph/latest/graph-snapshot-loader-report.md", "graph", "Graph snapshot loader validation artifact."),
    ArtifactSpec("graph_api_readonly", "Graph API Read-only Smoke Report", "reports/graph/latest/graph-api-readonly-smoke-report.md", "graph", "Minimal read-only graph API validation artifact."),
    ArtifactSpec("copilot_offline_smoke", "Copilot Offline Smoke Report", "reports/copilot/offline-smoke-report.md", "copilot", "Copilot offline deterministic safety validation artifact."),
    ArtifactSpec("copilot_safety_contract", "Copilot Safety Contract Smoke Report", "reports/copilot/safety-contract-smoke-report.md", "copilot", "Copilot safety contract validation artifact."),
    ArtifactSpec("operator_validation_checklist", "Operator Validation Checklist", "docs/operator-validation-checklist.md", "operator_docs", "Operator validation procedure document."),
    ArtifactSpec("repository_checkpoint_status", "Repository Checkpoint Current Status", "docs/repository-checkpoint-current-status.md", "repository_status", "Repository status summary document."),
]


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detect_status_hint(text: str) -> str:
    if "PASS" in text:
        return "PASS"
    if "FAIL" in text:
        return "FAIL"
    return "UNKNOWN"


def scan_artifact(repo_root: Path, spec: ArtifactSpec) -> dict[str, Any]:
    artifact_path = repo_root / spec.path
    record: dict[str, Any] = {
        "artifact_id": spec.artifact_id,
        "title": spec.title,
        "path": spec.path,
        "category": spec.category,
        "exists": artifact_path.exists(),
        "notes": spec.notes,
        "status_hint": "UNKNOWN",
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


def build_markdown(index: dict[str, Any]) -> str:
    s = index["summary"]
    lines = [
        "# Evidence / Validation Pack Index",
        "",
        f"UTC timestamp: {index['generated_at_utc']}",
        "",
        "## Purpose",
        "Summarize known local validation and status artifacts without altering source evidence.",
        "",
        "## Summary",
        "",
        "| total artifacts | present | missing | pass_hint_count | fail_hint_count | unknown_hint_count |",
        "|---:|---:|---:|---:|---:|---:|",
        f"| {s['total_artifacts']} | {s['present']} | {s['missing']} | {s['pass_hint_count']} | {s['fail_hint_count']} | {s['unknown_hint_count']} |",
        "",
        "## Artifact Table",
        "",
        "| category | artifact_id | path | exists | status_hint | sha256_prefix |",
        "|---|---|---|---|---|---|",
    ]
    for artifact in index["artifacts"]:
        sha_prefix = artifact.get("sha256", "")[:12] if artifact.get("exists") else ""
        lines.append(
            f"| {artifact['category']} | {artifact['artifact_id']} | `{artifact['path']}` | {artifact['exists']} | {artifact['status_hint']} | `{sha_prefix}` |"
        )

    lines.extend(
        [
            "",
            "## Boundaries",
            "- This evidence pack index only summarizes existing local artifacts.",
            "- It does not run tests, call services, regenerate reports, or modify source evidence.",
            "- It does not imply production readiness.",
            "",
        ]
    )
    return "\n".join(lines)


def build_index(repo_root: Path) -> dict[str, Any]:
    artifacts = [scan_artifact(repo_root, spec) for spec in ARTIFACT_SPECS]
    pass_count = sum(1 for a in artifacts if a["status_hint"] == "PASS")
    fail_count = sum(1 for a in artifacts if a["status_hint"] == "FAIL")
    unknown_count = sum(1 for a in artifacts if a["status_hint"] == "UNKNOWN")
    present = sum(1 for a in artifacts if a["exists"])

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_artifacts": len(artifacts),
            "present": present,
            "missing": len(artifacts) - present,
            "pass_hint_count": pass_count,
            "fail_hint_count": fail_count,
            "unknown_hint_count": unknown_count,
        },
        "artifacts": artifacts,
    }


def write_outputs(repo_root: Path, index: dict[str, Any]) -> None:
    out_dir = repo_root / "reports/evidence-pack"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evidence-pack-index.json").write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    (out_dir / "evidence-pack-index.md").write_text(build_markdown(index), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build evidence pack index from known local artifacts.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    index = build_index(repo_root)
    write_outputs(repo_root, index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
