# Repository Checkpoint — Current Status

## Purpose

This document is a checkpoint to prevent scope drift before starting the next major direction.

- This is a status checkpoint.
- No new implementation is included.
- The goal is to record what is working, what is frozen, and what must not be started accidentally.

## Current Maturity


Repository consistency cleanup aligned status wording after TRL6 readiness PASS and demo bundle smoke.

Current maturity: TRL6 readiness validation package PASS (local relevant-environment simulation) with an enriched-evidence operational prototype, improved risk/planning analysis, and lightweight JSON graph projection. TRL 6 achieved is not claimed.
TRL6 readiness package PASS; TRL 6 achieved is not claimed; production readiness is not claimed.

## Current Architecture Principle

- QRP is designed for internal/customer-controlled deployment.
- Evidence stays local by default.
- External LLM usage is optional and opt-in only.
- Deterministic core must work without LLM.
- Graph snapshots are sensitive infrastructure intelligence.
- No mandatory cloud AI dependency.
- Cross-platform by design, Linux-first implementation currently.

## Stage 1 — Core Stabilization

Status:

CLOSED

Summarize completed work:

- service startup stabilization
- TRL validation harness
- evidence package
- operator validation checklist
- policy-engine /evaluate
- API Gateway policy forwarding validation
- repeatable local validation
- README/status wording corrected to TRL 5 candidate

Key artifacts:

- scripts/run_trl_validation.sh
- reports/trl-validation-report.md
- reports/evidence/latest/
- docs/operator-validation-checklist.md
- scripts/run_evidence_pack_index.sh
- scripts/run_trl6_demo_bundle.sh
- reports/evidence-pack/evidence-pack-index.json
- reports/evidence-pack/evidence-pack-index.md

Evidence Pack Index status:
- implemented helper/report tool
- scans predefined local artifacts
- writes JSON/Markdown index
- does not run tests/services
- does not imply production readiness

TRL6 Demo Evidence Bundle status:
- implemented deterministic review/export bundle tool
- scans predefined TRL6/operator/evidence artifacts
- writes JSON/Markdown bundle indexes to reports/trl6/demo-bundle/
- does not run tests/services or regenerate source evidence
- does not claim TRL 6 achieved or production readiness
- TRL6 Demo Bundle Integrity Smoke validation tooling added: `bash scripts/run_trl6_demo_bundle_smoke.sh` (integrity/report validation only)

## Stage 2 — Discovery / Evidence Enrichment

Status:

FROZEN

Reference:

- docs/stage2-freeze-status.md

Summarize completed work:

### linux-host-agent
- package metadata
- certificate file indicators
- SSH/TLS/VPN config indicators
- stable evidence output contract
- sample output

### network-scanner
- richer TLS metadata
- leaf certificate metadata
- SHA-256 fingerprint
- certificate chain summary
- stable TLS output contract

### inventory-service
- accepts enriched host evidence
- accepts enriched network TLS evidence
- official Stage 2 fixtures
- Stage 2 inventory smoke validation

### Stage 2 validation
- scripts/run_stage2_inventory_smoke.sh
- scripts/run_stage2_e2e_smoke.sh
- reports/stage2-inventory-smoke-report.md
- reports/stage2-e2e-smoke-report.md

## Stage 3 — Risk / Planning Improvement

Status:

FROZEN

Reference:

- docs/stage3-freeze-status.md

Summarize completed work:

### risk-engine
- Stage 2 evidence-derived signals
- conservative score adjustments
- confidence_score
- risk_dimensions
- backward compatibility
- non-fatal missing/invalid optional evidence

### planner-service
- Stage 2 signal-aware prioritization
- priority_score
- clearer planning_reasons
- weak key/private key not later than wave_2
- no dependency graph logic

### Stage 3 validation
- scripts/run_stage3_risk_planning_smoke.sh
- reports/stage3-risk-planning-smoke-report.md

## Dependency Graph

Status:

FROZEN AS LIGHTWEIGHT JSON SNAPSHOT PROTOTYPE

Reference documents:

- docs/dependency-graph-design.md
- docs/dependency-graph-contract.md
- docs/dependency-graph-projection-plan.md
- docs/dependency-graph-projection-validation-examples.md
- docs/dependency-graph-implementation-boundary.md
- docs/dependency-graph-freeze-status.md
- docs/graph-api-design.md (minimal read-only snapshot API endpoints implemented)
- docs/graph-snapshot-loader-design.md (design reference for read-only local-file helper behavior)
- docs/graph-api-readonly-freeze-status.md (read-only boundary freeze for current Graph API scope)

Implemented lightweight artifacts:

- scripts/run_graph_projection_smoke.sh
- tools/graph_projection/project_stage2_fixtures.py
- tools/graph_projection/test_project_stage2_fixtures.py
- reports/graph/latest/graph-snapshot.json
- reports/graph/latest/graph-projection-report.md

State clearly:

- JSON Snapshot First
- no graph DB
- no Neo4j
- graph snapshot loader helper is implemented for local read-only snapshot validation
- minimal read-only graph API endpoints are implemented in api-gateway (snapshot-backed only)
- no graph UI
- no full dependency traversal yet
- production graph infrastructure remains not implemented

