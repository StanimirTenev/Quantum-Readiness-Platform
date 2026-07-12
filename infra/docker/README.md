# Docker Compose

Real containerized wiring of the 15 services `scripts/start_all.sh` starts on bare metal
(same set, same call graph), plus the web-ui -- for the on-premise/containerized deployment
story the architecture doc describes. Not a separate stack: same services, same contracts,
just packaged as containers instead of bare processes.

## Run

```bash
cd infra/docker
docker compose up -d --build
```

Then open **http://127.0.0.1:5173** in a browser -- that's the whole product: click
**Load Demo** on the Dashboard tab to seed a small realistic dataset (host, network, repo
evidence, and a vendor document) into the running stack, then browse Assets/Findings/Risk/
Migration Plan/Copilot/Reports. No script or service to touch directly. The gateway URL field
in the header is pre-filled with `http://127.0.0.1:8000` -- correct out of the box, since both
the web-ui and the gateway are reachable at `127.0.0.1` from the browser's perspective
regardless of which container they actually run in (only edit it if you've remapped the
gateway's host port).

```bash
curl http://127.0.0.1:8000/health   # backend only, if you don't need the UI
docker compose down          # stop and remove containers
docker compose down -v       # also drop the persisted inventory-service volume
```

## Exposing this outside a trusted local network (demos / presentations)

For the full pre-flight checklist, firewall guidance, an operator walkthrough script, and how
to reset the demo data, see `infra/docker/PUBLIC_DEMO.md`. Short version:

1. Copy `infra/docker/.env.example` to `infra/docker/.env` and fill in real values
   (`QRP_API_KEY`, `POSTGRES_PASSWORD`, `DOMAIN`, `CORS_ALLOW_ORIGINS`) -- `.env` is
   git-ignored, `docker compose` reads it automatically from this directory.
2. Start with the `public` profile, which also brings up **Caddy** as a reverse proxy with
   automatic HTTPS (Let's Encrypt):

   ```bash
   docker compose --profile public up -d --build
   ```

   `DOMAIN` must be a real, publicly resolvable domain (an A/AAAA record pointing at this
   host) -- Let's Encrypt cannot issue a certificate for `localhost` or a bare IP. Use a
   subdomain (e.g. `demo.example.com`) if the root domain is reserved for a separate
   landing/download page. Caddy fails loudly on startup if `DOMAIN` is left empty.
3. `api-gateway` (8000) and `web-ui` (5173) are bound to `127.0.0.1` only -- reachable from
   this host (so local dev/CI curling them directly keeps working unchanged) but not from the
   public internet. Caddy (ports 80/443, published normally) is the only public entry point;
   it talks to both over the internal Compose network (`api-gateway:8000`, `web-ui:5173`), not
   via those loopback-bound ports. Caddy routes `/api/*`, `/health`, and `/graph/*` to
   `api-gateway`, everything else to `web-ui` -- see `infra/docker/Caddyfile`.
4. Every gateway route except `/health` requires a matching `X-API-Key` header once
   `QRP_API_KEY` is set. Open `https://<your-domain>`, paste the same key into the console's
   **API Key** field (next to the gateway URL -- point it at `https://<your-domain>`, not a
   port), click **Check** -- the console attaches the header on every request from then on and
   self-heals anything that failed to load before the key was entered (the dashboard loads
   eagerly on page open, racing the user typing the key). This is a single shared secret, not
   per-user accounts -- adequate for a controlled demo, not a substitute for real auth in a
   multi-tenant deployment. See `services/api-gateway/README.md`.
5. Postgres credentials default to `qrp`/`qrp`/`qrp` -- fine for `docker compose up` with no
   profile, but change `POSTGRES_PASSWORD` in `.env` before using the `public` profile.
6. For an unattended public demo instance visitors browse without needing a key, set
   `QRP_DEMO_MODE=true` (independent of `QRP_API_KEY` -- a deployment can use either, both, or
   neither) -- restricts the gateway to browsing plus the built-in demo dataset, blocking
   arbitrary scan ingest and other mutations (`403`). The console shows a visible banner
   whenever this is on. See `services/api-gateway/README.md`.

Without `--profile public` (plain `docker compose up`), Caddy never starts at all -- this is
the default local/CI path, fully unaffected by any of the above.

## What's wired

- One shared `Dockerfile`, parametrized by a `SERVICE_DIR` build arg, reused for all 15
  services -- they all follow the same `app/main.py` + `requirements.txt` shape, so a single
  image definition covers them (api-gateway's module path, `main:app` instead of
  `app.main:app`, is the one exception, overridden via `command:` in `docker-compose.yml`).
- The build context is the repo root and the image preserves the real `services/<name>/...`
  path (not flattened) because `inventory-service` and `api-gateway` compute their repo root
  as `Path(__file__).resolve().parents[3]` and import shared code from `tools/` at that root
  -- the image copies `tools/` alongside the service for the same reason.
- Every inter-service URL env var (`INVENTORY_SERVICE_URL`, `WORKFLOW_SERVICE_URL`, etc.) is
  set explicitly to the Compose service DNS name; none of the services' own `127.0.0.1`
  defaults apply inside containers.
- `inventory-service`, `workflow-service`, and `api-gateway` run on a shared **PostgreSQL**
  container (`postgres:16-alpine`, one `postgres-data` named volume) here, not SQLite --
  `DATABASE_URL` is set on all three, which their repositories prefer over the SQLite fallback
  they still use everywhere else (bare-metal dev, tests, CI). One Postgres database is shared
  by all three since their table names don't collide (`tasks`/`approvals` vs.
  `workspaces`/`assets`/`scans`/`risk_results`/`reports` vs. `users`/`sessions`) -- no
  per-service database provisioning needed. Credentials default to `qrp`/`qrp`/`qrp`
  (user/password/db), overridable via `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` (e.g.
  in a `.env` file) before exposing this stack anywhere it matters. Fully separate from the
  bare-metal dev DB (`services/inventory-service/inventory.db`), never touched by this stack.
  See `tools/db_compat.py` and `services/inventory-service/README.md`.
- Schema on this Postgres instance is created by Alembic migrations, not implicitly: the
  one-shot `inventory-migrate`/`workflow-migrate`/`gateway-migrate` services run
  `alembic upgrade head` and exit; `inventory-service`/`workflow-service`/`api-gateway` each
  `depends_on` their migrate service with `condition: service_completed_successfully`, so
  `docker compose up` always migrates before the app starts. Re-running `docker compose up`
  against an already-migrated database is a no-op (idempotent). See
  `docs/adr/0001-product-v1-architecture.md` and
  `scripts/run_db_migration_smoke.sh`.
- `graph-service`, `copilot-service`, `retrieval-service`, and `api-gateway` read the repo's
  already-committed `reports/graph/latest/graph-snapshot.json` /
  `reports/doc-index/latest/doc-index.json` via bind mounts landed at the exact path each
  service's own `Path(__file__).resolve().parents[3]`-computed default expects (`/app/reports/
  .../...` inside the container) -- no `GRAPH_SNAPSHOT_PATH`/`DOC_INDEX_PATH` env var override
  needed, the default just resolves correctly. `api-gateway` mounts both **read-write**
  (the others are read-only): `POST /api/demo/load` (`demo_seed.py`) writes a fresh graph
  snapshot and doc index there when seeding the demo dataset, and also reads Stage2 fixture
  files from a third bind mount
  (`services/inventory-service/tests/fixtures/stage2_evidence`, read-only) -- without these
  three mounts, clicking "Load Demo" 500s inside a container (it doesn't on bare metal, where
  the whole repo tree is naturally on disk together).
- `workflow-service`'s tasks/approvals survive `docker compose up --build` via the same
  Postgres volume described above (fixed 2026-07-11; previously reset on every rebuild since
  the service had no persistent store here at all).
- `web-ui` needs no build: it's a buildless static site (see `frontend/web-ui/README.md`), so
  the service just bind-mounts `frontend/web-ui/public` read-only into a stock
  `python:3.12-slim` image and runs the same `python -m http.server 5173` command
  `npm run dev` uses locally, bound to `0.0.0.0` so the container's port mapping reaches it.
  Waits on `api-gateway`'s healthcheck so the UI doesn't come up before the backend can answer
  it (cosmetic only -- the static files serve regardless).
- Healthchecks (`GET /health` for backend services, `GET /` for web-ui) gate startup ordering
  via `depends_on: condition: service_healthy`, following each service's real call graph.
- `caddy` is gated behind Compose's `public` profile (`profiles: ["public"]`), so a plain
  `docker compose up` (local dev, CI) never starts it -- fully inert unless explicitly
  requested. `DOMAIN` is read with a plain `${DOMAIN:-}` default rather than a Compose
  required-variable (`${DOMAIN:?...}`): Compose interpolates every service's variables at
  config-parse time regardless of which profile is active, so a required-variable here would
  break the default profile too, not just fail cleanly when `public` is actually requested.

## Verified live

Full 17-container build + start (16 app services + `postgres`), all healthy; a real
headless-browser (Playwright) run against `http://127.0.0.1:5173` clicking Load Demo end to end
with zero console/page errors (screenshot confirmed clean rendering: assets/risks/graph
snapshot/doc index all populated); `POST /api/demo/load` returns `"overall":"ok"` with all five
steps (`ingest_host`, `ingest_network`, `ingest_repo`, `doc_index`, `graph_snapshot`) reporting
`"status":"ok"`; ingest -> risk score -> Copilot Risk Narrator end to end through the gateway; a
persisted workspace operator report generated (exercises the
`tools.report.build_operator_report` import, plus `inventory-service`'s `create_report`/
`list_scans_by_workspace` against Postgres). `docker compose up -d --build --force-recreate`
(no `-v`) re-verified assets and a `workflow-service` task both survive a full container
rebuild on the `postgres-data` volume. `docker compose down` leaves no host-side state changes
beyond the two bind-mounted
report files `api-gateway` writes to during a Load Demo click (`graph-snapshot.json` is
git-tracked and reverted with `git checkout --` after manual testing, same as any other live
verification in this repo; `doc-index.json` is gitignored).

The `public` profile was verified separately with `DOMAIN=localhost` (Caddy's special case --
issues a locally-trusted certificate instead of requesting one from Let's Encrypt, so the
routing logic can be verified without a real internet-facing domain): `caddy validate` confirmed
the Caddyfile syntax; a real HTTPS request through Caddy correctly reached the console at `/`,
`api-gateway` at `/health`/`/api/algorithms`/`/graph/summary`, and `/api/demo/load` end to end
(identical responses to hitting `api-gateway` directly, confirming Caddy's routing is
transparent); HTTP requests to port 80 redirected to HTTPS (308); `docker port` confirmed
`api-gateway`/`web-ui` bind to `127.0.0.1` only while `caddy` binds `80`/`443` to `0.0.0.0`;
direct `127.0.0.1:8000` access kept working throughout (the same access pattern CI/local dev
use). A plain `docker compose up` (no `--profile public`) afterward confirmed `caddy` never
starts and every other behavior is unchanged. One real bug caught during this verification: a
first attempt using `DOMAIN=localhost docker compose ...` failed because `sudo` drops
environment variables set before it by default -- `sudo` doesn't see a shell prefix assignment
placed before its own name, only variables placed after it
(`sudo DOMAIN=localhost docker compose ...`) or exported beforehand; not a Compose or Caddy bug.

## Not included

- `linux-host-agent`, `network-scanner`, `repo-ci-scanner`, `doc-ingestion` are CLI tools run
  against the stack, not long-running services -- same boundary `start_all.sh` already draws.
- `infra/k8s/` and `infra/terraform/` remain placeholders, not part of this change.
