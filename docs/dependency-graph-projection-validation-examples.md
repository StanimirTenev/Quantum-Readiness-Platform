# Dependency Graph Projection Validation Examples

## Purpose

This document provides concrete examples of how existing Stage 2 evidence fixtures should project into future graph snapshot nodes, edges, and warnings.

This is not implementation.
No graph database is introduced.
No graph service/API is implemented.
These examples are intended to guide future graph projection tests.

## Relationship to Previous Graph Docs

This document complements:

- `docs/dependency-graph-design.md`
- `docs/dependency-graph-contract.md`
- `docs/dependency-graph-projection-plan.md`

Relationship:

- The design document defines graph purpose.
- The contract document defines node/edge shapes.
- The projection plan defines transformation phases.
- This document defines validation examples using current fixtures.

## Source Fixtures

| Fixture | Purpose |
|---|---|
| `minimal_ingest.json` | smallest valid Stage 1-compatible ingest payload |
| `host_enriched_ingest.json` | enriched host crypto/package/config evidence |
| `network_enriched_ingest.json` | enriched network TLS/certificate evidence |

Fixture paths:

- `services/inventory-service/tests/fixtures/stage2_evidence/minimal_ingest.json`
- `services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json`
- `services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json`

## Validation Example 1 — Minimal Ingest Projection

Input:
`minimal_ingest.json`

Expected graph behavior:

- creates at least one `Asset` node if asset identity exists
- no `Package` nodes required
- no `ConfigFile` nodes required
- no `Certificate` nodes required
- no `Service` nodes required unless service/endpoint evidence exists
- warnings should be emitted for missing optional relationship data only if relevant

Expected nodes:

- `Asset`

Expected edges:

- none or minimal evidence-backed edges only

Expected warnings:

- `missing_environment` if environment missing
- `missing_criticality` if criticality missing
- no warning for absent Stage 2 evidence

Compact example JSON:

```json
{
  "nodes": [
    {"id": "asset:sha256:3f3d...", "kind": "Asset", "name": "example-host"}
  ],
  "edges": [],
  "warnings": [
    {"code": "missing_environment", "severity": "info"},
    {"code": "missing_criticality", "severity": "info"}
  ]
}
```

## Validation Example 2 — Host Package Evidence Projection

Input:
`host_enriched_ingest.json`

From:
`crypto_evidence.package_metadata.packages[]`

Expected nodes:

- `Asset`
- `Package` nodes

Expected edges:

- `Asset HAS_PACKAGE Package`

Required checks:

- package node id is deterministic
- edge id is deterministic
- `package_manager` is preserved
- `version` is preserved if present
- confidence is high for package-manager-derived evidence

Compact example JSON:

```json
{
  "nodes": [
    {"id": "asset:sha256:3f3d...", "kind": "Asset", "name": "host-a"},
    {"id": "pkg:sha256:19af...", "kind": "Package", "name": "openssl", "version": "3.0.2", "package_manager": "dpkg"}
  ],
  "edges": [
    {"id": "edge:sha256:cf61...", "kind": "HAS_PACKAGE", "from": "asset:sha256:3f3d...", "to": "pkg:sha256:19af...", "confidence": 0.95}
  ]
}
```

## Validation Example 3 — Host Certificate File Indicator Projection

Input:
`host_enriched_ingest.json`

From:
`crypto_evidence.cert_indicators.certificate_file_indicators`

Expected nodes:

- `Asset`
- `ConfigFile` nodes when file paths are present
- `CryptoFinding` nodes for certificate/key indicators

Expected edges:

- `Asset HAS_CONFIG ConfigFile`
- `Asset HAS_FINDING CryptoFinding`

Expected warnings:

- `private_key_indicator` if key count > 0
- `low_confidence_relationship` for path/name-only indicators if appropriate

Compact example JSON:

```json
{
  "nodes": [
    {"id": "asset:sha256:3f3d...", "kind": "Asset"},
    {"id": "cfg:sha256:6a2d...", "kind": "ConfigFile", "path": "/etc/ssl/private/server.key"},
    {"id": "finding:sha256:ab81...", "kind": "CryptoFinding", "signal": "private_key_files_detected"}
  ],
  "edges": [
    {"id": "edge:sha256:c19e...", "kind": "HAS_CONFIG", "from": "asset:sha256:3f3d...", "to": "cfg:sha256:6a2d...", "confidence": 0.6},
    {"id": "edge:sha256:1da0...", "kind": "HAS_FINDING", "from": "asset:sha256:3f3d...", "to": "finding:sha256:ab81...", "confidence": 0.9}
  ],
  "warnings": [
    {"code": "private_key_indicator", "severity": "high"},
    {"code": "low_confidence_relationship", "severity": "medium"}
  ]
}
```

## Validation Example 4 — Host Config Indicator Projection

Input:
`host_enriched_ingest.json`

From:
`crypto_evidence.cert_indicators.config_file_indicators`

