# Web UI — Quantum Readiness Console

A **buildless** static frontend for the QRP API Gateway. No framework, no bundler,
no `node_modules` — just `public/index.html`, `styles.css`, and `app.js`. It talks
to the gateway with `fetch` and is theme-aware (light/dark).

## What it does
An **operator workflow** as the primary navigation, plus the original deterministic-core
testing tools kept as secondary tabs (visually separated, still fully functional):

Operator workflow:
- **Dashboard** (the default/first tab) — one click ("Load Demo") seeds a small realistic
  dataset (host, network, repo evidence, and a vendor document) via `POST /api/demo/load` into
  the running stack, without touching any script or service directly. "Refresh demo status"
  re-checks (`GET /api/demo/status`) without re-seeding. `POST /api/demo/load` is idempotent:
  an asset already present is skipped, not re-ingested, so clicking twice never creates
  duplicates. Also shows a platform overview, clickable top-risk rows
  (`GET /api/copilot/operational-summary`), and the current demo workspace (project/workspace
  model -- see `services/inventory-service/README.md`): a workspace is created only when
  there's something new to seed, and all of that click's scans join it.
- **Assets** — every asset (`GET /api/assets`) with its rating, as a clickable table. Clicking
  a row opens **Asset detail**: Risk Narrator's explanation, Change Assistant's checklist, and
  the asset's migration wave — the core click-through flow (asset row → narrative → checklist →
  wave), sourced from two calls (`GET /api/copilot/narrate/{asset}` and
  `GET /api/copilot/change-plan/{asset}`, the latter already carrying the wave assignment).
- **Findings** — Discovery Analyst's explicit findings, inferred context, and evidence gaps
  (`GET /api/copilot/discover`).
- **Risk** — every scored asset ranked by priority (`GET /api/copilot/migration-plan`'s waves,
  flattened); rows are also clickable, jumping to the same asset detail view.
- **Migration Plan** — Migration Planner's per-wave narrative and vendor readiness context
  (`GET /api/copilot/migration-plan`).
- **Copilot** — free-text `POST /api/copilot/query`, plus a direct button per subagent:
  Risk Narrator and Change Assistant (need an asset name), Discovery Analyst, Vendor
  Intelligence Analyst, and Migration Planner (platform-wide, no input needed). Renders the
  plain-language narrative plus known structured fields (findings, checklist, readiness
  matrix, waves) readably, with the raw JSON always available underneath. All five subagents
  are deterministic — no external LLM call is ever made; see `services/copilot-service/README.md`.
- **Reports** — the live operational summary (`GET /api/copilot/operational-summary`), plus a
  "Generate workspace report" button that persists a real operator report for the current demo
  workspace (`POST /api/workspaces/{id}/reports`) and renders it inline. The full file-based
  demo reports written by `scripts/run_product_demo.sh` live under `reports/product-demo/` on
  disk (not served over HTTP).

Deterministic core (secondary tabs):
- **Fingerprint** — classify algorithms / a TLS certificate (`POST /api/fingerprint`);
  colour-coded findings + a readiness summary.
- **Scenarios** — re-score assets under a quantum-risk scenario (`POST /api/scenarios/run`).
- **Integrations** — integration dry-run preview (`POST /api/integrations/dry-run`);
  always shows execution disabled.
- **Graph** — traverse the dependency snapshot: blast radius, trust chain,
  neighbours (`GET /graph/nodes` to pick a node, `POST /api/graph/*`).
- **Algorithms** — the deterministic knowledge base (`GET /api/algorithms`).

The gateway URL is editable in the header; **Check** hits `GET /health`. An **API Key** field
next to it attaches `X-API-Key` on every request when the gateway requires one
(`QRP_API_KEY` -- see `services/api-gateway/README.md`); a page-load health check (and every
successful **Check** click) also reads `GET /health`'s `demo_mode` flag and shows a banner
across the top of the page when the gateway is running in Public Demo Safety Mode
(`QRP_DEMO_MODE=true` -- scanning and other mutations return `403` in that mode).

## Run

Start the backend stack (`scripts/start_all.sh`), then serve the UI:

```bash
cd frontend/web-ui
npm run dev            # python -m http.server 5173 --directory public
# open http://127.0.0.1:5173
```

Or via Docker Compose (backend + web-ui together, one command) -- see
`infra/docker/README.md`.

The gateway enables CORS (`CORS_ALLOW_ORIGINS`, default `*`) so the browser app
can call it cross-origin during local development.

## Build

```bash
cd frontend/web-ui
npm run build         # copies public/ -> dist/ for static hosting
```

## Verify (no test framework needed)

```bash
node --check public/app.js     # JS parses
npm run build                  # produces dist/
```

## Notes / limitations
- Dynamic text is HTML-escaped before rendering; data comes from the local,
  validated gateway. For a hardened deployment, add a sanitizer and same-origin
  serving instead of permissive CORS.
- No persistence; it is a thin console over the deterministic core.
