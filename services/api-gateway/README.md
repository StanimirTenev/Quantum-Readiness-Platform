# API Gateway

## What this service does
- Provides a single HTTP entry point for ingest, asset, risk, scenario, and copilot routes.

## Current role in the prototype
- Working prototype gateway that forwards requests to inventory, risk, copilot, and scenario services.

## Main endpoints or functions
- `GET /health`
- `POST /api/scans/{host|network|repo}`
- `GET /api/assets`, `GET /api/assets/{asset_id}`, `GET /api/assets/{asset_id}/risk`, `GET /api/assets/{asset_id}/history`
- `POST /api/scenarios/run`
- `POST /api/copilot/query`, `GET /api/copilot/narrate/{asset_name}`, `GET /api/copilot/discover`, `GET /api/copilot/vendor-intelligence`, `GET /api/copilot/migration-plan`, `GET /api/copilot/change-plan/{asset_name}`, `GET /api/copilot/{plan-summary|workflow-summary|operational-summary}` (copilot-service, `COPILOT_SERVICE_URL`, default port 8008)
- `POST /api/policies/evaluate`
- `GET /api/algorithms`, `POST /api/fingerprint` (crypto-fingerprint-service, `CRYPTO_FINGERPRINT_URL`, default port 8003)
- `POST /api/normalize` (evidence-normalizer, `EVIDENCE_NORMALIZER_URL`, default port 8009)
- `GET /api/readiness-states`, `POST /api/pqc-readiness` (pqc-readiness-service, `PQC_READINESS_URL`, default port 8012)
- `POST /api/assess` — chains crypto-fingerprint → pqc-readiness → finding-attribution → optional risk-engine for one asset
- `POST /api/attribute` (finding-attribution-service, `FINDING_ATTRIBUTION_URL`, default port 8014) — location + service/application attribution per finding
- `GET /api/graph/queries`, `POST /api/graph/{blast-radius,trust-chain,neighbors}` (graph-service, in-memory traversal, `GRAPH_SERVICE_URL`, default port 8013)
- `GET /api/integrations`, `POST /api/integrations/dry-run` (integration-service, dry-run/disabled, `INTEGRATION_SERVICE_URL`, default port 8011)
- `GET /graph/{snapshot|summary|nodes|edges|warnings}` (read-only snapshot)
- `POST /api/demo/load`, `GET /api/demo/status` — seeds/checks the small realistic demo dataset
  (host/network/repo evidence + a vendor document, graph snapshot, doc index) the web-ui's
  Dashboard tab uses. The one deliberate exception to the gateway being read-only/proxy-only:
  writes directly, but only through the normal `/scans/ingest` contract plus a graph
  snapshot/doc index file write, same as a real collector would. Idempotent -- an asset
  already present is skipped, not re-ingested. Creates a workspace (see below) only when
  there's actually something new to ingest. See `demo_seed.py`.
- `POST /api/workspaces`, `GET /api/workspaces`, `GET /api/workspaces/{workspace_id}` (rollup:
  scans/risks/reports), `POST /api/workspaces/{workspace_id}/reports`,
  `GET /api/reports/{report_id}`, `GET /api/reports` (optional `?workspace_id=`) — proxy the
  lightweight workspace/report model; see `services/inventory-service/README.md`.
  `POST /api/scans/{host|network|repo}` and `/api/demo/load` also accept `?workspace_id=` to
  group a scan under an existing workspace.

## Inputs / outputs
- Input: JSON payloads for scans, scenario runs, and copilot requests.
- Output: JSON passthrough responses from downstream services.

## Shared API key (optional)
- Set `QRP_API_KEY` to require an `X-API-Key` header matching it on every route except
  `/health` and CORS preflight (`OPTIONS`) -- unset (default) leaves the gateway open, so
  local dev/CI need no header. A single shared secret, not per-user accounts -- meant to
  gate exposing this stack outside a trusted local network (e.g. a public demo), not as a
  substitute for real auth in a multi-tenant deployment.
- Only this service enforces it. The other 14 services are not meant to be reachable
  directly outside the internal network -- see `infra/docker/README.md`.

## Current status
- Partially implemented integration gateway.

## How to run tests
- `pytest services/api-gateway/tests`

## Known limitations
- Some forwarded routes depend on downstream endpoints that are not fully implemented yet.
