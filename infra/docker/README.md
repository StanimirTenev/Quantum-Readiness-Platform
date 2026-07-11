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

Only `api-gateway` (8000) and `web-ui` (5173) publish a host port -- every other service
(inventory-service, risk-engine, etc.) is reachable only on the internal Compose network, the
same way they already call each other. Set a shared key before exposing the stack publicly:

```bash
QRP_API_KEY=some-long-random-string docker compose up -d --build
```

Every gateway route except `/health` then requires a matching `X-API-Key` header. Open
`http://<host>:5173`, paste the same key into the console's **API Key** field (next to the
gateway URL), click **Check** -- the console attaches the header on every request from then on
and self-heals anything that failed to load before the key was entered (the dashboard loads
eagerly on page open, racing the user typing the key). This is a single shared secret, not
per-user accounts -- adequate for a controlled demo, not a substitute for real auth in a
multi-tenant deployment. See `services/api-gateway/README.md`.

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
- `inventory-service` and `workflow-service` run on a shared **PostgreSQL** container
  (`postgres:16-alpine`, one `postgres-data` named volume) here, not SQLite -- `DATABASE_URL`
  is set on both, which their repositories prefer over the SQLite fallback they still use
  everywhere else (bare-metal dev, tests, CI). One Postgres database is shared by both
  services since their table names don't collide (`tasks`/`approvals` vs.
  `workspaces`/`assets`/`scans`/`risk_results`/`reports`) -- no per-service database
  provisioning needed. Credentials default to `qrp`/`qrp`/`qrp` (user/password/db), overridable
  via `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` (e.g. in a `.env` file) before exposing
  this stack anywhere it matters. Fully separate from the bare-metal dev DB
  (`services/inventory-service/inventory.db`), never touched by this stack. See
  `tools/db_compat.py` and `services/inventory-service/README.md`.
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

## Not included

- `linux-host-agent`, `network-scanner`, `repo-ci-scanner`, `doc-ingestion` are CLI tools run
  against the stack, not long-running services -- same boundary `start_all.sh` already draws.
- `infra/k8s/` and `infra/terraform/` remain placeholders, not part of this change.
