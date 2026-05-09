# Graph Projection Smoke Report

## Validation Date
2026-05-09T10:03:49Z

## Scope
- Stage 2 host enriched fixture projection
- Stage 2 network enriched fixture projection
- JSON graph snapshot validation

## Inputs

| Fixture | Status |
|---|---|
| /workspace/Quantum-Readiness-Platform/services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json | OK |
| /workspace/Quantum-Readiness-Platform/services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json | OK |

## Snapshot Summary

- graph_snapshot_id: 50eb0ae424cec904
- graph_schema_version: 0.1
- node count: 8
- edge count: 5
- warning count: 3

## Node Types

| Type | Count |
|---|---|
| Asset | 2 |
| Certificate | 2 |
| ConfigFile | 2 |
| Package | 1 |
| Service | 1 |

## Edge Types

| Type | Count |
|---|---|
| HAS_CONFIG | 2 |
| HAS_PACKAGE | 1 |
| SIGNED_BY | 1 |
| USES_CERTIFICATE | 1 |

## Warnings

- low_confidence_relationship: 2
- missing_certificate_fingerprint: 1

## Result

PASS
