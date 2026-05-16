# TRL6 Demo Evidence Bundle Index

UTC timestamp: 2026-05-16T04:27:28.567462+00:00

## Purpose
Deterministic TRL6 demo evidence bundle for operator review/export without regenerating source evidence.

## Bundle Summary

| total artifacts | present | missing | required_present | required_missing | pass_hint_count | fail_hint_count | unknown_hint_count |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 16 | 0 | 9 | 0 | 13 | 1 | 2 |

## Artifact Table

| category | artifact_id | path | required | exists | status_hint | sha256 short prefix |
|---|---|---|---|---|---|---|
| trl6_readiness | trl6_readiness_report | `reports/trl6/trl6-readiness-report.md` | True | True | PASS | `fc9b33bedab9` |
| operator_review | trl6_operator_summary | `reports/trl6/operator-review-summary.md` | True | True | PASS | `77c20c279f06` |
| operator_review | trl6_operator_checklist | `reports/trl6/operator-demo-checklist.md` | True | True | UNKNOWN | `138e52a6519e` |
| limitations | trl6_known_limitations | `reports/trl6/known-limitations.md` | True | True | FAIL | `0792cb83e53c` |
| trl6_readiness | trl6_readiness_plan | `docs/trl6-readiness-plan.md` | False | True | PASS | `654518b87555` |
| operator_review | trl6_review_boundary | `docs/trl6-operator-review-boundary.md` | True | True | PASS | `2917037effef` |
| evidence_index | evidence_pack_index_md | `reports/evidence-pack/evidence-pack-index.md` | True | True | PASS | `ab12ab9baafd` |
| evidence_index | evidence_pack_index_json | `reports/evidence-pack/evidence-pack-index.json` | True | True | PASS | `50630b402d6a` |
| graph_validation | graph_api_readonly_smoke | `reports/graph/latest/graph-api-readonly-smoke-report.md` | False | True | PASS | `062893f38882` |
| graph_validation | graph_snapshot_loader_smoke | `reports/graph/latest/graph-snapshot-loader-report.md` | False | True | PASS | `dd16509937e0` |
| copilot_validation | copilot_safety_contract_smoke | `reports/copilot/safety-contract-smoke-report.md` | False | True | PASS | `776e97b6d56b` |
| stage_validation | stage2_inventory_smoke | `reports/stage2-inventory-smoke-report.md` | False | True | PASS | `5337f5cf86ac` |
| stage_validation | stage2_e2e_smoke | `reports/stage2-e2e-smoke-report.md` | False | True | PASS | `3233d0d4108e` |
| stage_validation | stage3_risk_planning_smoke | `reports/stage3-risk-planning-smoke-report.md` | False | True | PASS | `c5cf5b4ccb68` |
| trl6_readiness | trl_validation_report | `reports/trl-validation-report.md` | True | True | PASS | `d9f16a3607f4` |
| repository_status | repository_checkpoint_status | `docs/repository-checkpoint-current-status.md` | True | True | UNKNOWN | `ddadd0f57497` |

## Review Boundary Statements
- This bundle supports TRL6 demo/operator review only.
- TRL 6 achieved is not claimed by this bundle.
- Production readiness is not claimed by this bundle.
- This bundle does not run tests, start services, or regenerate evidence.

## Next Review Action
- operator must review readiness report
- operator must review known limitations
- operator must complete checklist/sign-off
- relevant-environment demo evidence must be attached before TRL6 achieved wording is used
