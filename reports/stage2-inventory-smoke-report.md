# Stage 2 Inventory Smoke Report

## Validation Date
2026-05-17T06:51:34Z

## Scope
- minimal Stage 1-compatible ingest
- enriched host evidence ingest
- enriched network TLS evidence ingest
- invalid enriched payload rejection

## Fixtures Used

| Fixture | Expected | Result |
|---|---|---|
| minimal_ingest.json | 2xx + scan metadata fields | PASS |
| host_enriched_ingest.json | 2xx + scan metadata fields | PASS |
| network_enriched_ingest.json | 2xx + scan metadata fields | PASS |
| invalid_tls_metadata.json | HTTP 4xx validation failure | HTTP 422 |
| invalid_package_metadata.json | HTTP 4xx validation failure | HTTP 422 |

## Success Responses

- minimal scan_id: db867a16-f945-470f-a926-074c56cab244, created: 1, asset_ids count: 1
- host enriched scan_id: adcb9ba5-a705-4d59-abc4-d83bf55391a1, created: 1, asset_ids count: 1
- network enriched scan_id: 2428083f-ab25-49cb-afe5-a635970d996f, created: 1, asset_ids count: 1

## Invalid Fixture Results

- invalid_tls_metadata.json status: HTTP 422
- invalid_package_metadata.json status: HTTP 422

## Result

PASS
