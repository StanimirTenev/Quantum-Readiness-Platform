# Stage 2 Inventory Smoke Report

## Validation Date
2026-05-16T03:59:55Z

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

- minimal scan_id: def82829-02de-490e-a856-729540fcb4bc, created: 1, asset_ids count: 1
- host enriched scan_id: 9adc8e5a-6641-4356-b228-03ec697d5695, created: 1, asset_ids count: 1
- network enriched scan_id: 95875cfb-73ff-4140-9abf-6e973a743e2a, created: 1, asset_ids count: 1

## Invalid Fixture Results

- invalid_tls_metadata.json status: HTTP 422
- invalid_package_metadata.json status: HTTP 422

## Result

PASS
