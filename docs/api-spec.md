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

## Assessment pipeline
- POST /api/assess  (chains crypto-fingerprint -> pqc-readiness -> finding-attribution -> optional risk-engine)

## Finding attribution
- POST /api/attribute  (location + service/application attribution; vulnerability -> location -> service/app -> asset -> certificate/library/pipeline)

## Graph traversal (in-memory over JSON snapshot)
- GET /api/graph/queries
- POST /api/graph/blast-radius
- POST /api/graph/trust-chain
- POST /api/graph/neighbors
- POST /api/graph/evidence-path  (vulnerability -> service/location -> asset -> certificate/library/pipeline)

## Integrations (dry-run only, disabled)
- GET /api/integrations
- POST /api/integrations/dry-run
