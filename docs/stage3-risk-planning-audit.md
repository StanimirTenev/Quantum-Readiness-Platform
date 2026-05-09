# Stage 3 Risk/Planning Audit

## Purpose

Stage 3 starts by reviewing the current risk-engine and planner-service behavior as implemented at the Stage 2 freeze point before changing any scoring or planning logic.

## Current Risk Engine Behavior

| Area | Current Behavior | Source File / Test | Notes |
|---|---|---|---|
| Input model | `RiskInput` requires core scoring fields (`criticality`, `confidentiality_lifetime`, `quantum_exposure`, `blast_radius`, `vendor_lock_in`, `migration_difficulty`) plus `asset_name`; optional Stage 2 fields include `stage2_notes`, `crypto_evidence`, and `tls_metadata`; scenario is constrained to known literals. | `services/risk-engine/app/main.py` (`RiskInput`) | Stage 2 evidence is optional; baseline inputs remain accepted. |
| Output model | `RiskOutput` returns score fields, scenario fields, Stage 2 signals/adjustment, and a numeric/bool rationale map. | `services/risk-engine/app/main.py` (`RiskOutput`) | Output is score-centric with signal/rationale detail. |
| Current score fields | `base_score` from weighted factors, multiplied by scenario multiplier, plus Stage 2 adjustment; normalized to `normalized_score_100` and mapped to `rating` buckets. | `services/risk-engine/app/main.py` (`calculate_base_score`, `score`, `classify_rating`) | Final normalized score is capped at 100. |
| Current scenario handling | Scenarios are fixed via `ScenarioName` and `SCENARIO_MULTIPLIERS`; score endpoint applies multiplier by selected scenario. | `services/risk-engine/app/main.py` (`ScenarioName`, `SCENARIO_MULTIPLIERS`, `score`) | Deterministic scenario factor application. |
| Current Stage 2 evidence signals | Signal extraction derives notes signals, dependency/vendor pressure, and evidence flags from crypto/tls metadata (packages, cert/key files, config flags, TLS collected, weak RSA key, cert expiry within 90 days, chain availability). | `services/risk-engine/app/main.py` (`extract_stage2_signals`) | Parsing is defensive (`_safe_int`, `_parse_iso_datetime`). |
| Current adjustment logic | Stage 2 adjustment adds conservative increments for vendor blocked/high dependencies, HNDL/PQC-note hints, and weighted evidence signals; negative totals are clamped to zero. | `services/risk-engine/app/main.py` (`calculate_stage2_adjustment`, `EVIDENCE_SIGNAL_WEIGHTS`) | Stage 2 evidence can strongly increase score; PQC-plan note can reduce by 0.10 only. |
| Current reasons/rationale output | `rationale` includes core numeric inputs plus select boolean evidence flags; `stage2_signals` carries detailed signal objects used for traceability. | `services/risk-engine/app/main.py` (`score`) | Rationale is flat and mixed-type, not yet dimensioned. |
| Backward compatibility behavior | Legacy payloads without enriched evidence still score successfully with zero Stage 2 adjustment; invalid cert date input does not fail scoring. | `services/risk-engine/tests/test_risk_engine.py` (`test_score_endpoint_backward_compatible_without_enriched_evidence`, `test_invalid_certificate_date_does_not_fail`) | Stage 2 optionality and non-fatal parsing are verified by tests. |

## Current Planner Behavior