Expected nodes:

- `ConfigFile` nodes for SSH/TLS/VPN/keystore config indicators
- `CryptoFinding` nodes for `tls_config_detected` or `ssh_config_detected` if appropriate

Expected edges:

- `Asset HAS_CONFIG ConfigFile`
- `Asset HAS_FINDING CryptoFinding` if a risk-relevant signal is derived

Expected warnings:

- unreadable config path if `readable=false`
- `low_confidence_relationship` for indicator-only links

Compact example JSON:

```json
{
  "nodes": [
    {"id": "cfg:sha256:8c0a...", "kind": "ConfigFile", "path": "/etc/ssh/sshd_config", "readable": false},
    {"id": "finding:sha256:7bd5...", "kind": "CryptoFinding", "signal": "ssh_config_detected"}
  ],
  "edges": [
    {"id": "edge:sha256:02e0...", "kind": "HAS_CONFIG", "from": "asset:sha256:3f3d...", "to": "cfg:sha256:8c0a...", "confidence": 0.65}
  ],
  "warnings": [
    {"code": "unreadable_config_path", "severity": "medium"},
    {"code": "low_confidence_relationship", "severity": "medium"}
  ]
}
```

## Validation Example 5 — Network TLS Certificate Projection

Input:
`network_enriched_ingest.json`

From:
`tls_metadata.target`
`tls_metadata.port`
`tls_metadata.server_name`
`tls_metadata.certificate`

Expected nodes:

- `Asset` if asset identity is known
- `Service`
- `Certificate`

Expected edges:

- `Asset RUNS Service` if asset-service relation is known
- `Service USES_CERTIFICATE Certificate`

Expected warnings:

- `asset_service_link_unknown` if service cannot be linked to an asset
- `weak_public_key` if RSA key size is weak
- `missing_certificate_fingerprint` if fingerprint is missing

Compact example JSON:

```json
{
  "nodes": [
    {"id": "service:sha256:4be2...", "kind": "Service", "endpoint": "api.example.internal:443", "server_name": "api.example.internal"},
    {"id": "cert:sha256:fed1...", "kind": "Certificate", "subject": "CN=api.example.internal", "public_key_bits": 1024}
  ],
  "edges": [
    {"id": "edge:sha256:0a2c...", "kind": "USES_CERTIFICATE", "from": "service:sha256:4be2...", "to": "cert:sha256:fed1...", "confidence": 0.95}
  ],
  "warnings": [
    {"code": "asset_service_link_unknown", "severity": "medium"},
    {"code": "weak_public_key", "severity": "high"}
  ]
}
```

## Validation Example 6 — Certificate Chain Projection

Input:
`network_enriched_ingest.json`

From:
`tls_metadata.certificate_chain.certificates[]`

Expected nodes:

- `Certificate` nodes for each chain certificate

Expected edges:

- `Certificate SIGNED_BY Certificate`

Required checks:

- `certificate_chain.certificates[0]` is normally the leaf
- each certificate fingerprint becomes deterministic certificate id
- edge direction represents issued-by relation

Expected warnings:

- `chain_unavailable` if `certificate_chain.available=false`
- chain length mismatch if declared length differs from certificates array length

Compact example JSON:

```json
{
  "nodes": [
    {"id": "cert:sha256:leaf...", "kind": "Certificate", "fingerprint": "AA:BB"},
    {"id": "cert:sha256:intermediate...", "kind": "Certificate", "fingerprint": "CC:DD"}
  ],
  "edges": [
    {"id": "edge:sha256:3a66...", "kind": "SIGNED_BY", "from": "cert:sha256:leaf...", "to": "cert:sha256:intermediate...", "confidence": 0.9}
  ],
  "warnings": []
}
```

## Validation Example 7 — Risk Signal Projection

Input:
risk-engine output derived from Stage 2 enriched evidence

From:
`stage2_signals.evidence_signals`

Expected nodes:

- `CryptoFinding` nodes

Expected edges:

- `Asset HAS_FINDING CryptoFinding`
- `Service HAS_FINDING CryptoFinding` if service context exists

Signals to cover:

- `private_key_files_detected`
- `weak_public_key_detected`
- `expiring_certificate_detected`
- `tls_detected`
- `certificate_chain_available`

Expected warnings:

- `private_key_indicator`
- `weak_public_key`
- `low_confidence_relationship` if context is incomplete

Compact example JSON:

```json
{
  "nodes": [
    {"id": "finding:sha256:pk...", "kind": "CryptoFinding", "signal": "private_key_files_detected"},
    {"id": "finding:sha256:wk...", "kind": "CryptoFinding", "signal": "weak_public_key_detected"}
  ],
  "edges": [
    {"id": "edge:sha256:2d33...", "kind": "HAS_FINDING", "from": "asset:sha256:3f3d...", "to": "finding:sha256:pk...", "confidence": 0.92},
    {"id": "edge:sha256:4f0c...", "kind": "HAS_FINDING", "from": "service:sha256:4be2...", "to": "finding:sha256:wk...", "confidence": 0.75}
  ],
  "warnings": [
    {"code": "private_key_indicator", "severity": "high"},
    {"code": "weak_public_key", "severity": "high"}
  ]
}
```

