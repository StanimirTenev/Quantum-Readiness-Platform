# Quantum Readiness Platform

QRP is designed for internal/customer-controlled deployment with local-first evidence processing, optional local Copilot support, and no mandatory external LLM dependency.

Note: the legacy demo (`docs/demo/qrp_demo_legacy.html`) has external LLM calls disabled to preserve the local-first/privacy boundary.

Quantum Readiness Platform is a cybersecurity software prototype for automated post-quantum cryptography assessment — host and network evidence collection, risk scoring, and migration planning. Current status: QRP has a passing TRL6 readiness validation package in a local relevant-environment simulation. TRL 6 achieved is not claimed until relevant-environment demo execution and operator review/sign-off are completed.

## Modules
- API Gateway
- Inventory Service
- Evidence Normalizer
- Crypto Fingerprint Service
- Risk Engine
- Scenario Engine
- Policy Engine
- Planner Service
- Workflow Service
- Retrieval Service
- Copilot Service
- Integration Service
- Linux Host Agent
- Network Scanner
- Frontend Web UI

## Service maturity overview

| Service | Status | Tests |
| --- | --- | --- |
| linux-host-agent | ✅ Working prototype | ✅ Unit tests |
| network-scanner | ✅ Working prototype | ✅ Unit tests |
| inventory-service | ✅ Working prototype | ✅ Unit + smoke tests |
| risk-engine | ✅ Working prototype | ✅ Unit tests |
| planner-service | ✅ Working prototype | ✅ Unit + API tests |
| workflow-service | ✅ Working prototype | ✅ Unit + API tests |
| api-gateway | 🟨 Partially implemented | ✅ API tests |
| copilot-service | ✅ Working prototype | ✅ Unit/API tests |
| retrieval-service | ✅ Working prototype | ✅ Unit + API tests |
| evidence-normalizer | 🔲 Placeholder | — |
| crypto-fingerprint-service | 🔲 Placeholder | — |
| policy-engine | 🔲 Placeholder | — |
| scenario-engine | 🟨 Partially implemented | — |
| repo-ci-scanner | 🔲 Placeholder | — |
| integration-service | 🔲 Placeholder | — |
| dashboard-ui | ✅ Working prototype | — |
| web-ui | 🔲 Skeleton | — |

## First implementation targets
1. Inventory service
2. Risk engine
3. Linux host agent
4. TLS/SSH scanner

- Stage 2 inventory smoke validation added for official enriched evidence fixtures.
- Stage 2 E2E smoke validation added for inventory → risk → planner flow.
- risk-engine now returns confidence_score and risk_dimensions for Stage 3 analysis.
- planner-service now returns priority_score and clearer wave rationale for Stage 3 planning.
- Stage 3 risk/planning smoke validation added for confidence, dimensions and planner priority_score.
- Graph JSON snapshot smoke projection added: scripts/run_graph_projection_smoke.sh

## Architecture and delivery navigation
- Core architecture: `docs/architecture.md`
- TRL5 execution roadmap: `docs/trl5-working-navigator.md`
- Stage 1 core stabilization execution: `docs/stage1-core-stabilization.md`
- Stage 2 freeze/status document added: `docs/stage2-freeze-status.md`
- Stage 3 freeze/status document added: `docs/stage3-freeze-status.md`
- Stage 3 risk/planning audit added: `docs/stage3-risk-planning-audit.md`
- Dependency graph design document added: `docs/dependency-graph-design.md`
- Dependency graph contract document added: `docs/dependency-graph-contract.md`
- Dependency graph projection plan added: `docs/dependency-graph-projection-plan.md`
- Dependency graph projection validation examples added: `docs/dependency-graph-projection-validation-examples.md`
- Dependency graph freeze/status document added: `docs/dependency-graph-freeze-status.md`
- Graph API Design: `docs/graph-api-design.md`
- Graph Snapshot Loader Design: `docs/graph-snapshot-loader-design.md`
- Graph API Read-only Freeze Status: `docs/graph-api-readonly-freeze-status.md`
- Repository checkpoint added: `docs/repository-checkpoint-current-status.md`
- TRL 6 Readiness Plan: `docs/trl6-readiness-plan.md`
- TRL7 Operational Readiness Plan: `docs/trl7-operational-readiness-plan.md`
- TRL7 Operational Pilot Checklist template: `reports/trl7/trl7-operational-pilot-checklist.md`
- TRL7 Operational Evidence Bundle Design: `docs/trl7-operational-evidence-bundle-design.md`
- TRL7 Operational Readiness Report template: `reports/trl7/trl7-operational-readiness-report.md`
- TRL7 Operational Dry-Run Review Report: `reports/trl7/trl7-operational-dry-run-review-report.md`
- TRL7 External Pilot Package: `reports/trl7/trl7-external-pilot-package.md`
- TRL7 Static External Pilot Export Manifest: `reports/trl7/trl7-static-external-pilot-export-manifest.md`
- Cross-Platform Agent Design: `docs/cross-platform-agent-design.md`
- Windows Evidence Fixture Contract: `docs/windows-evidence-fixture-contract.md`
- Inventory Windows Evidence Acceptance Design: `docs/inventory-windows-evidence-acceptance-design.md`
- Windows Risk/Planning Signal Mapping Design: `docs/windows-risk-planning-signal-mapping-design.md`
- Post-Copilot-freeze repository checkpoint added: docs/repository-checkpoint-post-copilot-freeze.md
- Copilot local-first design documented: `docs/copilot-local-first-design.md`
- Copilot provider test plan documented: `docs/copilot-provider-test-plan.md`
- Copilot context packaging policy documented: `docs/copilot-context-packaging-policy.md`
- Copilot implementation boundary documented: `docs/copilot-implementation-boundary.md`
- Local Copilot provider design documented: `docs/copilot-local-provider-design.md`
- Local Copilot Provider Test Contract documented: `docs/copilot-local-provider-test-contract.md`
- Local Copilot Provider Implementation Plan documented: `docs/copilot-local-provider-implementation-plan.md`
- Copilot disabled-provider stub and offline smoke validation added.
- Copilot safety-contract smoke command: `bash scripts/run_copilot_safety_contract_smoke.sh`
- Copilot remains disabled-safe; local provider is not implemented.
- Copilot freeze/status document added: docs/copilot-freeze-status.md

