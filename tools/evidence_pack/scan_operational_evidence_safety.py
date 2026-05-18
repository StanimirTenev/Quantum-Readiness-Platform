from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCANNED_ROOTS = [
    "reports/trl7/",
    "reports/trl6/",
    "reports/evidence/",
    "reports/evidence-pack/",
    "reports/external-review/",
]
JSON_REPORT_PATH = "reports/trl7/operational-evidence-safety-scan-report.json"
MD_REPORT_PATH = "reports/trl7/operational-evidence-safety-scan-report.md"

PEM_MARKERS = [
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN OPENSSH PRIVATE KEY",
    "BEGIN EC PRIVATE KEY",
    "BEGIN PGP PRIVATE KEY BLOCK",
]
CREDENTIAL_KEYS = [
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "access_key",
    "refresh_token",
    "client_secret",
    "ntlm",
    "kerberos_ticket",
    "credential_blob",
]
SAFE_BOUNDARY_TERMS = ["no secrets", "no private keys", "do not include secrets", "stop if secrets are collected"]

AWS_KEY_RE = re.compile(r"AKIA[0-9A-Z]{16}")
BEARER_RE = re.compile(r"\bbearer\s+([A-Za-z0-9_\-\.=+/]{20,})", re.IGNORECASE)
PEM_LINE_RE = re.compile(r"-----BEGIN [A-Z0-9 ]+-----")
KEY_WITH_VALUE_RE = re.compile(r"(?P<key>[A-Za-z0-9_\-]+)\s*[:=]\s*(?P<value>.+)$")


def is_self_reporting_scan_context(line: str) -> bool:
    lowered = line.lower()
    if re.search(r"\b(high|medium|low)\s+findings\b", lowered):
        return True
    reporting_terms = [
        "finding summary",
        "scan totals",
        "result:",
        "review_required",
        "credential indicators",
        "private-key findings",
        "blocking credential/private-key findings",
        "were not detected",
        "require reviewer awareness",
        '"indicator":',
        '"redacted_excerpt":',
    ]
    return any(term in lowered for term in reporting_terms)


def is_policy_or_boundary_context(line: str) -> bool:
    lowered = line.lower()
    if any(term in lowered for term in SAFE_BOUNDARY_TERMS):
        return True
    policy_terms = [
        "policy",
        "boundary",
        "do not",
        "must not",
        "should not",
        "scanner",
        "scan",
        "report",
        "review",
        "triage",
        "indicators",
        "blocking",
        "escalate",
        "external sharing",
        "rationale",
        "allowed wording",
    ]
    return any(term in lowered for term in policy_terms)


def is_placeholder_or_redacted_value(value: str) -> bool:
    normalized = value.strip().strip("`\"'").lower()
    placeholder_tokens = {"", "none", "null", "n/a", "redacted", "[redacted]", "<redacted>", "masked", "(redacted)"}
    if normalized in placeholder_tokens:
        return True
    return bool(re.fullmatch(r"[*x•-]{3,}", normalized))


def classify_credential_like_line(line: str) -> dict[str, str] | None:
    m = KEY_WITH_VALUE_RE.search(line)
    if not m:
        return None
    key = m.group("key").strip().lower()
    value = m.group("value").strip()
    if key not in CREDENTIAL_KEYS:
        return None
    if is_placeholder_or_redacted_value(value):
        return None
    return {"severity": "MEDIUM", "indicator": key, "reason": "Credential-like key with non-empty value."}


def redact_excerpt(line: str) -> str:
    line = AWS_KEY_RE.sub("AKIA[REDACTED]", line)
    line = BEARER_RE.sub("Bearer [REDACTED]", line)
    line = re.sub(r"([A-Za-z0-9_\-]{6,})", lambda m: m.group(1) if len(m.group(1)) <= 10 else m.group(1)[:4] + "…", line)
    return line[:220]


