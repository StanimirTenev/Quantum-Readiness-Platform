# API Spec

## Inventory
- POST /api/scans/host
- POST /api/scans/network
- POST /api/scans/repo
- GET /api/assets
- GET /api/assets/{id}

## Risk
- GET /api/assets/{id}/risk
- POST /api/scenarios/run  (scenario-engine POST /run)

## Copilot
- POST /api/copilot/query
- POST /api/copilot/explain-risk
- POST /api/copilot/generate-wave-plan

## Crypto Fingerprint
- GET /api/algorithms
- POST /api/fingerprint

## Evidence Normalizer
- POST /api/normalize

## PQC Readiness
- GET /api/readiness-states
- POST /api/pqc-readiness

## Integrations (dry-run only, disabled)
- GET /api/integrations
- POST /api/integrations/dry-run
