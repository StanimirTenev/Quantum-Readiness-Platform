# Web UI — Quantum Readiness Console

A **buildless** static frontend for the QRP API Gateway. No framework, no bundler,
no `node_modules` — just `public/index.html`, `styles.css`, and `app.js`. It talks
to the gateway with `fetch` and is theme-aware (light/dark).

## What it does
Four panels over the gateway's routes:
- **Fingerprint** — classify algorithms / a TLS certificate (`POST /api/fingerprint`);
  colour-coded findings + a readiness summary.
- **Scenarios** — re-score assets under a quantum-risk scenario (`POST /api/scenarios/run`).
- **Integrations** — integration dry-run preview (`POST /api/integrations/dry-run`);
  always shows execution disabled.
- **Algorithms** — the deterministic knowledge base (`GET /api/algorithms`).

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
