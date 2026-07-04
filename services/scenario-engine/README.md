# Scenario Engine

## What this service does
- Re-projects asset risk under a chosen quantum-risk scenario by applying the
  scenario multiplier, then re-ranks the assets.
- Scenarios: `public_timeline` (1.00), `early_break` (1.20),
  `hidden_capability` (1.35), `hndl_active_now` (1.40), `partial_break` (1.10),
  `vendor_lag` (1.15), `compliance_pressure` (1.18). Multipliers are aligned
  with the risk-engine so scenario re-scoring stays consistent.

## Current role in the prototype
- Working prototype. Deterministic, local-first, no LLM. Backs the API Gateway
  `POST /api/scenarios/run` route.

## Main endpoints
- `GET /health`
- `GET /scenarios` — scenario-to-multiplier mapping.
- `POST /run` — apply a scenario to a set of assets and return re-ranked results.

## Inputs / outputs

`POST /run`:

```json
{
  "scenario": "hidden_capability",
  "assets": [
    {"asset_name": "payments-api", "base_score": 3.2},
    {"asset_name": "backup-store", "base_score": 2.1}
  ]
}
```

returns, sorted by `normalized_score_100` descending:

```json
{
  "scenario": "hidden_capability",
  "scenario_multiplier": 1.35,
  "asset_count": 2,
  "highest_rating": "critical",
  "results": [
    {
      "asset_name": "payments-api",
      "base_score": 3.2,
      "scenario": "hidden_capability",
      "scenario_multiplier": 1.35,
      "final_score": 4.32,
      "normalized_score_100": 86.4,
      "rating": "critical"
    }
  ]
}
```

- `base_score` is the pre-scenario risk score in the 0-5 range.
- `final_score = base_score * scenario_multiplier`.
- `normalized_score_100 = min(final_score / 5 * 100, 100)`.
- `rating`: `critical` (>=80), `high` (>=60), `medium` (>=40), `low` (>=20), else `minimal`.
- An unknown scenario returns HTTP 422.

## Run locally

```bash
cd services/scenario-engine
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --port 8006
```

## Tests

```bash
cd services/scenario-engine
PYTHONPATH=. pytest -q
```

## Known limitations
- Consumes a pre-computed `base_score`; it does not recompute base risk factors
  (that remains the risk-engine's responsibility).
- Stateless: it does not persist scenario runs.
