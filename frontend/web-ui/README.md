# Web UI — Quantum Readiness Console

A **buildless** static frontend for the QRP API Gateway. No framework, no bundler,
no `node_modules` — just `public/index.html`, `styles.css`, and `app.js`. It talks
to the gateway with `fetch` and is theme-aware (light/dark).

## What it does
Six panels over the gateway's routes:
- **Fingerprint** — classify algorithms / a TLS certificate (`POST /api/fingerprint`);
  colour-coded findings + a readiness summary.
- **Scenarios** — re-score assets under a quantum-risk scenario (`POST /api/scenarios/run`).
- **Integrations** — integration dry-run preview (`POST /api/integrations/dry-run`);
  always shows execution disabled.
- **Graph** — traverse the dependency snapshot: blast radius, trust chain,
  neighbours (`GET /graph/nodes` to pick a node, `POST /api/graph/*`).
- **Algorithms** — the deterministic knowledge base (`GET /api/algorithms`).
- **Copilot** — free-text `POST /api/copilot/query`, plus a direct button per subagent:
  Risk Narrator and Change Assistant (need an asset name), Discovery Analyst, Vendor
  Intelligence Analyst, and Migration Planner (platform-wide, no input needed). Renders the
  plain-language narrative plus known structured fields (findings, checklist, readiness
  matrix, waves) readably, with the raw JSON always available underneath. All five subagents
  are deterministic — no external LLM call is ever made; see `services/copilot-service/README.md`.

The gateway URL is editable in the header; **Check** hits `GET /health`.

## Run

Start the backend stack (`scripts/start_all.sh`), then serve the UI:

```bash
cd frontend/web-ui
npm run dev            # python -m http.server 5173 --directory public
# open http://127.0.0.1:5173
```

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
