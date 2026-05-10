# Repository Checkpoint — Post Copilot Freeze

## Purpose

This checkpoint records the current repository state after the dependency-graph and Copilot freeze points.

- This is a status checkpoint only.
- No new implementation is included.
- The purpose is to prevent scope drift before choosing the next major direction.

## Current Maturity

Current maturity: TRL 5 candidate / enriched-evidence operational prototype with improved risk/planning analysis, lightweight JSON graph projection, and disabled-provider Copilot stub.

## Architecture Principles Locked

- QRP runs inside customer-controlled environments.
- Evidence stays local by default.
- Graph snapshots stay local by default.
- External LLM usage is optional and opt-in only.
- Deterministic core works without LLM.
- Copilot is advisory only.
- No mandatory cloud AI dependency.
- Cross-platform by design, Linux-first implementation currently.

## Stage 1 — Core Stabilization

Status:

CLOSED

Summarize:
- service startup stabilization
- TRL validation harness
- evidence package
- operator validation checklist
- policy-engine /evaluate
- API Gateway policy forwarding validation
- repeatable local validation

Key artifacts:
- scripts/run_trl_validation.sh
- reports/trl-validation-report.md
- reports/evidence/latest/
- docs/operator-validation-checklist.md

## Stage 2 — Discovery / Evidence Enrichment

Status:

FROZEN

Reference:
- docs/stage2-freeze-status.md

Summarize:
- linux-host-agent package metadata
- certificate file indicators
- SSH/TLS/VPN config indicators
- network-scanner TLS metadata
- certificate chain summary
- inventory enriched evidence ingest
- official Stage 2 fixtures
- Stage 2 smoke validations

Key artifacts:
- scripts/run_stage2_inventory_smoke.sh
- scripts/run_stage2_e2e_smoke.sh
- reports/stage2-inventory-smoke-report.md
- reports/stage2-e2e-smoke-report.md

## Stage 3 — Risk / Planning Improvement

Status:

FROZEN

Reference:
- docs/stage3-freeze-status.md

Summarize:
- risk-engine Stage 2 evidence-derived signals
- confidence_score
- risk_dimensions
- planner priority_score
- clearer planning_reasons
- Stage 3 smoke validation

Key artifacts:
- scripts/run_stage3_risk_planning_smoke.sh
- reports/stage3-risk-planning-smoke-report.md

## Dependency Graph

Status:

FROZEN AS LIGHTWEIGHT JSON SNAPSHOT PROTOTYPE

References:
- docs/dependency-graph-design.md
- docs/dependency-graph-contract.md
- docs/dependency-graph-projection-plan.md
- docs/dependency-graph-projection-validation-examples.md
- docs/dependency-graph-implementation-boundary.md
- docs/dependency-graph-freeze-status.md

Summarize:
- JSON Snapshot First decision
- graph projection from Stage 2 fixtures
- graph helper tests
- polished projection report
- no graph DB/API/UI

Key artifacts:
- scripts/run_graph_projection_smoke.sh
- tools/graph_projection/project_stage2_fixtures.py
- tools/graph_projection/test_project_stage2_fixtures.py
- reports/graph/latest/graph-snapshot.json
- reports/graph/latest/graph-projection-report.md

## Copilot

Status:

FROZEN AS DISABLED-PROVIDER STUB

References:
- docs/copilot-local-first-design.md
- docs/copilot-provider-test-plan.md
- docs/copilot-context-packaging-policy.md
- docs/copilot-implementation-boundary.md
- docs/copilot-freeze-status.md

Summarize:
- local-first provider boundary
- disabled/local/external modes documented
- disabled provider implemented
- POST /copilot/query exists
- deterministic offline-safe response
- no LLM call
- no external endpoint
- offline smoke validation

Key artifacts:
- scripts/run_copilot_offline_smoke.sh
- reports/copilot/offline-smoke-report.md
- services/copilot-service tests

## Privacy Cleanup

Summarize:
- legacy demo external Anthropic call disabled
- demo uses deterministic local placeholder
- no mandatory external LLM dependency preserved

Reference:
- docs/demo/qrp_demo_legacy.html

## Current Validation Commands

bash scripts/run_trl_validation.sh
bash scripts/run_stage2_inventory_smoke.sh
bash scripts/run_stage2_e2e_smoke.sh
bash scripts/run_stage3_risk_planning_smoke.sh
bash scripts/run_graph_projection_smoke.sh
bash scripts/run_copilot_offline_smoke.sh

Service/unit tests:

cd services/inventory-service && PYTHONPATH=. pytest -q
cd services/risk-engine && PYTHONPATH=. pytest -q
cd services/planner-service && PYTHONPATH=. pytest -q
cd services/copilot-service && PYTHONPATH=. pytest -q
cd agents/linux-host-agent && go test ./...
cd agents/network-scanner && go test ./...
python -m pytest tools/graph_projection -q

## What Is Explicitly Not Implemented Yet

- production graph database
- graph API service
- graph UI
- Neo4j
- PostgreSQL graph projection tables
- real dependency traversal / blast-radius engine
- local LLM provider
- external LLM provider
- RAG/vector DB
- embedding model
- real AI Copilot reasoning
- Windows agent
- AD/certificate estate discovery
- cloud/KMS/HSM integrations
- production auth/RBAC
- production deployment hardening
- autonomous execution

## Code Weight Assessment

The repository is still controlled because:
- no new database was added
- no graph DB dependency was added
- no graph API was added
- no graph UI was added
- no real LLM provider was added
- no RAG/vector DB was added
- most additions are deterministic scripts, tests, fixtures, reports and docs

Main risk:
opening graph DB, Copilot, RAG, Windows agent and production hardening at the same time.

## Recommended Next Options

### Option A — Local Copilot Provider Design
Docs-only design for local provider interface and local URL validation.
No implementation yet.

### Option B — Cross-Platform Agent Design
Docs-only design for future Windows/server/workstation coverage.
No implementation yet.

### Option C — Graph API Design
Docs-only design for future graph query API.
No implementation yet.

### Option D — Stop and Full Manual Repo Review
Upload/review full repository package before any more work.

Recommended default:

Option D — Stop and Full Manual Repo Review.

## Stop Rules

Do not start the following until explicitly chosen:

- graph DB
- graph API implementation
- graph UI
- Neo4j
- local Copilot provider implementation
- external LLM integration
- RAG/vector DB
- auth/RBAC
- production infra
- Windows agent implementation
- cloud integrations
- autonomous execution

## One-Sentence Status

"QRP is currently a TRL 5 candidate operational prototype with validated enriched evidence ingestion, improved risk/planning analysis, a lightweight JSON dependency-graph projection prototype, and an offline-safe disabled Copilot stub, still local-first and without production graph/Copilot infrastructure."
