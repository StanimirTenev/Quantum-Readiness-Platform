# TRL6 Demo Evidence Bundle Index

UTC timestamp: 2026-05-17T06:52:01.746425+00:00

## Purpose
Deterministic TRL6 demo evidence bundle for operator review/export without regenerating source evidence.

## Bundle Summary

| total artifacts | present | missing | required_present | required_missing | pass_hint_count | fail_hint_count | unknown_hint_count |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 16 | 0 | 9 | 0 | 5 | 0 | 11 |

## Artifact Table

| category | artifact_id | path | required | exists | status_hint | sha256 short prefix |
|---|---|---|---|---|---|---|
| trl6_readiness | trl6_readiness_report | `reports/trl6/trl6-readiness-report.md` | True | True | UNKNOWN | `3ed0996a53dd` |
| operator_review | trl6_operator_summary | `reports/trl6/operator-review-summary.md` | True | True | UNKNOWN | `89b6189ba9f9` |
| operator_review | trl6_operator_checklist | `reports/trl6/operator-demo-checklist.md` | True | True | UNKNOWN | `e8d2ed741966` |
| limitations | trl6_known_limitations | `reports/trl6/known-limitations.md` | True | True | UNKNOWN | `0792cb83e53c` |
| trl6_readiness | trl6_readiness_plan | `docs/trl6-readiness-plan.md` | False | True | UNKNOWN | `654518b87555` |
| operator_review | trl6_review_boundary | `docs/trl6-operator-review-boundary.md` | True | True | UNKNOWN | `2917037effef` |
| evidence_index | evidence_pack_index_md | `reports/evidence-pack/evidence-pack-index.md` | True | True | PASS | `b374110f0497` |
| evidence_index | evidence_pack_index_json | `reports/evidence-pack/evidence-pack-index.json` | True | True | UNKNOWN | `22cbffc83610` |
| graph_validation | graph_api_readonly_smoke | `reports/graph/latest/graph-api-readonly-smoke-report.md` | False | True | PASS | `b5a48b18bafe` |
| graph_validation | graph_snapshot_loader_smoke | `reports/graph/latest/graph-snapshot-loader-report.md` | False | True | PASS | `cc403a9d3bf2` |
| copilot_validation | copilot_safety_contract_smoke | `reports/copilot/safety-contract-smoke-report.md` | False | True | UNKNOWN | `f6d9ba11fd4c` |
| stage_validation | stage2_inventory_smoke | `reports/stage2-inventory-smoke-report.md` | False | True | UNKNOWN | `4820eb192693` |
| stage_validation | stage2_e2e_smoke | `reports/stage2-e2e-smoke-report.md` | False | True | UNKNOWN | `7bded2195a2b` |
| stage_validation | stage3_risk_planning_smoke | `reports/stage3-risk-planning-smoke-report.md` | False | True | UNKNOWN | `a00bf1af7f8f` |
| trl6_readiness | trl_validation_report | `reports/trl-validation-report.md` | True | True | PASS | `757367b87642` |
| repository_status | repository_checkpoint_status | `docs/repository-checkpoint-current-status.md` | True | True | PASS | `b9d2d1b0b7ee` |

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
