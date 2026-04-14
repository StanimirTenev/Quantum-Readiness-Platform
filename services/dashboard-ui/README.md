# Dashboard UI Service

## What this service does
- Serves the static dashboard and proxies UI API calls to backend services.

## Current role in the prototype
- Working prototype frontend gateway for demo and evaluator review flows.

## Main endpoints or functions
- `GET /` and `/static/*` for UI assets
- `GET /api/{health|summary|operational-summary|plan|tasks|approvals|asset}`
- `POST /api/{search|export-tasks|copilot-query}`

## Inputs / outputs
- Input: browser HTTP requests and JSON payloads from dashboard actions.
- Output: HTML/JS static assets and JSON responses from proxied backend calls.

## Current status
- Working prototype service.

## Known limitations
- No dedicated automated test suite is present in this service folder.
