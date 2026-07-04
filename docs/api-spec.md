# API Spec

## Inventory
- POST /api/scans/host
- POST /api/scans/network
- POST /api/scans/repo
- GET /api/assets
- GET /api/assets/{id}

## Risk
- GET /api/assets/{id}/risk
- POST /api/scenarios/run

## Copilot
- POST /api/copilot/query
- POST /api/copilot/explain-risk
- POST /api/copilot/generate-wave-plan

## Crypto Fingerprint
- GET /api/algorithms
- POST /api/fingerprint
