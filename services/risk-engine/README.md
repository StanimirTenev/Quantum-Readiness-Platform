# Risk Engine

## What this service does
- Calculates weighted risk scores and ratings for assets under defined scenarios.

## Current role in the prototype
- Working prototype scoring engine used by inventory and gateway flows.

## Main endpoints or functions
- `GET /health`, `GET /scenarios`
- `POST /score`

## Inputs / outputs
- Input: bounded numeric factors (`0..5`) plus scenario name and asset metadata.
- Output: JSON with base/final score, normalized score, rating, stage2 signals/adjustment, and rationale fields.

### Stage 2 (optional)
- `stage2_notes` is an optional free-text input used for deterministic signal extraction.
- Extracted signals:
  - `has_hndl_signal`
  - `has_pqc_plan_signal`
  - `high_dependency_pressure`
  - `vendor_blocked`
- Conservative deterministic adjustment:
  - `+0.20` when vendor is blocked
  - `+0.15` when dependency pressure is high (`dependency_count >= 10`)
  - `+0.10` when HNDL signal is present
  - `-0.10` when PQC migration-plan signal is present
  - floor at `0.0` (never negative)

## Current status
- Working prototype service.

## How to run tests
- `pytest services/risk-engine/tests`

## Known limitations
- Weighting and thresholds are static constants in this phase.
