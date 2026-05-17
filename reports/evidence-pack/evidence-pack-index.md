# Evidence / Validation Pack Index

UTC timestamp: 2026-05-17T06:52:00.893631+00:00

## Purpose
Summarize known local validation and status artifacts without altering source evidence.

## Summary

| total artifacts | present | missing | pass_hint_count | fail_hint_count | unknown_hint_count |
|---:|---:|---:|---:|---:|---:|
| 11 | 11 | 0 | 11 | 0 | 0 |

## Artifact Table

| category | artifact_id | path | exists | status_hint | sha256_prefix |
|---|---|---|---|---|---|
| core_trl | trl_validation | `reports/trl-validation-report.md` | True | PASS | `757367b87642` |
| stage2_evidence | stage2_inventory_smoke | `reports/stage2-inventory-smoke-report.md` | True | PASS | `4820eb192693` |
| stage2_evidence | stage2_e2e_smoke | `reports/stage2-e2e-smoke-report.md` | True | PASS | `7bded2195a2b` |
| stage3_risk_planning | stage3_risk_planning_smoke | `reports/stage3-risk-planning-smoke-report.md` | True | PASS | `a00bf1af7f8f` |
| graph | graph_projection | `reports/graph/latest/graph-projection-report.md` | True | PASS | `761d2d4538eb` |
| graph | graph_snapshot_loader | `reports/graph/latest/graph-snapshot-loader-report.md` | True | PASS | `cc403a9d3bf2` |
| graph | graph_api_readonly | `reports/graph/latest/graph-api-readonly-smoke-report.md` | True | PASS | `b5a48b18bafe` |
| copilot | copilot_offline_smoke | `reports/copilot/offline-smoke-report.md` | True | PASS | `e3467a3ff57c` |
| copilot | copilot_safety_contract | `reports/copilot/safety-contract-smoke-report.md` | True | PASS | `f6d9ba11fd4c` |
| operator_docs | operator_validation_checklist | `docs/operator-validation-checklist.md` | True | PASS | `6d730bcd9b92` |
| repository_status | repository_checkpoint_status | `docs/repository-checkpoint-current-status.md` | True | PASS | `b9d2d1b0b7ee` |

## Boundaries
- This evidence pack index only summarizes existing local artifacts.
- It does not run tests, call services, regenerate reports, or modify source evidence.
- It does not imply production readiness.
