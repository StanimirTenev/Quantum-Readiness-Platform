# New Services Smoke Report

Generated: 2026-07-04 15:09:21Z

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
| GET /api/integrations reports everything disabled | PASS |
| POST /api/integrations/dry-run never executes when approved | PASS |
| POST /api/integrations/dry-run rejects secret material | PASS |

Result: PASS
