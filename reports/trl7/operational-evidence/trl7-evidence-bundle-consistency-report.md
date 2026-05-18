# TRL7 Evidence Bundle Consistency Report

UTC timestamp: 2026-05-18T06:31:25.176286+00:00

## Purpose
Deterministic local consistency validation for TRL7 operational evidence-bundle artifacts.

## Result
FAIL

## Summary
| failed_checks | warnings | artifacts_checked | required_missing | hash_mismatches |
|---:|---:|---:|---:|---:|
| 1 | 0 | 8 | 0 | 4 |

## Checks
| check_id | description | status | detail |
|---|---|---|---|
| A | Bundle index files exist | PASS | Both index JSON/Markdown files were found. |
| B | JSON index has required root keys | PASS | All required root keys are present. |
| C | Summary contains required fields | PASS | All required summary fields are present. |
| D | required_missing equals zero | PASS | required_missing=0 |
| E | Present artifacts exist with matching metadata/hash | FAIL | Size mismatch for docs/repository-checkpoint-current-status.md: expected 17097, actual 18239; SHA256 mismatch for docs/repository-checkpoint-current-status.md; Size mismatch for reports/trl7/operational-evidence-safety-scan-report.md: expected 2026, actual 1546; SHA256 mismatch for reports/trl7/operational-evidence-safety-scan-report.md; Size mismatch for reports/trl7/operational-evidence-safety-scan-report.json: expected 2087, actual 1583; SHA256 mismatch for reports/trl7/operational-evidence-safety-scan-report.json; Size mismatch for docs/trl7-operational-evidence-bundle-design.md: expected 5427, actual 5485; SHA256 mismatch for docs/trl7-operational-evidence-bundle-design.md |
| F | Required-for-review artifacts are marked present | PASS | All required artifacts are marked present. |
| G | Safety scan artifacts are indexed | PASS | Safety scan artifacts are indexed. |
| H | Smoke report exists and contains PASS | PASS | Smoke report contains PASS. |
| I | Boundary statements appear in bundle Markdown | PASS | Required boundary statements present. |
| J | Forbidden claim wording is not used as a claim | PASS | No forbidden claim wording used as a claim was detected. |

## Missing Required Artifacts
None.

## Hash Mismatch Section
hash_mismatches: 4

## Safety Scan Inclusion Section
See check G for indexed safety scan artifact paths.

## Boundary Statement Section
See checks I and J for boundary and claim-wording validation.

This consistency check validates local TRL7 evidence-bundle integrity only.
This check does not claim TRL 7 achieved.
Production readiness is not claimed by this check.
