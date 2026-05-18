from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

INDEX_JSON_PATH = Path("reports/trl7/operational-evidence/trl7-operational-evidence-bundle-index.json")
INDEX_MD_PATH = Path("reports/trl7/operational-evidence/trl7-operational-evidence-bundle-index.md")
SMOKE_MD_PATH = Path("reports/trl7/operational-evidence/trl7-operational-evidence-bundle-smoke-report.md")
OUT_JSON_PATH = Path("reports/trl7/operational-evidence/trl7-evidence-bundle-consistency-report.json")
OUT_MD_PATH = Path("reports/trl7/operational-evidence/trl7-evidence-bundle-consistency-report.md")

REQUIRED_ROOT_KEYS = {"generated_at_utc", "artifacts", "summary"}
REQUIRED_SUMMARY_FIELDS = {
    "total_artifacts", "present", "missing", "required_present", "required_missing",
    "pass_hint_count", "fail_hint_count", "unknown_hint_count", "review_required_count",
}
REQUIRED_BOUNDARY_LINES = [
    "TRL 7 achieved is not claimed by this bundle.",
    "Production readiness is not claimed by this bundle.",
]
SAFETY_SCAN_PATHS = {
    "reports/trl7/operational-evidence-safety-scan-report.json",
    "reports/trl7/operational-evidence-safety-scan-report.md",
}
FORBIDDEN_TERMS = [
    "TRL 7 achieved",
    "production-ready",
    "enterprise-ready",
    "production readiness achieved",
    "certified TRL 7",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_non_claim_context(line: str) -> bool:
    lowered = line.lower()
    return any(token in lowered for token in ["not claimed", "does not claim", "non-claim", "forbidden", "boundary"])


def _has_forbidden_claim(text: str) -> tuple[bool, str]:
    for line in text.splitlines():
        for term in FORBIDDEN_TERMS:
            if term.lower() in line.lower() and not _is_non_claim_context(line):
                return True, f"Potential claim wording found: '{term}' in line: {line.strip()}"
    return False, "No forbidden claim wording used as a claim was detected."


def validate(repo_root: Path) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    artifacts_checked = 0
    hash_mismatches = 0
    missing_required_artifacts: list[str] = []

    index_json_path = repo_root / INDEX_JSON_PATH
    index_md_path = repo_root / INDEX_MD_PATH
    smoke_md_path = repo_root / SMOKE_MD_PATH

    if index_json_path.exists() and index_md_path.exists():
        checks.append({"check_id": "A", "description": "Bundle index files exist", "status": "PASS", "detail": "Both index JSON/Markdown files were found."})
    else:
        checks.append({"check_id": "A", "description": "Bundle index files exist", "status": "FAIL", "detail": "Missing one or both bundle index files."})

    index_data: dict[str, Any] = {}
    if index_json_path.exists():
        try:
            index_data = json.loads(index_json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            checks.append({"check_id": "B", "description": "JSON index has required root keys", "status": "FAIL", "detail": f"Invalid JSON: {exc}"})

    if index_data:
        missing_root = sorted(REQUIRED_ROOT_KEYS - set(index_data.keys()))
        checks.append({"check_id": "B", "description": "JSON index has required root keys", "status": "PASS" if not missing_root else "FAIL", "detail": "All required root keys are present." if not missing_root else f"Missing root keys: {missing_root}"})

        summary = index_data.get("summary", {}) if isinstance(index_data.get("summary"), dict) else {}
        missing_summary = sorted(REQUIRED_SUMMARY_FIELDS - set(summary.keys()))
        checks.append({"check_id": "C", "description": "Summary contains required fields", "status": "PASS" if not missing_summary else "FAIL", "detail": "All required summary fields are present." if not missing_summary else f"Missing summary fields: {missing_summary}"})

        required_missing = summary.get("required_missing")
        checks.append({"check_id": "D", "description": "required_missing equals zero", "status": "PASS" if required_missing == 0 else "FAIL", "detail": f"required_missing={required_missing}"})

        artifacts = index_data.get("artifacts", []) if isinstance(index_data.get("artifacts"), list) else []
        artifact_failures: list[str] = []
        for artifact in artifacts:
            path = artifact.get("path")
            if not path:
                continue
            present = bool(artifact.get("exists") or artifact.get("present"))
            required_for_review = bool(artifact.get("required_for_trl7_review"))
            artifact_path = repo_root / path

            if required_for_review and not present:
                missing_required_artifacts.append(path)

            if present:
                artifacts_checked += 1
                if not artifact_path.exists():
                    artifact_failures.append(f"Marked present but missing on disk: {path}")
                    continue
                expected_size = artifact.get("size_bytes")
                actual_size = artifact_path.stat().st_size
                if expected_size is not None and expected_size != actual_size:
                    artifact_failures.append(f"Size mismatch for {path}: expected {expected_size}, actual {actual_size}")
                expected_hash = artifact.get("sha256")
                if expected_hash:
                    actual_hash = compute_sha256(artifact_path)
                    if expected_hash != actual_hash:
                        hash_mismatches += 1
                        artifact_failures.append(f"SHA256 mismatch for {path}")

        checks.append({"check_id": "E", "description": "Present artifacts exist with matching metadata/hash", "status": "PASS" if not artifact_failures else "FAIL", "detail": "All present artifacts verified." if not artifact_failures else "; ".join(artifact_failures)})
        checks.append({"check_id": "F", "description": "Required-for-review artifacts are marked present", "status": "PASS" if not missing_required_artifacts else "FAIL", "detail": "All required artifacts are marked present." if not missing_required_artifacts else f"Missing required artifacts: {missing_required_artifacts}"})

        indexed_paths = {a.get("path") for a in artifacts if isinstance(a, dict)}
        missing_scan = sorted(p for p in SAFETY_SCAN_PATHS if p not in indexed_paths)
        checks.append({"check_id": "G", "description": "Safety scan artifacts are indexed", "status": "PASS" if not missing_scan else "FAIL", "detail": "Safety scan artifacts are indexed." if not missing_scan else f"Missing indexed safety scan paths: {missing_scan}"})
    else:
        checks.extend([
            {"check_id": "C", "description": "Summary contains required fields", "status": "FAIL", "detail": "Cannot validate without valid index JSON."},
            {"check_id": "D", "description": "required_missing equals zero", "status": "FAIL", "detail": "Cannot validate without valid index JSON."},
            {"check_id": "E", "description": "Present artifacts exist with matching metadata/hash", "status": "FAIL", "detail": "Cannot validate without valid index JSON."},
            {"check_id": "F", "description": "Required-for-review artifacts are marked present", "status": "FAIL", "detail": "Cannot validate without valid index JSON."},
            {"check_id": "G", "description": "Safety scan artifacts are indexed", "status": "FAIL", "detail": "Cannot validate without valid index JSON."},
        ])

    smoke_ok = smoke_md_path.exists() and ("PASS" in smoke_md_path.read_text(encoding="utf-8", errors="replace"))
    checks.append({"check_id": "H", "description": "Smoke report exists and contains PASS", "status": "PASS" if smoke_ok else "FAIL", "detail": "Smoke report contains PASS." if smoke_ok else "Smoke report missing or does not contain PASS."})

    boundary_ok = False
    if index_md_path.exists():
        index_md_text = index_md_path.read_text(encoding="utf-8", errors="replace")
        missing_lines = [line for line in REQUIRED_BOUNDARY_LINES if line not in index_md_text]
        boundary_ok = not missing_lines
        checks.append({"check_id": "I", "description": "Boundary statements appear in bundle Markdown", "status": "PASS" if boundary_ok else "FAIL", "detail": "Required boundary statements present." if boundary_ok else f"Missing boundary lines: {missing_lines}"})
    else:
        checks.append({"check_id": "I", "description": "Boundary statements appear in bundle Markdown", "status": "FAIL", "detail": "Bundle Markdown index is missing."})
        index_md_text = ""

    index_json_text = index_json_path.read_text(encoding="utf-8", errors="replace") if index_json_path.exists() else ""
    forbidden_found, forbidden_detail = _has_forbidden_claim(index_md_text + "\n" + index_json_text)
    checks.append({"check_id": "J", "description": "Forbidden claim wording is not used as a claim", "status": "FAIL" if forbidden_found else "PASS", "detail": forbidden_detail})

    failed_checks = sum(1 for c in checks if c["status"] == "FAIL")
    warnings = sum(1 for c in checks if c["status"] == "WARN")
    result = "FAIL" if failed_checks else ("REVIEW_REQUIRED" if warnings else "PASS")

    return {
        "generated_at_utc": _utc_now(),
        "result": result,
        "checks": checks,
        "summary": {
            "failed_checks": failed_checks,
            "warnings": warnings,
            "artifacts_checked": artifacts_checked,
            "required_missing": (index_data.get("summary", {}) if index_data else {}).get("required_missing"),
            "hash_mismatches": hash_mismatches,
            "missing_required_artifacts": missing_required_artifacts,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# TRL7 Evidence Bundle Consistency Report",
        "",
        f"UTC timestamp: {report['generated_at_utc']}",
        "",
        "## Purpose",
        "Deterministic local consistency validation for TRL7 operational evidence-bundle artifacts.",
        "",
        f"## Result\n{report['result']}",
        "",
        "## Summary",
        "| failed_checks | warnings | artifacts_checked | required_missing | hash_mismatches |",
        "|---:|---:|---:|---:|---:|",
        f"| {s['failed_checks']} | {s['warnings']} | {s['artifacts_checked']} | {s['required_missing']} | {s['hash_mismatches']} |",
        "",
        "## Checks",
        "| check_id | description | status | detail |",
        "|---|---|---|---|",
    ]
    for check in report["checks"]:
        lines.append(f"| {check['check_id']} | {check['description']} | {check['status']} | {check['detail']} |")
    lines.extend([
        "",
        "## Missing Required Artifacts",
        ", ".join(s["missing_required_artifacts"]) if s["missing_required_artifacts"] else "None.",
        "",
        "## Hash Mismatch Section",
        f"hash_mismatches: {s['hash_mismatches']}",
        "",
        "## Safety Scan Inclusion Section",
        "See check G for indexed safety scan artifact paths.",
        "",
        "## Boundary Statement Section",
        "See checks I and J for boundary and claim-wording validation.",
        "",
        "This consistency check validates local TRL7 evidence-bundle integrity only.",
        "This check does not claim TRL 7 achieved.",
        "Production readiness is not claimed by this check.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TRL7 evidence bundle consistency from local artifacts.")
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    report = validate(repo_root)
    out_dir = (repo_root / OUT_JSON_PATH).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    (repo_root / OUT_JSON_PATH).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (repo_root / OUT_MD_PATH).write_text(render_markdown(report), encoding="utf-8")

    return 0 if report["result"] in {"PASS", "REVIEW_REQUIRED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
