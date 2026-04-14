# Copilot Service

## What this service does
- Converts user questions into operational summaries, plan/workflow summaries, asset lookups, or search requests.

## Current role in the prototype
- Working prototype orchestration layer for evaluator-facing Q&A over platform data.

## Main endpoints or functions
- `GET /health`, `GET /summary`, `GET /top-risks`, `GET /asset/{asset_name}`
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