## Stage 2 smoke validation (short path)
Run:

```bash
./scripts/run_stage2_smoke_validation.sh
```

This smoke path validates:
- host enriched evidence ingest
- network enriched evidence ingest
- scans are stored and retrievable
- risk results are still generated after ingest
- planner service still returns a plan response


## Stage 2 E2E Smoke Validation

Run:

```bash
bash scripts/run_stage2_e2e_smoke.sh
```

Precondition:
inventory-service, risk-engine and planner-service are running locally.

Output:
reports/stage2-e2e-smoke-report.md


## Stage 3 Risk/Planning Smoke Validation

Run:

```bash
bash scripts/run_stage3_risk_planning_smoke.sh
```

Precondition:
inventory-service, risk-engine and planner-service are running locally.

Output:
reports/stage3-risk-planning-smoke-report.md


## Graph Projection Smoke

Run:

```bash
bash scripts/run_graph_projection_smoke.sh
```

Validation commands:

```bash
bash scripts/run_graph_snapshot_loader_smoke.sh
bash scripts/run_graph_api_readonly_smoke.sh
```

Output:

reports/graph/latest/graph-snapshot.json
reports/graph/latest/graph-projection-report.md

## TRL7 Operational Dry-Run (Orchestration/Reporting)

Run:

```bash
bash scripts/run_trl7_operational_dry_run.sh
```

## TRL7 Operational Evidence Bundle Smoke

Run:

```bash
bash scripts/run_trl7_operational_evidence_bundle_smoke.sh
```

## TRL 6 Operator Review / Demo Sign-off Package

Validation/status artifacts:
- `reports/trl6/operator-review-summary.md`
- `reports/trl6/operator-demo-checklist.md`
- `docs/trl6-readiness-plan.md`
- `docs/trl6-operator-review-boundary.md`
- `reports/trl6/demo-bundle/trl6-demo-bundle-index.md`
- `reports/trl6/demo-bundle/trl6-demo-bundle-smoke-report.md`
- `reports/trl6/operator-review-execution-record.md`
- `reports/trl6/relevant-environment-demo-evidence.md`
- `reports/trl6/relevant-environment-demo-execution-summary.md`
- `reports/trl6/relevant-environment-demo-run-instructions.md`
- `reports/trl6/trl6-claim-review-readiness-checklist.md`
- `reports/trl6/final-trl6-claim-review-decision.md`
- `reports/trl6/conservative-trl6-claim-approval-record.md`
- `reports/trl6/limited-trl6-demonstrated-approval-record.md`
- `reports/external-review/partner-handoff-pack.md`
- `reports/external-review/stravixlab-review-result.md`
- `reports/external-review/stravixlab-follow-up-action-plan.md`
- `reports/external-review/stravixlab-trl7-review-result.md`
- `reports/external-review/stravixlab-trl7-follow-up-action-plan.md`

## Stage 2 documentation update (current code + fixtures)