def classify_line(line: str) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    lowered = line.lower()

    if is_policy_or_boundary_context(line) or is_self_reporting_scan_context(line):
        # Preserve strict HIGH/MEDIUM detectors even in policy/reporting context.
        pass

    for marker in PEM_MARKERS:
        if marker.lower() in lowered:
            findings.append({"severity": "HIGH", "indicator": marker, "reason": "PEM/private-key marker detected."})

    if PEM_LINE_RE.search(line):
        findings.append({"severity": "HIGH", "indicator": "PEM block line", "reason": "PEM block boundary line detected."})

    if AWS_KEY_RE.search(line):
        findings.append({"severity": "HIGH", "indicator": "AWS access key pattern", "reason": "AWS access-key-like value detected."})

    if BEARER_RE.search(line):
        findings.append({"severity": "HIGH", "indicator": "Bearer token-like value", "reason": "Bearer token-like value detected."})

    credential_finding = classify_credential_like_line(line)
    if credential_finding:
        findings.append(credential_finding)

    if findings:
        return findings

    if is_policy_or_boundary_context(line) or is_self_reporting_scan_context(line):
        return findings

    for key in CREDENTIAL_KEYS:
        if re.search(rf"\b{re.escape(key)}\b", lowered):
            findings.append({"severity": "LOW", "indicator": key, "reason": "Credential-like term appears outside policy/reporting context."})
            break

    return findings


def scan_file(path: Path, repo_root: Path) -> tuple[list[dict[str, Any]], bool]:
    try:
        raw = path.read_bytes()
    except OSError:
        return [], True
    if b"\x00" in raw:
        return [], True
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return [], True

    file_findings: list[dict[str, Any]] = []
    rel_path = str(path.relative_to(repo_root))
    for i, line in enumerate(text.splitlines(), start=1):
        for finding in classify_line(line):
            file_findings.append({
                "path": rel_path,
                "line_number": i,
                "severity": finding["severity"],
                "indicator": finding["indicator"],
                "redacted_excerpt": redact_excerpt(line),
                "reason": finding["reason"],
            })
    return file_findings, False


def run_scan(repo_root: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    files_scanned = 0
    files_skipped = 0
    existing_roots: list[str] = []

    for root in SCANNED_ROOTS:
        root_path = repo_root / root
        if not root_path.exists():
            continue
        existing_roots.append(root)
        for path in sorted(p for p in root_path.rglob("*") if p.is_file()):
            file_findings, skipped = scan_file(path, repo_root)
            if skipped:
                files_skipped += 1
                continue
            files_scanned += 1
            findings.extend(file_findings)

    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for f in findings:
        counts[f["severity"]] += 1

    if counts["HIGH"] > 0 or counts["MEDIUM"] > 0:
        result = "FAIL"
    elif counts["LOW"] > 0:
        result = "REVIEW_REQUIRED"
    else:
        result = "PASS"

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scanned_roots": existing_roots,
        "files_scanned": files_scanned,
        "files_skipped": files_skipped,
        "finding_counts": counts,
        "result": result,
        "findings": findings,
    }


def build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Operational Evidence Safety Scan Report",
        "",
        f"UTC timestamp: {report['generated_at_utc']}",
        "",
        "## Purpose",
        "Deterministic local scan for obvious secret/private-key/credential indicators in generated evidence/report artifacts before sharing or pilot review.",
        "",
        "## Scanned Roots",
    ]
    lines.extend([f"- `{root}`" for root in report["scanned_roots"]] or ["- (none found)"])
    lines.extend([
        "",
        "## Scan Totals",
        f"- files scanned: {report['files_scanned']}",
        f"- files skipped: {report['files_skipped']}",
        f"- result: **{report['result']}**",
        "",
        "## Finding Summary",
        f"- HIGH: {report['finding_counts']['HIGH']}",
        f"- MEDIUM: {report['finding_counts']['MEDIUM']}",
        f"- LOW: {report['finding_counts']['LOW']}",
        "",
        "## Findings",
        "",
        "| path | line | severity | indicator | redacted_excerpt | reason |",
        "|---|---:|---|---|---|---|",
    ])
    if report["findings"]:
        for f in report["findings"]:
            lines.append(f"| `{f['path']}` | {f['line_number']} | {f['severity']} | {f['indicator']} | `{f['redacted_excerpt'].replace('`', '\\`')}` | {f['reason']} |")
    else:
        lines.append("| (none) | - | - | - | - | - |")

    lines.extend([
        "",
        "## Boundary Statements",
        "- This scan checks local evidence/report artifacts only.",
        "- This scan does not modify evidence.",
        "- TRL 7 achieved is not claimed by this scan.",
        "- Production readiness is not claimed by this scan.",
        "",
    ])
    return "\n".join(lines)


def write_outputs(repo_root: Path, report: dict[str, Any]) -> None:
    json_path = repo_root / JSON_REPORT_PATH
    md_path = repo_root / MD_REPORT_PATH
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown(report), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan local operational evidence/report artifacts for obvious secret/private-key indicators.")
    parser.add_argument("--repo-root", default=".", help="Repository root path.")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    report = run_scan(repo_root)
    write_outputs(repo_root, report)
    return 1 if report["result"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