| Area | Current Behavior | Source File / Test | Notes |
|---|---|---|---|
| Input model | Planner consumes inventory `assets` and `risks` lists; maps assets by name and deduplicates risks to highest normalized score per asset. | `services/planner-service/app/planner.py` (`build_plan`) | No explicit dependency graph input. |
| Output model | Returns summary, `wave_1/2/3` lists, and high-level execution plan phases; each item includes score/rating/scenario plus recommended action and planning reasons. | `services/planner-service/app/planner.py` (`build_plan`) | Designed for deterministic prioritization output. |
| Current wave assignment logic | `priority_score_100` = normalized score + dependency boost + vendor boost + Stage 2 boost; wave thresholds: >=65 wave_1, >=45 wave_2, else wave_3, then Stage 2 caps enforcement. | `services/planner-service/app/planner.py` (`_priority_score`, `build_plan`, `_enforce_stage2_wave_caps`) | Weak/public key signals are escalated to at least wave_2. |
| Current Stage 2 signal handling | High-priority and medium-priority Stage 2 evidence signal maps add boosts and append planning reason tags; unknown/missing signals are tolerated. | `services/planner-service/app/planner.py` (`HIGH_PRIORITY_STAGE2_SIGNALS`, `MEDIUM_PRIORITY_STAGE2_SIGNALS`, `_stage2_priority_boost`, `_planning_reasons`) | `certificate_chain_available` is intentionally informational-only. |
| Current planning reasons | Reasons are emitted as compact tags (e.g., `stage2_weak_public_key`, `stage2_tls_config`) based on evidence signal truth values. | `services/planner-service/app/planner.py` (`_planning_reasons`) | Useful for explainability, but terse and mostly signal-code-like. |
| Current backward compatibility behavior | Planner still builds output when Stage 2 signals are absent or unknown and preserves deterministic dedupe/wave behavior. | `services/planner-service/tests/test_planner.py` (`test_stage2_missing_or_unknown_signals_do_not_fail`, `test_build_plan_deduplicates_risks_and_splits_into_waves`) | Keeps old risk payloads operational. |

## What Stage 2 Proved

Current proven flow:

official Stage 2 fixtures  
→ inventory ingest  
→ risk scoring with Stage 2 signals  
→ planner prioritization  
→ Stage 2 E2E smoke report

This path is explicitly documented in Stage 2 freeze status and validated by the Stage 2 E2E smoke report artifacts.

## Current Strengths

- Deterministic scoring and planning functions with clear fixed multipliers/weights.
- Enriched evidence signals are optional and non-fatal when missing or partially invalid.
- Planner handles high-priority Stage 2 indicators conservatively (not later than wave_2 for weak/public key conditions).
- Old payloads remain valid through backward-compatible request handling.
- E2E smoke path exists and demonstrates fixture-to-plan flow continuity.

## Current Limitations

- Risk score still mixes risk, confidence, and evidence presence into one normalized score path.
- No explicit confidence score is exposed.
- No separate exposure / impact / urgency dimensions are modeled.
- Planner is not dependency-aware in graph terms (only numeric dependency count boosts).
- Planner wave logic is still basic thresholding with simple caps.
- No business owner / application context weighting.
- No SLA / deadline / certificate expiry urgency model beyond simple signal flags.
- No real blast-radius reasoning beyond the single weighted scalar input.

## Stage 3 Improvement Candidates

### Small

- Add `confidence_score` separate from `normalized_score_100`.
- Add `risk_dimensions` object with:
  - `exposure`
  - `impact`
  - `urgency`
  - `migration_complexity`
- Improve rationale structure to separate base factors vs evidence-derived factors.
- Add explicit urgency reason output for expiring certificates.
- Add planner `priority_score` field semantics before wave assignment (clear derivation and rationale).

### Medium

- Asset grouping by environment/criticality bands for planning batches.
- Better scenario factor explanations in score output.
- Planner wave balancing logic for distribution control across waves.
- Owner/team weighting fields if already available in upstream inventory payloads.

### Not Now

- Dependency graph implementation.
- Copilot/RAG integration changes.
- Auth/RBAC changes.
- Production deployment hardening.
- Cloud/KMS/HSM integrations.
- Autonomous execution.

## Recommended Stage 3 Path

1. Stage 3 Task 2 — Add explicit risk_dimensions and confidence_score to risk-engine.
2. Stage 3 Task 3 — Add planner priority_score and clearer wave rationale.
3. Stage 3 Task 4 — Add Stage 3 risk/planning smoke validation.

Graph implementation should not be started in this Stage 3 sequence.

## Definition of Done for Stage 3

Stage 3 should be considered complete when:

- risk-engine separates score, confidence and dimensions
- planner exposes priority_score and clearer wave rationale
- Stage 3 smoke validation proves risk → planner flow
- no graph, copilot or production hardening has been started