### 1) New evidence collected by `linux-host-agent`
- `crypto_evidence.config_indicators`:
  - `ssh_config_indicators` (path + presence)
  - `tls_config_indicators` (path + presence)
  - `service_config_hints` (detected service + likely config paths)
- `crypto_evidence.cert_indicators`:
  - `trust_store_indicators` (path + presence)
  - `key_store_indicators` (path + presence)
  - `certificate_file_indicators` (flat, non-recursive discovery of cert/key-like files)
- `crypto_evidence.package_metadata`:
  - `package_manager_type` (`dpkg`/`rpm`/`pacman`/`apk`/`unknown`)
  - `crypto_packages` filtered by crypto-relevant names (e.g. openssl/libssl/openssh/gnutls/...)

### 2) New evidence collected by `network-scanner`
- `tls_evidence.certificate` is Stage 2 structured:
  - `subject.display_dn`, `subject.fingerprint`
  - `issuer.display_dn`, `issuer.fingerprint`
  - `validity.not_before`, `validity.not_after`
  - `algorithms.signature`, `algorithms.public_key`
  - `key.type`, `key.size_bits`
  - `san.dns_names`
- `tls_evidence.certificate_chain` includes chain presence/length/summary and verification metadata.

### 3) Current Stage 2 payload patterns
- `source=host` minimal: `assets` + `host_inventory`.
- `source=host` enriched: adds `crypto_evidence` + optional `tls_evidence` with structured certificate object.
- `source=network` minimal: `assets` + `tls_evidence` with flattened certificate fields.
- `source=network` enriched: `tls_evidence` with structured certificate object + `certificate_chain`; may include `crypto_evidence`.

Reference fixtures:
- `services/inventory-service/tests/fixtures/stage2_evidence/host_minimal_ingest.json`
- `services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json`
- `services/inventory-service/tests/fixtures/stage2_evidence/network_minimal_ingest.json`
- `services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json`

### 4) Reliable vs best-effort
- Reliable (contract-level):
  - `/scans/ingest` requires `source` + `assets`; accepted `source` values are `host|network|repo|manual`.
  - Stage 2 structured certificate payload is accepted and normalized for storage.
  - Smoke path verifies ingest + retrieval + risk generation + planner API response.
- Best-effort:
  - Host command-based collection (`openssl`, package manager queries, service binaries) returns partial/empty data when commands or files are unavailable.
  - Certificate/key file indicators are bounded and non-recursive (top-level entries only, capped list).
  - Network chain verification details depend on TLS state and `-insecure` mode.

### 5) Ingest boundary vs normalization
- Ingest boundary: `inventory-service` `/scans/ingest` accepts payloads shaped by `ScanIngestRequest` (`assets`, optional `host_inventory`, `crypto_evidence`, `tls_evidence`).
- Normalization currently performed at ingest:
  - trim/clean optional strings
  - normalize list-like fields to `list[str]`
  - drop invalid object types for optional blocks
  - accept both flattened and Stage 2 structured TLS certificate forms
  - carry normalization warnings in `_normalization_warnings`

### 6) How to run Stage 2 smoke validation
```bash
./scripts/run_stage2_smoke_validation.sh
```

It runs:
- `services/inventory-service/tests/test_stage2_smoke_validation.py`
- `services/planner-service/tests/test_planner_api.py::test_plan`

### 7) Known limitations (current state)
- `network-scanner` currently performs TLS scan (`-target host:port`); README headline still mentions TLS/SSH/VPN but current implementation is TLS-focused.
- `linux-host-agent` evidence depth is environment-dependent (OS/files/packages/permissions).
- Inventory keeps evidence JSON blobs as-is after model normalization; no deep semantic enrichment beyond current validators.
- Stage 2 smoke is a short-path validation, not a full multi-service deployment conformance suite.

## TRL Evidence Package

The TRL validation run now generates an Evidence Package v1 with sanitized input and output artifacts for auditability and repeatability.

- Stores validation evidence for host/network inputs, inventory responses, risks, policy decision, planning outputs, and workflow export.
- Location: `reports/evidence/latest/`
- Regenerate: `bash scripts/run_trl_validation.sh`
- Operator checklist: `docs/operator-validation-checklist.md`
- Evidence Pack Index helper: `bash scripts/run_evidence_pack_index.sh`
- TRL6 Demo Evidence Bundle helper: `bash scripts/run_trl6_demo_bundle.sh`
- TRL7 Operational Evidence Bundle helper: `bash scripts/run_trl7_operational_evidence_bundle.sh`
- Outputs: `reports/evidence-pack/evidence-pack-index.json`, `reports/evidence-pack/evidence-pack-index.md`
- Indexes existing local validation artifacts; does not run tests or imply production readiness.
- Supports TRL 5 candidate status by proving a repeatable local validation run with persisted evidence artifacts.

