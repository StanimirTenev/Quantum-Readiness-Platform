# Retrieval Service

## What this service does
- Aggregates platform data for overview, asset-level lookup, and keyword search.

## Current role in the prototype
- Working prototype retrieval layer used by copilot and UI workflows.

## Main endpoints or functions
- `GET /health`, `GET /overview`, `GET /asset`
- `POST /search`

## Inputs / outputs
- Input: optional `asset_name` query parameter and search query JSON (`{ "query": "..." }`).
- Output: JSON overview metrics, asset bundles, and ranked search results.

## Current status
- Working prototype service.

## How to run tests
- `pytest services/retrieval-service/tests`

## Known limitations
- Search is in-memory and rule-based; no dedicated indexing backend is used.
