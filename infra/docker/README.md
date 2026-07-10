# Docker Compose

Real containerized wiring of the 15 services `scripts/start_all.sh` starts on bare metal
(same set, same call graph) -- for the on-premise/containerized deployment story the
architecture doc describes. Not a separate stack: same services, same contracts, just
packaged as containers instead of bare processes.

## Run

```bash
cd infra/docker
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

Every service is reachable on the same host port it uses in `start_all.sh`
(inventory-service on 8001, risk-engine on 8002, ..., api-gateway on 8000) -- internally
each container listens on port 8000 and services address each other by Compose service name
(e.g. `http://inventory-service:8000`), not by host port.

```bash
docker compose down          # stop and remove containers
docker compose down -v       # also drop the persisted inventory-service volume
```

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
- `inventory-service`'s SQLite DB lives on a named volume (`inventory-data`) so it survives
  `docker compose down`/`up`; fully separate from the bare-metal dev DB
  (`services/inventory-service/inventory.db`), never touched by this stack.
- `graph-service`, `copilot-service`, and `api-gateway` read the repo's already-committed
  `reports/graph/latest/graph-snapshot.json` via a read-only bind mount, matching the
  bare-metal default; `retrieval-service` does the same for
  `reports/doc-index/latest/doc-index.json`.
- `workflow-service`'s SQLite DB is not volume-backed (the service has no path override env
  var, unlike inventory-service) -- it resets on every `docker compose up --build`. Known,
  same-shape limitation as the bare-metal `workflow.db` (see inventory-service README's
  workspace/report model notes).
- Healthchecks (`GET /health`) gate startup ordering via `depends_on: condition:
  service_healthy`, following each service's real call graph.

## Verified live

Full 15-container build + start, all healthy; ingest -> risk score -> Copilot Risk Narrator
end to end through the gateway; a persisted workspace operator report generated (exercises
the `tools.report.build_operator_report` import); the graph snapshot bind mount readable via
`GET /graph/summary`. `docker compose down` leaves no host-side state changes (bind mounts are
read-only; the named volume is Compose-managed, isolated from the bare-metal dev DB).

## Not included

- `linux-host-agent`, `network-scanner`, `repo-ci-scanner`, `doc-ingestion` are CLI tools run
  against the stack, not long-running services -- same boundary `start_all.sh` already draws.
- `frontend/web-ui` is a buildless static site; run it separately (`npm run dev` in
  `frontend/web-ui`, see that directory's README) against the gateway on port 8000.
- `infra/k8s/` and `infra/terraform/` remain placeholders, not part of this change.