## Validation Example 8 — Planner Migration Task Projection

Input:
planner-service output from Stage 3

From:
`wave`
`priority_score`
`planning_reasons`

Expected nodes:

- `MigrationTask`

Expected edges:

- `Asset HAS_MIGRATION_TASK MigrationTask`

Required checks:

- `priority_score` is preserved
- `wave` is preserved
- `planning_reasons` are preserved
- weak_public_key/private_key wave cap reason is preserved if present

Expected warnings:

- `high_risk_late_wave` if high-risk item is placed too late
- `missing_planning_reason` if reasons absent

Compact example JSON:

```json
{
  "nodes": [
    {"id": "task:sha256:9f11...", "kind": "MigrationTask", "wave": 2, "priority_score": 0.88, "planning_reasons": ["weak_public_key wave cap"]}
  ],
  "edges": [
    {"id": "edge:sha256:b7de...", "kind": "HAS_MIGRATION_TASK", "from": "asset:sha256:3f3d...", "to": "task:sha256:9f11...", "confidence": 1.0}
  ],
  "warnings": []
}
```

## Expected Graph Snapshot Example

```json
{
  "graph_snapshot_id": "snapshot:sha256:2026-05-09:example-01",
  "nodes": [
    {"id": "asset:sha256:3f3d...", "kind": "Asset", "name": "host-a"},
    {"id": "service:sha256:4be2...", "kind": "Service", "endpoint": "api.example.internal:443"},
    {"id": "cert:sha256:fed1...", "kind": "Certificate", "subject": "CN=api.example.internal"},
    {"id": "pkg:sha256:19af...", "kind": "Package", "name": "openssl", "version": "3.0.2"},
    {"id": "cfg:sha256:8c0a...", "kind": "ConfigFile", "path": "/etc/ssh/sshd_config"},
    {"id": "finding:sha256:ab81...", "kind": "CryptoFinding", "signal": "weak_public_key_detected"},
    {"id": "task:sha256:9f11...", "kind": "MigrationTask", "wave": 1, "priority_score": 0.95}
  ],
  "edges": [
    {"id": "e1", "kind": "RUNS", "from": "asset:sha256:3f3d...", "to": "service:sha256:4be2...", "confidence": 0.8},
    {"id": "e2", "kind": "USES_CERTIFICATE", "from": "service:sha256:4be2...", "to": "cert:sha256:fed1...", "confidence": 0.95},
    {"id": "e3", "kind": "HAS_PACKAGE", "from": "asset:sha256:3f3d...", "to": "pkg:sha256:19af...", "confidence": 0.95},
    {"id": "e4", "kind": "HAS_CONFIG", "from": "asset:sha256:3f3d...", "to": "cfg:sha256:8c0a...", "confidence": 0.7},
    {"id": "e5", "kind": "HAS_FINDING", "from": "asset:sha256:3f3d...", "to": "finding:sha256:ab81...", "confidence": 0.9},
    {"id": "e6", "kind": "HAS_MIGRATION_TASK", "from": "asset:sha256:3f3d...", "to": "task:sha256:9f11...", "confidence": 1.0}
  ],
  "warnings": [
    {"code": "weak_public_key", "severity": "high"}
  ]
}
```

## Validation Checklist for Future Projection Tests

- snapshot has `graph_snapshot_id`
- `nodes` array exists
- `edges` array exists
- `warnings` array exists
- node IDs are unique
- edge IDs are unique
- every `edge.from` exists in `nodes`
- every `edge.to` exists in `nodes`
- confidence values are `0.0–1.0`
- package evidence creates `Package` nodes
- TLS certificate evidence creates `Certificate` nodes
- certificate chain creates `SIGNED_BY` edges
- private key signal creates `CryptoFinding` and warning
- planner output creates `MigrationTask` node
- no random UUIDs when deterministic IDs are possible
- sensitive path-derived IDs are hashed
- graph snapshot remains valid if partial

## Privacy / Local-First Boundary

- examples may include hostnames, file paths, certificate metadata, and owner names
- these are sensitive infrastructure intelligence
- graph snapshots must remain inside customer-controlled deployment by default
- external LLM providers must not receive graph snapshots unless explicitly configured
- deterministic graph projection must work without LLM

## Non-Goals

- no graph implementation in this task
- no graph database dependency
- no graph API endpoint
- no graph traversal engine
- no Neo4j
- no LLM graph reasoning
- no RAG
- no auth/RBAC
- no production deployment
- no autonomous execution
- no Windows agent implementation

## Recommended Next Step

Graph Design Task 5 — Decide minimal graph implementation boundary and storage approach.
