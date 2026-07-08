# Copilot Service

## What this service does
- Converts user questions into operational summaries, plan/workflow summaries, asset lookups, search requests, or plain-language risk explanations.
- Risk Narrator (`GET /narrate/{asset_name}`, or `POST /query` with a "why"/"explain" question): deterministic, template-based explanation of an asset's persisted risk — no LLM call. Turns risk-engine's `rationale` flags (weak keys, expiring/expired certs, domain-controller role, dependency count, vendor blocks) into plain-language sentences plus a rating-based recommendation. See `app/risk_narrator.py`.

## Current role in the prototype
- Working prototype orchestration layer for evaluator-facing Q&A over platform data, plus one deterministic Copilot subagent (Risk Narrator, the first instance of the subagent model described in the architecture reference doc's LLM Copilot Layer section).

## Main endpoints or functions
- `GET /health`, `GET /summary`, `GET /top-risks`, `GET /asset/{asset_name}`
- `GET /narrate/{asset_name}` — Risk Narrator
- `GET /plan-summary`, `GET /workflow-summary`, `GET /operational-summary`
- `POST /query`

## Inputs / outputs
- Input: natural-language question (`{ "question": "..." }`) or simple query params.
- Output: JSON intent + result blocks, built from retrieval/planner/workflow services.

## Current status
- Working prototype service.

## How to run tests
- `pytest services/copilot-service/tests`

## Known limitations
- Intent routing is rule-based keyword matching, not a full LLM agent.
- Risk Narrator only narrates signals present in `RiskRecord.rationale`. As of 2026-07-08, a
  normal `/scans/ingest` (network/host/repo) forwards `tls_metadata`/`crypto_evidence` into
  risk-engine's stage2 evidence-signal extraction (see
  `services/inventory-service/app/risk_mapper.py`), so classical evidence signals (weak keys,
  expiring certs, crypto packages/configs) populate the rationale on a routine ingest, not
  only via a hand-built `/score` call. See `scripts/run_evidence_to_risk_smoke.sh`.
- Only one subagent (Risk Narrator) is implemented; the other four named in the architecture reference (Discovery Analyst, Migration Planner, Vendor Intelligence Analyst, Change Assistant) do not exist yet.
