# Operational Evidence Safety Scan Report

UTC timestamp: 2026-07-07T17:47:57.776608+00:00

## Purpose
Deterministic local scan for obvious secret/private-key/credential indicators in generated evidence/report artifacts before sharing or pilot review.

## Scanned Roots
- `reports/trl7/`
- `reports/trl6/`
- `reports/evidence/`
- `reports/evidence-pack/`
- `reports/external-review/`

## Scan Totals
- files scanned: 49
- files skipped: 0
- result: **REVIEW_REQUIRED**

## Finding Summary
- HIGH: 0
- MEDIUM: 0
- LOW: 4

## Findings

| path | line | severity | indicator | redacted_excerpt | reason |
|---|---:|---|---|---|---|
| `reports/trl7/operational-evidence-safety-low-findings-triage.md` | 48 | LOW | token | `- token value` | Credential-like term appears outside policy/reporting context. |
| `reports/trl7/operational-evidence-safety-low-findings-triage.md` | 50 | LOW | password | `- password/secret material` | Credential-like term appears outside policy/reporting context. |
| `reports/trl7/operational-evidence-safety-scan-review.md` | 44 | LOW | token | `- token value` | Credential-like term appears outside policy/reporting context. |
| `reports/trl7/operational-evidence-safety-scan-review.md` | 46 | LOW | secret | `- secr… production file` | Credential-like term appears outside policy/reporting context. |

## Boundary Statements
- This scan checks local evidence/report artifacts only.
- This scan does not modify evidence.
- TRL 7 achieved is not claimed by this scan.
- Production readiness is not claimed by this scan.
