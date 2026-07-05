# PQC Readiness Engine

Deterministic transitional classification of an asset/service into where it sits
in the post-quantum migration (architecture &sect;6.2). It is the bridge between
`crypto-fingerprint-service` (which *identifies* algorithms) and `risk-engine`
(which *evaluates* risk): this engine *classifies migration state*, it does not
score risk.

## Readiness states
- `classical_only` — only classical quantum-vulnerable algorithms; no PQC in the current config.
- `hybrid_capable` — can operate in hybrid mode (classical + PQC); a transitional state.
- `pqc_ready` — configured for post-quantum algorithms.
- `vendor_blocked` — migration blocked because a vendor does not ship a PQC-capable version.
- `unknown` — insufficient public-key evidence to classify.

## Main endpoints
- `GET /health`
- `GET /readiness-states` — the five states with descriptions.
- `POST /classify` — classify one asset from its fingerprint findings.

## Inputs / outputs

`POST /classify`:

```json
{
  "asset_name": "payments-api",
  "findings": [ { "classification": "classical_vulnerable", "harvest_now_decrypt_later": true } ],
  "vendor_blocked": false,
  "hybrid_supported": false
}
```

returns:

```json
{
  "contract_version": "pqr-v1",
  "asset_name": "payments-api",
  "readiness": "classical_only",
  "confidence": "high",
  "signals": {
    "classical_vulnerable_present": true,
    "pqc_present": false,
    "vendor_blocked": false,
    "hybrid_supported": false,
    "hndl_exposure": true,
    "weak_key_present": false,
    "finding_count": 1
  },
  "reasons": ["Only classical quantum-vulnerable algorithms are present.", "Recorded traffic is exposed to harvest-now-decrypt-later."]
}
```

`findings` are the findings returned by `crypto-fingerprint-service` (only the
`classification` and optional `harvest_now_decrypt_later` / `weak_key` flags are
read), so the engine stays decoupled from the fingerprint model version.

### Classification rules (deterministic)
1. `vendor_blocked` wins over everything.
2. No classical/PQC public-key findings → `unknown`.
3. classical **and** PQC present → `hybrid_capable` (actively hybrid).
4. PQC only → `pqc_ready`.
5. classical only → `hybrid_capable` if `hybrid_supported` else `classical_only`.

## Run locally

```bash
cd services/pqc-readiness-service
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --port 8012
```

## Tests

```bash
cd services/pqc-readiness-service
PYTHONPATH=. pytest -q
```

## Known limitations
- Classifies a single asset per request from supplied findings; it does not fetch
  evidence itself. A caller (or a future gateway aggregation) chains
  fingerprint &rarr; readiness.
- Backs the API Gateway `GET /api/readiness-states` and `POST /api/pqc-readiness`.
