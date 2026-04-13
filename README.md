# Quantum Readiness Platform

Project skeleton for the Quantum Readiness Platform with LLM Copilot.

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
