# Evidence / Validation Pack Index

UTC timestamp: 2026-05-16T04:00:31.844293+00:00

## Purpose
Summarize known local validation and status artifacts without altering source evidence.

## Summary

| total artifacts | present | missing | pass_hint_count | fail_hint_count | unknown_hint_count |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 10 | 0 | 1 |

## Artifact Table

| category | artifact_id | path | exists | status_hint | sha256_prefix |
|---|---|---|---|---|---|
| core_trl | trl_validation | `reports/trl-validation-report.md` | True | PASS | `d9f16a3607f4` |
| stage2_evidence | stage2_inventory_smoke | `reports/stage2-inventory-smoke-report.md` | True | PASS | `5337f5cf86ac` |
| stage2_evidence | stage2_e2e_smoke | `reports/stage2-e2e-smoke-report.md` | True | PASS | `3233d0d4108e` |
| stage3_risk_planning | stage3_risk_planning_smoke | `reports/stage3-risk-planning-smoke-report.md` | True | PASS | `c5cf5b4ccb68` |
| graph | graph_projection | `reports/graph/latest/graph-projection-report.md` | True | PASS | `fa4c227d59e0` |
| graph | graph_snapshot_loader | `reports/graph/latest/graph-snapshot-loader-report.md` | True | PASS | `dd16509937e0` |
| graph | graph_api_readonly | `reports/graph/latest/graph-api-readonly-smoke-report.md` | True | PASS | `062893f38882` |
| copilot | copilot_offline_smoke | `reports/copilot/offline-smoke-report.md` | True | PASS | `ca92ba29da9e` |
| copilot | copilot_safety_contract | `reports/copilot/safety-contract-smoke-report.md` | True | PASS | `776e97b6d56b` |
| operator_docs | operator_validation_checklist | `docs/operator-validation-checklist.md` | True | PASS | `e4a6260a45dc` |
| repository_status | repository_checkpoint_status | `docs/repository-checkpoint-current-status.md` | True | UNKNOWN | `427d67c17a1c` |

## Boundaries
- This evidence pack index only summarizes existing local artifacts.
- It does not run tests, call services, regenerate reports, or modify source evidence.
- It does not imply production readiness.
