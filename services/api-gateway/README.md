# API Gateway

## What this service does
- Provides a single HTTP entry point for ingest, asset, risk, scenario, and copilot routes.

## Current role in the prototype
- Working prototype gateway that forwards requests to inventory, risk, copilot, and scenario services.

## Main endpoints or functions
- `GET /health`
- `POST /api/scans/{host|network|repo}`
- `GET /api/assets`, `GET /api/assets/{asset_id}`, `GET /api/assets/{asset_id}/risk`, `GET /api/assets/{asset_id}/history`
- `POST /api/scenarios/run`, `POST /api/copilot/{query|explain-risk|generate-wave-plan}`
- `POST /api/policies/evaluate`
- `GET /api/algorithms`, `POST /api/fingerprint` (crypto-fingerprint-service, `CRYPTO_FINGERPRINT_URL`, default port 8003)
- `POST /api/normalize` (evidence-normalizer, `EVIDENCE_NORMALIZER_URL`, default port 8009)
- `GET /api/readiness-states`, `POST /api/pqc-readiness` (pqc-readiness-service, `PQC_READINESS_URL`, default port 8012)
- `POST /api/assess` — chains crypto-fingerprint → pqc-readiness → finding-attribution → optional risk-engine for one asset
- `POST /api/attribute` (finding-attribution-service, `FINDING_ATTRIBUTION_URL`, default port 8014) — location + service/application attribution per finding
- `GET /api/graph/queries`, `POST /api/graph/{blast-radius,trust-chain,neighbors}` (graph-service, in-memory traversal, `GRAPH_SERVICE_URL`, default port 8013)
- `GET /api/integrations`, `POST /api/integrations/dry-run` (integration-service, dry-run/disabled, `INTEGRATION_SERVICE_URL`, default port 8011)
- `GET /graph/{snapshot|summary|nodes|edges|warnings}` (read-only snapshot)

## Inputs / outputs
- Input: JSON payloads for scans, scenario runs, and copilot requests.
- Output: JSON passthrough responses from downstream services.

## Current status
- Partially implemented integration gateway.

## How to run tests
- `pytest services/api-gateway/tests`

## Known limitations
- Some forwarded routes depend on downstream endpoints that are not fully implemented yet.
