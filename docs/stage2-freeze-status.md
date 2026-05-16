# Stage 2 Freeze Status

## Current Status

Stage 2 Discovery / Evidence Enrichment is complete enough for now.

Stage 2 is frozen as a working enriched-evidence prototype layer.

This does not represent production readiness.

## What Stage 2 Added

### linux-host-agent
- package metadata collection
- certificate file indicators
- SSH/TLS/VPN config indicators
- stable host evidence output contract
- sample output

### network-scanner
- richer TLS metadata
- leaf certificate metadata
- SHA-256 fingerprint
- certificate chain summary
- stable TLS output contract
- sample output

### inventory-service
- accepts Stage 2 enriched host evidence
- accepts Stage 2 enriched network TLS evidence
- official Stage 2 fixtures
- Stage 2 inventory smoke validation

### risk-engine
- derives deterministic evidence signals from Stage 2 host/network evidence
- conservative scoring adjustments
- missing evidence is non-fatal
- old payloads remain backward-compatible

### planner-service
- uses Stage 2 risk signals for conservative prioritization
- weak key/private key indicators are not placed later than wave_2
- certificate_chain_available is informational only
- no dependency graph logic added

### validation
- Stage 2 inventory smoke report
- Stage 2 E2E smoke report
- service tests passing

## Evidence Flow Now Proven

official Stage 2 fixtures
→ inventory ingest
→ risk scoring
→ planner prioritization
→ Stage 2 E2E smoke report

## Validation Commands

```bash
bash scripts/run_stage2_inventory_smoke.sh
bash scripts/run_stage2_e2e_smoke.sh

cd services/inventory-service && PYTHONPATH=. pytest -q
cd services/risk-engine && PYTHONPATH=. pytest -q
cd services/planner-service && PYTHONPATH=. pytest -q
```

## What Is Explicitly Not Included

- no dependency graph
- no real Copilot/RAG implementation
- no external LLM calls
- no production auth/RBAC
- no production deployment hardening
- no Windows agent implementation yet
- no cloud/KMS/HSM integrations
- no autonomous execution

## Privacy / Deployment Principle

QRP is designed for internal/customer-controlled deployment.
Evidence stays local by default.
External LLM usage is optional and opt-in only.
Deterministic core must work without LLM.

## Current Maturity

Current maturity: TRL6 readiness validation package PASS (local relevant-environment simulation). TRL 6 achieved is not claimed.

## Recommended Next Options

1. Stage 3 — Improve risk/planning model
2. Architecture task — dependency graph design only, no implementation
3. Copilot privacy/provider boundary documentation and local-first interface design

Recommended default next step:

Stage 3 — improve risk/planning model, but only after reviewing Stage 2 outputs.

## Stop Rules

Do not start graph, Copilot, RAG, auth, infra, or production integrations until the next active stage is explicitly chosen.