Graph API read-only hardening status:
- Graph API read-only hardening coverage has been added for the existing snapshot-backed GET endpoints; no new endpoints, mutation methods, graph DB, Neo4j, traversal, blast-radius, or production graph infrastructure were added.
- stronger tests/smoke cover stable response keys/shapes for existing GET /graph/* endpoint responses
- node_type and edge_type filters are checked
- unsafe/missing GRAPH_SNAPSHOT_PATH error behavior is checked
- mutation methods are verified not to return successful 2xx responses
- response content is checked for no DB/Neo4j/traversal/blast-radius indicators
- endpoint surface area remains unchanged

Windows inventory schema/validator hardening status:
- Windows inventory schema/validator contract coverage has been strengthened as tests-only preparation; Windows runtime ingestion, Windows agent, AD scanner, and credential/private key handling remain not implemented.
- strict tests-only Windows schema/validator contract coverage is added
- recursive sensitive-key/value safety scan coverage is added
- normalized aggregate-only summary contract coverage is strengthened
- no runtime ingestion is implemented
- no Windows support implemented claim is made

## Privacy Cleanup

Summarize:

- legacy demo hardcoded external Anthropic call disabled
- local deterministic placeholder response used instead
- no mandatory external LLM dependency preserved

Reference:

- docs/demo/qrp_demo_legacy.html

## Current Validation Commands

bash scripts/run_trl_validation.sh
bash scripts/run_stage2_inventory_smoke.sh
bash scripts/run_stage2_e2e_smoke.sh
bash scripts/run_stage3_risk_planning_smoke.sh
bash scripts/run_graph_projection_smoke.sh
bash scripts/run_graph_snapshot_loader_smoke.sh
bash scripts/run_trl6_readiness_validation.sh

TRL 6 readiness validation script status:
- implemented as deterministic validation orchestration/reporting only
- does not claim TRL 6 achieved

Service/unit tests:

cd services/inventory-service && PYTHONPATH=. pytest -q
cd services/risk-engine && PYTHONPATH=. pytest -q
cd services/planner-service && PYTHONPATH=. pytest -q
cd agents/linux-host-agent && go test ./...
cd agents/network-scanner && go test ./...
python -m pytest tools/graph_projection -q


## Next TRL6 Evidence Step

- Operator Review / Demo Sign-off Package
- Operator Review Execution Record: `reports/trl6/operator-review-execution-record.md` (prepared; pending named operator/reviewer sign-off)
- Relevant-Environment Demo Evidence Record: `reports/trl6/relevant-environment-demo-evidence.md` (prepared template; pending real relevant-environment demo execution)
- Relevant-Environment Demo Execution Summary: `reports/trl6/relevant-environment-demo-execution-summary.md` (prepared; pending real relevant-environment demo execution)
- Relevant-Environment Demo Run Instructions: `reports/trl6/relevant-environment-demo-run-instructions.md` (prepared instruction sheet; demo execution remains pending)
- TRL6 Claim Review Readiness Checklist: `reports/trl6/trl6-claim-review-readiness-checklist.md` (prepared; current claim decision state: NOT_READY)
  - `reports/trl6/operator-review-summary.md`
  - `reports/trl6/operator-demo-checklist.md`
  - `docs/trl6-operator-review-boundary.md`
  - `reports/external-review/partner-handoff-pack.md` (external partner/operator technical review handoff artifact)
- This is an evidence review/sign-off step only.
- TRL 6 achieved is not claimed in this checkpoint.

## What Is Not Implemented Yet

- production graph database
- separate production graph API service
- graph UI
- Neo4j
- PostgreSQL graph tables
- real dependency traversal / blast-radius engine
- real Copilot/RAG implementation
- external LLM provider interface
- Windows agent
- AD/certificate estate discovery
- cloud/KMS/HSM integrations
- production auth/RBAC
- production deployment hardening
- autonomous execution

## Code Weight Assessment

The code is still controlled because:
- no new database was added
- no graph DB dependency was added
- no separate graph API service was added; only minimal read-only graph endpoints were added to the existing api-gateway
- no graph UI was added
- no Copilot/RAG implementation was added
- most additions are deterministic scripts, tests, fixtures, reports and docs

Main risk:
opening too many new tracks at once.

## Recommended Next Options

### Option A — Copilot Local-First Design
Docs-only design for provider boundary:
- disabled provider
- local provider
- optional external provider
- no external default

### Option B — Cross-Platform Agent Design
Docs-only design for:
- Linux current implementation
- Windows future agent
- workstation/server differences
- no coding yet

### Option C — Graph Pause / Review
Stop graph work and review whether JSON snapshot is enough for now.

Recommended default:

Option A — Copilot Local-First Design, because privacy/local-first is a core product differentiator and must be designed before any Copilot implementation.

Additional docs-only recommended option:

- Cross-Platform Agent Design (`docs/cross-platform-agent-design.md`) for future Windows/AD evidence modeling without implementation changes.
- Windows Evidence Fixture Contract (`docs/windows-evidence-fixture-contract.md`) as docs/fixture-only preparation for future Windows evidence ingestion without implementation changes.
- Inventory Windows Evidence Acceptance Design (`docs/inventory-windows-evidence-acceptance-design.md`) as docs-only next preparation for future inventory acceptance modeling without runtime ingestion changes.
- Windows Risk/Planning Signal Mapping Design (`docs/windows-risk-planning-signal-mapping-design.md`) as docs-only preparation for future aggregate Windows risk/planning signals without runtime mapping changes.

## Stop Rules

Do not start the following until explicitly chosen:

- graph DB
- graph API
- graph UI
- Neo4j
- Copilot implementation
- RAG implementation
- external LLM integration
- auth/RBAC
- production infra
- Windows agent implementation
- cloud integrations
- autonomous execution

## One-Sentence Status

"QRP is currently a TRL 5 candidate operational prototype with validated enriched evidence ingestion, improved risk/planning analysis, and a first lightweight JSON dependency-graph projection smoke path, still local-first and without production graph/Copilot infrastructure."

## TRL 6 Readiness Track (Next Direction)

- Next direction: execute a docs-first TRL 6 readiness track focused on relevant-environment validation planning and operator-driven demonstration evidence.
- Status remains conservative: TRL 6 is not yet claimed.
- See: `docs/trl6-readiness-plan.md`
