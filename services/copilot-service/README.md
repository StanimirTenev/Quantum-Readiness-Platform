# Copilot Service

## What this service does
- Converts user questions into operational summaries, plan/workflow summaries, asset lookups, search requests, or plain-language risk explanations.
- Risk Narrator (`GET /narrate/{asset_name}`, or `POST /query` with a "why"/"explain" question): deterministic, template-based explanation of an asset's persisted risk — no LLM call. Turns risk-engine's `rationale` flags (weak keys, expiring/expired certs, domain-controller role, dependency count, vendor blocks) into plain-language sentences plus a rating-based recommendation. See `app/risk_narrator.py`.
- Discovery Analyst (`GET /discover`, or `POST /query` with a "discover"/"dependencies" question): deterministic synthesis of crypto dependencies across host/network/repo scans, indexed documents, the dependency graph, and persisted risk records — no LLM call. Classifies findings as explicit (directly observed), inferred (aggregate-signal context scanners don't state directly, e.g. a domain-controller host being a PKI trust anchor, or a graph node's blast radius), and evidence gaps (source types or assets with no supporting evidence). See `app/discovery_analyst.py`.

## Current role in the prototype
- Working prototype orchestration layer for evaluator-facing Q&A over platform data, plus two deterministic Copilot subagents (Risk Narrator, Discovery Analyst) from the architecture reference doc's LLM Copilot Layer subagent model.

## Main endpoints or functions
- `GET /health`, `GET /summary`, `GET /top-risks`, `GET /asset/{asset_name}`
- `GET /narrate/{asset_name}` — Risk Narrator
- `GET /discover` — Discovery Analyst
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
- Discovery Analyst's document keyword matching is a fixed list (`DOC_CRYPTO_KEYWORDS`) with word-boundary matching — not semantic, so a doc discussing "quantum-safe" without ever saying "PQC" or an algorithm name won't surface.
- Discovery Analyst's "inferred context" rules are a small deterministic starter set (domain-controller trust anchor, repo signing without pipeline evidence, graph blast radius) — not exhaustive; extend `app/discovery_analyst.py::_inferred_context` as new inference patterns prove useful.
- Two of five subagents (Risk Narrator, Discovery Analyst) are implemented; Migration Planner, Vendor Intelligence Analyst, and Change Assistant do not exist yet.
