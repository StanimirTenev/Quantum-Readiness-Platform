# Quantum Readiness Platform

Quantum Readiness Platform is a cybersecurity software prototype for automated post-quantum cryptography assessment — host and network evidence collection, risk scoring, and migration planning. Current status: TRL 5 candidate based on repeatable local validation.

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

## Architecture and delivery navigation
- Core architecture: `docs/architecture.md`
- TRL5 execution roadmap: `docs/trl5-working-navigator.md`
- Stage 1 core stabilization execution: `docs/stage1-core-stabilization.md`

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


Last successful local TRL validation: 2026-05-08 10:06:39 UTC
Command run: `bash scripts/run_trl_validation.sh`
Report generation: successful (`reports/trl-validation-report.md`, `Result: PASS`)
Known limitations:
- Validation is local-only and does not yet run against representative production-like infrastructure.
- Evidence artifacts are not yet archived automatically for audit trails.
- Failure/retry orchestration and operator runbook checklist are still pending.

Environment notes:
- Default local endpoints: inventory `:8001`, risk `:8002`, planner `:8004`, workflow `:8005`, policy `:8007`, api-gateway `:8000`.
- Override endpoints with `INVENTORY_URL`, `RISK_URL`, `PLANNER_URL`, `WORKFLOW_URL`, `POLICY_URL`, `API_GATEWAY_URL`.
- Script is fail-fast (`set -euo pipefail`) and exits immediately if required services or required response fields are missing.
