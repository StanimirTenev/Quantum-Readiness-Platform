# Graph Projection Smoke Report

## Validation Date
2026-07-08T06:07:22Z

## Scope
- JSON snapshot projection
- Stage 2 fixture-based
- no graph DB
- no graph API

## Inputs

| Fixture | Status |
|---|---|
| services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json | OK |
| services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json | OK |

## Snapshot Summary

- graph_snapshot_id: 07023e0d35e1ee66
- graph_schema_version: 0.1
- projection_version: 0.3.0
- source: stage2_fixture_projection_smoke
- node count: 9
- edge count: 7
- warning count: 3

## Node Types

| Type | Count |
|---|---|
| Asset | 2 |
| Certificate | 2 |
| ConfigFile | 2 |
| CryptoFinding | 1 |
| Package | 1 |
| Service | 1 |

## Edge Types

| Type | Count |
|---|---|
| HAS_CONFIG | 2 |
| HAS_PACKAGE | 1 |
| RUNS | 1 |
| SERVICE_HAS_FINDING | 1 |
| SIGNED_BY | 1 |
| USES_CERTIFICATE | 1 |

## Warning Summary

| Code | Severity | Count |
|---|---:|---:|
| low_confidence_relationship | info | 2 |
| missing_certificate_fingerprint | warning | 1 |

## Evidence Coverage

| Evidence Area | Expected Graph Object | Status |
|---|---|---|
| Host asset | Asset | PASS |
| Host packages | Package + HAS_PACKAGE | PASS |
| Host config indicators | ConfigFile + HAS_CONFIG | PASS |
| Network TLS service | Service | PASS |
| Asset runs service | RUNS | PASS |
| Service vulnerability finding | CryptoFinding + SERVICE_HAS_FINDING | PASS |
| TLS certificate | Certificate + USES_CERTIFICATE | PASS |
| Certificate chain | Certificate + SIGNED_BY | PASS |

## Validation Checks

| Check | Result |
|---|---|
| graph_schema_version exists | PASS |
| graph_snapshot_id exists | PASS |
| nodes array exists | PASS |
| edges array exists | PASS |
| warnings array exists | PASS |
| node IDs unique | PASS |
| edge IDs unique | PASS |
| edge references valid | PASS |
| confidence values within 0.0–1.0 | PASS |

## Privacy Boundary

Graph snapshots may contain sensitive infrastructure intelligence. They remain local by default and must not be sent to external LLM providers unless explicitly configured by the operator.

## Non-Goals

- no graph database
- no graph API
- no graph UI
- no Neo4j
- no Copilot/RAG graph reasoning

## Result

PASS
