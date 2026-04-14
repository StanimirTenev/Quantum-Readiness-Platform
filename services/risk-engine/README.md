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
- Output: JSON with base/final score, normalized score, rating, and rationale fields.

## Current status
- Working prototype service.

## How to run tests
- `pytest services/risk-engine/tests`

## Known limitations
- Weighting and thresholds are static constants in this phase.
