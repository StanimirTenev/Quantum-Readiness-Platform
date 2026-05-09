# Inventory Service

## What this service does
- Stores assets, ingested scan events, and related risk records.

## Stage 2 enriched evidence ingest
- `POST /scans/ingest` now accepts optional Stage 2 enriched evidence blocks while remaining backward compatible with existing Stage 1 payloads.
- Optional blocks accepted:
  - `crypto_evidence.package_metadata`
  - `crypto_evidence.cert_indicators.certificate_file_indicators`
  - `crypto_evidence.cert_indicators.config_file_indicators`
  - `tls_metadata` (accepted as alias of `tls_evidence`)
  - `tls_metadata.certificate_chain`
- Minimal validation behavior:
  - missing optional Stage 2 blocks do not fail ingest
  - obvious invalid shapes are rejected (for example non-numeric `tls_metadata.port`, non-array `package_metadata.packages`, non-array `certificate_chain.certificates`)
  - safe defaults are applied when practical (`packages/files/errors/searched_paths/certificates -> []`)

### Sample ingest payload snippet
```json
{
  "source": "network",
  "assets": [{"asset_type": "endpoint", "name": "example.com:443"}],
  "tls_metadata": {
    "target": "example.com",
    "port": 443,
    "protocol_version": "TLS 1.3",
    "certificate_chain": {
      "available": true,
      "certificates": []
    }
  }
}
```

## Main endpoints or functions
- `GET /health`
- `GET/POST/PUT/DELETE /assets` and `/assets/{asset_id}`
- `POST /scans/ingest`, `GET /scans`, `GET /scans/{scan_id}`
- `GET /risks`, `POST /admin/cleanup-assets`

## How to run tests
- `pytest services/inventory-service/tests`


## Stage 2 Evidence Fixtures
- `minimal_ingest.json`: smallest Stage 1-compatible ingest payload used as the baseline success case.
- `host_enriched_ingest.json`: host ingest payload with Stage 2 `crypto_evidence.package_metadata` plus certificate/config file indicator blocks.
- `network_enriched_ingest.json`: network ingest payload with Stage 2 `tls_metadata`, including `certificate` and `certificate_chain.certificates`.
- `invalid_tls_metadata.json`: negative-test fixture with intentionally invalid `tls_metadata.port` shape.
- `invalid_package_metadata.json`: negative-test fixture with intentionally invalid `crypto_evidence.package_metadata.packages` shape.


## Stage 2 Inventory Smoke Validation

Run:

```bash
bash scripts/run_stage2_inventory_smoke.sh
```

Precondition:
- inventory-service is running locally on port 8001.

Output:
- `reports/stage2-inventory-smoke-report.md`
