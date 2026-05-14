# Evidence / Validation Pack Index

UTC timestamp: 2026-05-14T04:43:56.459393+00:00

## Purpose
Summarize known local validation and status artifacts without altering source evidence.

## Summary

| total artifacts | present | missing | pass_hint_count | fail_hint_count | unknown_hint_count |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 10 | 0 | 1 |

## Artifact Table

| category | artifact_id | path | exists | status_hint | sha256_prefix |
|---|---|---|---|---|---|
| core_trl | trl_validation | `reports/trl-validation-report.md` | True | PASS | `7f496928d947` |
| stage2_evidence | stage2_inventory_smoke | `reports/stage2-inventory-smoke-report.md` | True | PASS | `7842fbb2c1bd` |
| stage2_evidence | stage2_e2e_smoke | `reports/stage2-e2e-smoke-report.md` | True | PASS | `def7ccfb71bc` |
| stage3_risk_planning | stage3_risk_planning_smoke | `reports/stage3-risk-planning-smoke-report.md` | True | PASS | `c3e0cc0ce847` |
| graph | graph_projection | `reports/graph/latest/graph-projection-report.md` | True | PASS | `6504003d260d` |
| graph | graph_snapshot_loader | `reports/graph/latest/graph-snapshot-loader-report.md` | True | PASS | `62447f3b12b2` |
| graph | graph_api_readonly | `reports/graph/latest/graph-api-readonly-smoke-report.md` | True | PASS | `15a2033947b5` |
| copilot | copilot_offline_smoke | `reports/copilot/offline-smoke-report.md` | True | PASS | `ee7c419987f9` |
| copilot | copilot_safety_contract | `reports/copilot/safety-contract-smoke-report.md` | True | PASS | `b13d9c824840` |
| operator_docs | operator_validation_checklist | `docs/operator-validation-checklist.md` | True | PASS | `e4a6260a45dc` |
| repository_status | repository_checkpoint_status | `docs/repository-checkpoint-current-status.md` | True | UNKNOWN | `663a72e39da2` |

## Boundaries
- This evidence pack index only summarizes existing local artifacts.
- It does not run tests, call services, regenerate reports, or modify source evidence.
- It does not imply production readiness.
