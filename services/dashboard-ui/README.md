# Dashboard UI Service

## What this service does
- Serves the static dashboard and proxies UI API calls to backend services.

## Current role in the prototype
- Legacy: superseded by `frontend/web-ui` (the actively developed, tested console -- see
  `frontend/web-ui/README.md`). Not started by `scripts/start_all.sh` or
  `infra/docker/docker-compose.yml`; kept for reference, not part of the live product flow.

## Main endpoints or functions
- `GET /` and `/static/*` for UI assets
- `GET /api/{health|summary|operational-summary|plan|tasks|approvals|asset}`
- `POST /api/{search|export-tasks|copilot-query}`

## Inputs / outputs
- Input: browser HTTP requests and JSON payloads from dashboard actions.
- Output: HTML/JS static assets and JSON responses from proxied backend calls.

## Current status
- Legacy prototype, superseded (see above).

## Known limitations
- No dedicated automated test suite is present in this service folder.
