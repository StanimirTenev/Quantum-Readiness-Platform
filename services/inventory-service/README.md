# Inventory Service

## What this service does
- Stores assets, ingested scan events, and related risk records.

## Current role in the prototype
- Working prototype data backbone for inventory and scan ingestion.

## Main endpoints or functions
- `GET /health`
- `GET/POST/PUT/DELETE /assets` and `/assets/{asset_id}`
- `POST /scans/ingest`, `GET /scans`, `GET /scans/{scan_id}`
- `GET /risks`, `POST /admin/cleanup-assets`

## Inputs / outputs
- Input: structured asset and scan-ingest JSON payloads.
- Output: JSON records for assets, scans, and calculated risk snapshots.

## Current status
- Working prototype service.

## How to run tests
- `pytest services/inventory-service/tests`

## Known limitations
- Risk scoring is currently triggered through fixed mapping logic and configured upstream client calls.
