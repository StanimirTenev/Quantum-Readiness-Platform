# Stage 2 Inventory Smoke Report

## Validation Date
2026-05-09T04:38:44Z

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

- minimal scan_id: 228ced85-d17a-4861-a1d4-e8db7f8a6350, created: 1, asset_ids count: 1
- host enriched scan_id: ed18f23c-3bcd-4109-b63f-d2c7e5074847, created: 1, asset_ids count: 1
- network enriched scan_id: e3d04587-e675-40ec-b6a8-9597ee81d423, created: 1, asset_ids count: 1

## Invalid Fixture Results

- invalid_tls_metadata.json status: HTTP 422
- invalid_package_metadata.json status: HTTP 422

## Result

PASS
