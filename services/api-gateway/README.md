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

## Local authentication (Product v1 roadmap Phase 3 item 6)
- `POST /api/auth/bootstrap {username, password}` — creates the first Admin user; only works
  while no users exist yet (`409` afterwards). Run this immediately after first deploying the
  stack, before exposing it beyond a trusted network, so nobody else can race to become the
  first admin.
- `POST /api/auth/login {username, password}` — verifies credentials, starts a session, and
  sets an `httponly` session cookie (`qrp_session`, 24h TTL). `401` on a wrong username/password.
- `POST /api/auth/logout` — ends the current session and clears the cookie.
- `GET /api/auth/me` — the current session's user, or `401` if not logged in.
- `POST /api/auth/password {current_password, new_password}` — changes the logged-in user's
  password after re-verifying the current one.
- Passwords are hashed with `bcrypt`, never stored or logged in plaintext. Session tokens are
  stored hashed (like passwords) so a DB dump alone doesn't yield usable session credentials.
- Set `QRP_SESSION_COOKIE_SECURE=true` once this stack sits behind HTTPS (e.g. the `infra/docker`
  `public` Compose profile) -- off by default so local-dev `http://` still gets the cookie back.
- This is real per-user login, alongside (not replacing) `QRP_API_KEY` above -- see
  `docs/adr/0001-product-v1-architecture.md`. It does not yet gate any route by role; RBAC route
  enforcement and the audit log are separate, later roadmap tasks (Phase 3 items 7-8). See `auth.py`.
- Users/sessions live in the same dual SQLite (dev/test)/Postgres (production, via
  `services/api-gateway/migrations/`) model as inventory-service/workflow-service -- see
  `tools/db_compat.py` and `services/inventory-service/README.md`.

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
- The key travels as a plain HTTP header -- pair it with the `infra/docker` `public` Compose
  profile (Caddy reverse proxy, automatic HTTPS) before exposing this stack anywhere the key
  could be intercepted in transit. See `infra/docker/README.md`.

## Public Demo Safety Mode (optional)
- Set `QRP_DEMO_MODE=true` to restrict the gateway to a fixed allowlist -- every `GET`/`HEAD`
  route (all read-only) plus a short list of `POST` routes that either don't persist anything
  (`/api/copilot/query`, `/api/scenarios/run`, `/api/policies/evaluate`, `/api/fingerprint`,
  `/api/normalize`, `/api/pqc-readiness`, `/api/assess`, `/api/attribute`,
  `/api/graph/blast-radius`, `/api/graph/trust-chain`, `/api/graph/neighbors`,
  `/api/graph/evidence-path`, `/api/integrations/dry-run`) or are the controlled, idempotent,
  bounded demo-seeding endpoint itself (`/api/demo/load`) -- not "arbitrary" ingest. Every other
  `POST` (`/api/scans/{host,network,repo,windows}`, `/api/workspaces`,
  `/api/workspaces/{id}/reports`) returns `403`.
- Independent of `QRP_API_KEY` -- a deployment can use either, both, or neither. Meant for an
  unattended public demo instance visitors browse (and click "Load Demo" on) without needing a
  key, while still being unable to ingest arbitrary scans or otherwise mutate persisted state.
- `GET /health` includes a `demo_mode` boolean so the web-ui can show a visible banner -- see
  `frontend/web-ui/README.md`.
- Disabled by default (unset), so local dev/CI need no changes.

## Current status
- Partially implemented integration gateway.

## How to run tests
- `pytest services/api-gateway/tests`

## Known limitations
- Some forwarded routes depend on downstream endpoints that are not fully implemented yet.