## TRL Validation

Run the repeatable TRL validation harness:

```bash
./scripts/run_trl_validation.sh
```

The script validates the end-to-end flow:
- service health checks (`inventory-service`, `risk-engine`, `planner-service`, `workflow-service`, `policy-engine`, optional `api-gateway`)
- evidence ingest (host + network fixtures)
- inventory output integrity (`scan_id`, `created`, `asset_ids`)
- risk retrieval
- policy evaluation (`POST /evaluate`)
- planning endpoints (`GET /plan`, `GET /waves`)
- workflow export (`POST /export-tasks`)

Generated output:
- `reports/trl-validation-report.md`


Last successful local TRL validation: 2026-05-08 15:09:34 UTC
Command run: `bash scripts/run_trl_validation.sh`
Report generation: successful (`reports/trl-validation-report.md`, `Result: PASS`)

Startup fix summary (2026-05-08):
- `scripts/start_all.sh` now starts the required TRL validation services (`inventory-service`, `risk-engine`, `planner-service`, `workflow-service`, `policy-engine`, `api-gateway`) and verifies `/health` before reporting success.
- `scripts/start_all.sh` uses tighter curl timeouts, longer health wait retries, and restarts services when PID is live but health is failing.
- Process detachment uses `setsid` + PID file write from child process to avoid stale PID tracking and premature STOPPED status in this environment.
- `scripts/status_all.sh` now validates both PID liveness and `/health` endpoint responsiveness.
- `scripts/stop_all.sh` now stops the same required TRL validation service set in reverse order.
- Service logs are written to `logs/*.log` for direct diagnostics.
- Local API Gateway startup now injects local upstream URLs: `INVENTORY_SERVICE_URL=http://127.0.0.1:8001`, `RISK_ENGINE_URL=http://127.0.0.1:8002`, `POLICY_ENGINE_URL=http://127.0.0.1:8007` (plus local planner/workflow/scenario/copilot defaults).

How to inspect logs:
```bash
tail -n 200 logs/inventory-service.log
tail -n 200 logs/risk-engine.log
tail -n 200 logs/planner-service.log
tail -n 200 logs/workflow-service.log
tail -n 200 logs/policy-engine.log
tail -n 200 logs/api-gateway.log
```

Known limitations:
- Validation is local-only and does not yet run against representative production-like infrastructure.
- Failure/retry orchestration is still pending.
- Timestamped evidence archival across multiple runs is still pending.

Environment notes:
- Default local endpoints: inventory `:8001`, risk `:8002`, planner `:8004`, workflow `:8005`, policy `:8007`, api-gateway `:8000`.
- Override endpoints with `INVENTORY_URL`, `RISK_URL`, `PLANNER_URL`, `WORKFLOW_URL`, `POLICY_URL`, `API_GATEWAY_URL`.
- Script is fail-fast (`set -euo pipefail`) and exits immediately if required services or required response fields are missing.

## Project Progress

- [x] Policy evaluation flow
- [x] TRL validation harness v1
- [x] TRL evidence package v1
- [x] Operator validation checklist
- [ ] Real infrastructure validation sample
- [ ] Evidence preservation across timestamped runs

- inventory-service ingest now accepts Stage 2 enriched evidence blocks
- Official Stage 2 enriched evidence fixtures added for host and network ingest.
- risk-engine now derives conservative scoring signals from Stage 2 enriched evidence.
- planner-service now uses Stage 2 risk signals for conservative wave prioritization.
- Dependency graph implementation boundary documented: docs/dependency-graph-implementation-boundary.md

## Copilot Offline Smoke

Run:

```bash
bash scripts/run_copilot_offline_smoke.sh
```

Output:

reports/copilot/offline-smoke-report.md

- Copilot Safety Contract Smoke: `bash scripts/run_copilot_safety_contract_smoke.sh` (report: `reports/copilot/safety-contract-smoke-report.md`)

## TRL 6 readiness validation

```bash
bash scripts/run_trl6_readiness_validation.sh
bash scripts/run_trl6_demo_bundle_smoke.sh
```

## Local Validation Prerequisites

For local validation and evidence-pack tooling:

- Python 3 is required.
- On Ubuntu 24.04, install `python-is-python3` (or run scripts explicitly with `python3` if `python` is not available).
- `pytest` is required for Python tooling/tests used in validation flows.

Suggested setup commands:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python-is-python3
python3 -m pip install pytest
```
