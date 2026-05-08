# Operator Validation Checklist

## Purpose

This checklist is used to manually verify that the local TRL validation run is repeatable, evidence-backed and suitable for TRL 5 candidate assessment.

## Preconditions

- Required services can be started locally.
- `./scripts/start_all.sh` is available.
- `./scripts/status_all.sh` is available.
- `scripts/run_trl_validation.sh` is available.
- `jq` is recommended but not strictly required.
- No production secrets should be present in sample evidence.

## Required Services

| Service | Port | Health Endpoint | Expected |
|---|---:|---|---|
| inventory-service | 8001 | http://127.0.0.1:8001/health | healthy |
| risk-engine | 8002 | http://127.0.0.1:8002/health | healthy |
| planner-service | 8004 | http://127.0.0.1:8004/health | healthy |
| workflow-service | 8005 | http://127.0.0.1:8005/health | healthy |
| policy-engine | 8007 | http://127.0.0.1:8007/health | healthy |
| api-gateway | 8000 | http://127.0.0.1:8000/health | healthy |

## Step 1 — Clean Start

Run:

```bash
./scripts/stop_all.sh || true
./scripts/start_all.sh
./scripts/status_all.sh
```

Validate:
- All required services are reported as running.
- No service is shown as stopped or unhealthy.

## Step 2 — Execute TRL Validation Harness

Run:

```bash
./scripts/run_trl_validation.sh
```

Validate:
- Command exits with status code `0`.
- No fail-fast abort message is present.

## Step 3 — Confirm Validation Report

Open:
- `reports/trl-validation-report.md`

Validate:
- `Result: PASS` is present.
- Report includes timestamp and endpoint checks.
- Report contains evidence, risk, policy, plan, waves and workflow sections.

## Step 4 — Confirm Evidence Package v1 Artifacts

Inspect:
- `reports/evidence/latest/`

Expected files:
- `host-evidence.json`
- `network-evidence.json`
- `inventory-ingest-response.json`
- `assets.json`
- `risks.json`
- `policy-decision.json`
- `plan.json`
- `waves.json`
- `workflow-export.json`

Validate:
- Each file exists and is non-empty.
- JSON is parseable (`jq . <file>` if available).

## Step 5 — Cross-Artifact Consistency Checks

Validate:
- `inventory-ingest-response.json` contains non-empty `scan_id` and `asset_ids`.
- Asset identifiers in `assets.json` overlap with evidence payload identifiers.
- `risks.json` contains at least one risk entry or an explicit empty set with valid structure.
- `policy-decision.json` contains a decision payload with no runtime error field.
- `plan.json` and `waves.json` reflect the same planning intent (same asset/risk scope where applicable).
- `workflow-export.json` contains exportable tasks structure.

## Step 6 — Repeatability Check

Run the harness again:

```bash
./scripts/run_trl_validation.sh
```

Validate:
- Second run also exits `0`.
- `reports/trl-validation-report.md` still ends with `Result: PASS`.
- Evidence files are regenerated without schema regressions.

## Step 7 — Security and Sanitization Spot Check

Validate:
- Evidence artifacts do not contain production credentials, API keys, tokens, private keys, or secrets.
- Host and network samples remain representative but sanitized.

## Acceptance Criteria

The checklist is considered passed only if all conditions below are true:
- Services are healthy after clean start.
- TRL harness passes on at least two consecutive local runs.
- `reports/trl-validation-report.md` shows `Result: PASS`.
- Evidence Package v1 artifacts exist, are parseable, and internally consistent.
- No sensitive production data is present in saved evidence.

## Failure Handling

If any check fails:
1. Capture failing command output and relevant service logs from `logs/*.log`.
2. Record which checklist step failed and why.
3. Fix the issue and restart from **Step 1 — Clean Start**.
4. Do not claim TRL 5 candidate readiness until all acceptance criteria pass.
