# New Services Smoke Report

Generated: 2026-07-05 08:15:52Z

Scope: crypto-fingerprint-service, evidence-normalizer, scenario-engine,
integration-service (dry-run), web-ui gateway routes -- exercised through api-gateway.

| Check | Result |
| --- | --- |
| gateway health | PASS |
| GET /api/algorithms lists known families | PASS |
| POST /api/fingerprint classical+pqc mix is hybrid_partial | PASS |
| POST /api/fingerprint flags weak RSA key as critical | PASS |
| POST /api/normalize canonicalizes nested certificate | PASS |
| POST /api/normalize extracts host packages | PASS |
| POST /api/scenarios/run applies multiplier and ranks | PASS |
| POST /api/assess chains fingerprint -> pqc-readiness | PASS |
| POST /api/assess includes risk when risk_factors given | PASS |
| GET /api/readiness-states lists five states | PASS |
| POST /api/pqc-readiness classifies classical-only | PASS |
| POST /api/pqc-readiness classifies hybrid and vendor_blocked | PASS |
| GET /api/graph/queries lists traversal queries | PASS |
| POST /api/graph/blast-radius reaches the dependent asset | PASS |
| POST /api/graph/trust-chain follows SIGNED_BY to root | PASS |
| GET /api/integrations reports everything disabled | PASS |
| POST /api/integrations/dry-run never executes when approved | PASS |
| POST /api/integrations/dry-run rejects secret material | PASS |

Result: PASS
