# Copilot Service

## What this service does
- Converts user questions into operational summaries, plan/workflow summaries, asset lookups, search requests, or plain-language risk explanations.
- Risk Narrator (`GET /narrate/{asset_name}`, or `POST /query` with a "why"/"explain" question): deterministic, template-based explanation of an asset's persisted risk — no LLM call. Turns risk-engine's `rationale` flags (weak keys, expiring/expired certs, domain-controller role, dependency count, vendor blocks, weak/legacy SSH algorithms, embedded private keys in a repo) into plain-language sentences plus a rating-based recommendation. See `app/risk_narrator.py`.
- Discovery Analyst (`GET /discover`, or `POST /query` with a "discover"/"dependencies" question): deterministic synthesis of crypto dependencies across host/network/repo scans, indexed documents, the dependency graph, and persisted risk records — no LLM call. Surfaces SSH algorithm offers (network scans) and IaC-declared algorithms / embedded private keys (repo scans) as explicit findings alongside the existing host/TLS/CI ones. Classifies findings as explicit (directly observed), inferred (aggregate-signal context scanners don't state directly, e.g. a domain-controller host being a PKI trust anchor, or a graph node's blast radius), and evidence gaps (source types or assets with no supporting evidence). See `app/discovery_analyst.py`.
- Vendor Intelligence Analyst (`GET /vendor-intelligence`, or `POST /query` with a "vendor"/"roadmap"/"readiness matrix" question): deterministic extraction of PQC readiness claims from indexed vendor documents — no LLM call. Classifies each paragraph-level claim by `claimed_readiness` (reusing pqc-readiness-service's own state taxonomy: classical_only/hybrid_capable/pqc_ready/vendor_blocked/unknown), a `confidence` (certain/uncertain/unknown — roadmap language like "we plan to" or "Q3 2026" is flagged uncertain, not treated as fact), and whether it's a migration blocker note. Aggregates into a per-document `readiness_matrix`. See `app/vendor_intelligence_analyst.py`.
- Migration Planner (`GET /migration-plan`, or `POST /query` with a "migration plan"/"sequencing" question): deterministic plain-language explanation of planner-service's algorithmic wave/priority plan — no LLM call. Turns each asset's `planning_reasons` codes into narrative sentences (why it landed in its wave), flags vendor-blocked assets, and surfaces Vendor Intelligence Analyst's readiness matrix as document-level context (not joined to specific assets — no reliable asset<->vendor-doc key exists yet, and a fuzzy name match would risk a misleading link). See `app/migration_planner.py`.
- Change Assistant (`GET /change-plan/{asset_name}`, or `POST /query` with a "change plan"/"checklist" question naming an asset): deterministic draft pre-change checklist for one asset — no LLM call, and never executes or schedules anything itself (only GETs existing state). Turns the asset's risk rationale into actionable pre-checks (e.g. "confirm a PQC-capable replacement certificate is provisioned"), reports its recommended wave, and either references an existing workflow-service task or suggests creating one — never creating a duplicate silently. Always ends with an explicit safety notice that QRP does not execute changes. See `app/change_assistant.py`.

## Current role in the prototype
- Working prototype orchestration layer for evaluator-facing Q&A over platform data, plus all five deterministic Copilot subagents (Risk Narrator, Discovery Analyst, Vendor Intelligence Analyst, Migration Planner, Change Assistant) named in the architecture reference doc's LLM Copilot Layer subagent model.

## Main endpoints or functions
- `GET /health`, `GET /summary`, `GET /top-risks`, `GET /asset/{asset_name}`
- `GET /narrate/{asset_name}` — Risk Narrator
- `GET /discover` — Discovery Analyst
- `GET /vendor-intelligence` — Vendor Intelligence Analyst
- `GET /migration-plan` — Migration Planner
- `GET /change-plan/{asset_name}` — Change Assistant
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
- Vendor Intelligence Analyst classifies at paragraph granularity within a chunk (split on blank lines), not sentence granularity — two claims run together without a blank line between them would still be conflated into one classification.
- Vendor Intelligence Analyst's `product_hint` is derived from the document's filename, not parsed from its body — a v1 heuristic; the doc, not an NLP-extracted product name, is the unit of the readiness matrix.
- Migration Planner's vendor readiness context is document-level, not per-asset: it reports "N analyzed vendor documents raise a blocker" without claiming which specific asset(s) that blocker applies to.
- Change Assistant's pre-change checklist is a deterministic starter set keyed off the same rationale flags Risk Narrator uses, now including SSH (weak kex/host-key/cipher/MAC) and repo/IaC (embedded private key) items; it still doesn't cover CI-pipeline-specific remediation steps (e.g. rotating a signing key referenced in a CI workflow, as opposed to a key found embedded in the repo itself).
- All five named subagents (Risk Narrator, Discovery Analyst, Vendor Intelligence Analyst, Migration Planner, Change Assistant) are implemented.
