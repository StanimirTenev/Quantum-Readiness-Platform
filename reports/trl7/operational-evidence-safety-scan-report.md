# Operational Evidence Safety Scan Report

UTC timestamp: 2026-05-18T04:44:49.075104+00:00

## Purpose
Deterministic local scan for obvious secret/private-key/credential indicators in generated evidence/report artifacts before sharing or pilot review.

## Scanned Roots
- `reports/trl7/`
- `reports/trl6/`
- `reports/evidence/`
- `reports/evidence-pack/`
- `reports/external-review/`

## Scan Totals
- files scanned: 45
- files skipped: 0
- result: **REVIEW_REQUIRED**

## Finding Summary
- HIGH: 0
- MEDIUM: 0
- LOW: 4

## Findings

| path | line | severity | indicator | redacted_excerpt | reason |
|---|---:|---|---|---|---|
| `reports/trl7/operational-evidence-safety-scan-report.json` | 23 | LOW | secret | `      "indicator": "secret",` | Credential-like term appears in likely policy/reference context. |
| `reports/trl7/operational-evidence-safety-scan-report.json` | 24 | LOW | secret | `      "reda…": "Dete\u2026 local scan for obvious secret/priv\u2026/credential indicators in generated evidence/report artifacts before sharing or pilot review.",` | Credential-like term appears in likely policy/reference context. |
| `reports/trl7/operational-evidence-safety-scan-report.md` | 6 | LOW | secret | `Dete… local scan for obvious secret/priv…/credential indicators in generated evidence/report artifacts before sharing or pilot review.` | Credential-like term appears in likely policy/reference context. |
| `reports/trl7/operational-evidence-safety-scan-report.md` | 29 | LOW | secret | `| \`reports/trl7/oper….md\` | 6 | LOW | secret | \`Dete… local scan for obvious secret/priv…/credential indicators in generated evidence/report artifacts before sharing or pilot review.\` | Cred… term appears in likely polic` | Credential-like term appears in likely policy/reference context. |

## Boundary Statements
- This scan checks local evidence/report artifacts only.
- This scan does not modify evidence.
- TRL 7 achieved is not claimed by this scan.
- Production readiness is not claimed by this scan.
