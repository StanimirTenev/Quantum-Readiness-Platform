# TRL6 Demo Bundle Integrity Smoke Report

UTC timestamp: 2026-05-17T05:42:30Z

## Checked Files
- reports/trl6/demo-bundle/trl6-demo-bundle-index.json
- reports/trl6/demo-bundle/trl6-demo-bundle-index.md

## Required Artifact Presence Summary
| artifact | file_exists | json_marked_present |
|---|---|---|
| reports/trl6/trl6-readiness-report.md | true | true |
| reports/trl6/operator-review-summary.md | true | true |
| reports/trl6/operator-demo-checklist.md | true | true |
| reports/trl6/known-limitations.md | true | true |
| docs/trl6-readiness-plan.md | true | true |
| docs/trl6-operator-review-boundary.md | true | true |

## Boundary Statement Checks
- PASS: This bundle supports TRL6 demo/operator review only.
- PASS: TRL 6 achieved is not claimed by this bundle.
- PASS: Production readiness is not claimed by this bundle.
- PASS: This bundle does not run tests, start services, or regenerate evidence.

## JSON Structure Checks
- PASS: key present: generated_at_utc
- PASS: key present: artifacts
- PASS: key present: summary

## Overall Check Log
- PASS: exists reports/trl6/demo-bundle/trl6-demo-bundle-index.json
- PASS: exists reports/trl6/demo-bundle/trl6-demo-bundle-index.md
- PASS: boundary statement present: This bundle supports TRL6 demo/operator review only.
- PASS: boundary statement present: TRL 6 achieved is not claimed by this bundle.
- PASS: boundary statement present: Production readiness is not claimed by this bundle.
- PASS: boundary statement present: This bundle does not run tests, start services, or regenerate evidence.
- PASS: json root key present: generated_at_utc
- PASS: json root key present: artifacts
- PASS: json root key present: summary

## Result
PASS

This smoke validates demo bundle integrity only.

This smoke does not claim TRL 6 achieved or production readiness.
