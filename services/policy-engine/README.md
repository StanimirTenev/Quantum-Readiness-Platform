# Policy Engine

## What this service does
- Provides deterministic policy evaluation for PQC readiness decisions.

## Endpoints
- `GET /health`
  - Returns service health status.
- `POST /evaluate`
  - Evaluates a policy request and returns deterministic `allow`, `deny`, or `review` decision output.

## Policy rule metadata
- `rule_id`: `pqc-readiness-gate-v1`
- `rule_version`: `1.0.0`

## Decision behavior
- Deterministic logic is applied from the request attributes and produces:
  - `allow` when readiness signals meet the gate.
  - `review` when the request requires manual review.
  - `deny` when blocking conditions are met.

## Inputs / outputs
- Input: JSON policy evaluation payload.
- Output: JSON response containing `decision`, `reasons`, `rule_id`, and `rule_version`.
