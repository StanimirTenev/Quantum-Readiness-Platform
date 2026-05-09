# Dependency Graph Projection Plan

## Purpose

This document defines how future dependency graph snapshots will be derived from current QRP outputs across inventory, risk-engine, and planner-service.

This is a projection plan only.

- No graph implementation is included.
- No graph database is introduced.
- No graph service/API is implemented.
- The purpose is to prevent ad hoc graph construction later.

## Relationship to Existing Graph Docs

This plan is aligned with:

- `docs/dependency-graph-design.md`
- `docs/dependency-graph-contract.md`

Relationship between the three documents:

- The design document defines what the graph is for.
- The contract document defines node and edge shapes.
- This document defines how to build graph snapshots from existing system outputs.

## Current Inputs

The following existing QRP outputs are available as projection inputs.

### Inventory Service

Inputs:
- scan ingest responses
- asset records
- stored raw/enriched evidence
- `asset_ids`
- `scan_id`
- source/evidence references if available

Stage 2 evidence:
- `crypto_evidence.package_metadata`
- `crypto_evidence.cert_indicators.certificate_file_indicators`
- `crypto_evidence.cert_indicators.config_file_indicators`
- `tls_metadata`
- `tls_metadata.certificate`
- `tls_metadata.certificate_chain`

### Risk Engine

Inputs:
- `normalized_score_100` / `final_score`
- `rating`
- `stage2_signals.evidence_signals`
- `stage2_adjustment`
- `confidence_score`
- `risk_dimensions`
- rationale/reasons

### Planner Service

Inputs:
- `wave`
- `priority_score`
- `planning_reasons`
- migration task fields if available
- Stage 2 wave cap behavior

## Projection Output

Future graph projection output shape:

```json
{
  "graph_snapshot_id": "string",
  "generated_at": "ISO timestamp",
  "source": "inventory_risk_planner_projection",
  "inputs": {
    "scan_ids": [],
    "risk_run_id": "string|null",
    "planner_run_id": "string|null"
  },
  "nodes": [],
  "edges": [],
  "warnings": []
}
```

Notes:
- `nodes` and `edges` follow `docs/dependency-graph-contract.md`.
- `warnings` capture missing, ambiguous, or low-confidence relationships.
- A graph snapshot can be partial when source evidence is partial.

## Projection Phases

Projection should run in deterministic ordered phases.

### Phase 1 — Asset Projection

From inventory assets:

Create:
- Asset nodes

Use:
- `asset_id`
- `name`
- `asset_type`
- `environment`
- `criticality`
- owner if present

Warnings:
- missing asset name
- missing environment
- missing criticality
- duplicate asset identifiers

### Phase 2 — Host Evidence Projection

From `crypto_evidence.package_metadata`:

Create:
- Package nodes
- Asset `HAS_PACKAGE` Package edges

From `crypto_evidence.cert_indicators.certificate_file_indicators`:

Create:
- CryptoFinding nodes for certificate/key indicators
- optionally ConfigFile nodes when paths are available
- Asset `HAS_FINDING` CryptoFinding edges
- Asset `HAS_CONFIG` ConfigFile edges when file path is present

From `crypto_evidence.cert_indicators.config_file_indicators`:

Create:
- ConfigFile nodes
- Asset `HAS_CONFIG` ConfigFile edges
- CryptoFinding nodes for `tls_config_detected` / `ssh_config_detected` if appropriate

Warnings:
- missing package version
- unreadable config path
- high number of certificate/key indicators
- private key indicator present

### Phase 3 — Network TLS Projection

From `tls_metadata.target` / `port` / `server_name`:

Create:
- Service node
- Asset `RUNS` Service edge if asset relation is known
- warning if asset relation is unknown

From `tls_metadata.certificate`:

Create:
- Certificate node
- Service `USES_CERTIFICATE` Certificate edge

From `tls_metadata.certificate_chain.certificates[]`:

Create:
- Certificate nodes
- Certificate `SIGNED_BY` Certificate edges

Warnings:
- certificate missing fingerprint
- certificate expired or expiring soon
- weak RSA key
- chain unavailable
- chain length mismatch

### Phase 4 — Risk Projection

From risk-engine output:

Create:
- CryptoFinding nodes for evidence-derived signals
- Asset `HAS_FINDING` CryptoFinding edges

Map signals:
- `crypto_packages_detected`
- `certificate_files_detected`
- `private_key_files_detected`
- `tls_config_detected`
- `ssh_config_detected`
- `tls_detected`
- `weak_public_key_detected`
- `expiring_certificate_detected`
- `certificate_chain_available`

Include properties:
- `normalized_score_100`
- `rating`
- `confidence_score`
- `risk_dimensions`
- `stage2_adjustment`
- rationale

Warnings:
- low confidence score
- high urgency dimension
- weak public key signal
- private key indicator signal

### Phase 5 — Planner Projection

From planner-service output:

Create:
- MigrationTask nodes
- Asset `HAS_MIGRATION_TASK` MigrationTask edges

Include properties:
- `wave`
- `priority_score`
- `planning_reasons`
- `no_later_than_wave_2` check if applicable

Warnings:
- high-risk asset not in early wave
- missing planning reasons
- `priority_score` missing
- wave assignment missing

## Deterministic ID Projection Rules

Use ID rules from `docs/dependency-graph-contract.md`.

Concrete examples:

- Asset: `asset:{asset_id}`
- Service: `service:{asset_id}:{protocol}:{port}:{fqdn_or_target}`
- Certificate: `certificate:{fingerprint_sha256}`
- ConfigFile: `config:{asset_id}:{path_hash}`
- Package: `package:{asset_id}:{package_manager}:{package_name}`
- CryptoFinding: `finding:{scan_id}:{finding_type}:{fingerprint_or_hash}`
- MigrationTask: `migration_task:{asset_id}:{wave}:{task_type}`
- Edge: `edge:{from_id}:{edge_type}:{to_id}`

Rules:
- use stable evidence-derived IDs
- hash sensitive file paths where appropriate
- do not use random UUIDs for repeatable projections
- if required identifiers are missing, emit warning and skip or create low-confidence node only if safe

## Confidence Assignment

Confidence mapping rules:

- `1.0`
  - direct scanner evidence with stable identifier
  - certificate fingerprint from TLS scan
  - package name/version from package manager

- `0.8`
  - normalized inventory evidence
  - planner/risk output derived from direct evidence

- `0.6`
  - config file indicator by path/name only
  - certificate/key file indicator without content parsing

- `0.4`
  - manually supplied owner/team metadata
  - weakly linked asset-service relation

- `0.2`
  - incomplete relationship with missing identifiers

Rules:
- never hide low-confidence data
- mark it clearly
- low-confidence edges must not drive critical automation

## Warning Model

Warning object shape:

```json
{
  "code": "string",
  "severity": "info|warning|critical",
  "message": "string",
  "related_node_ids": [],
  "related_edge_ids": [],
  "evidence_ref": "string|null"
}
```

Required warning codes:
- `missing_asset_identity`
- `missing_environment`
- `missing_criticality`
- `missing_certificate_fingerprint`
- `chain_unavailable`
- `weak_public_key`
- `private_key_indicator`
- `low_confidence_relationship`
- `asset_service_link_unknown`
- `high_risk_late_wave`
- `missing_planning_reason`

## Projection Examples

Compact examples for common transformations.

### Example 1 — Host package to graph

Input:
- `crypto_evidence.package_metadata.packages[]`

Output:
- Asset node
- Package node
- `HAS_PACKAGE` edge

### Example 2 — TLS certificate to graph

Input:
- `tls_metadata.certificate`

Output:
- Service node
- Certificate node
- `USES_CERTIFICATE` edge

### Example 3 — Certificate chain to graph

Input:
- `tls_metadata.certificate_chain.certificates[]`

Output:
- Certificate nodes
- `SIGNED_BY` edges

### Example 4 — Risk signal to graph finding

Input:
- `stage2_signals.evidence_signals.private_key_files_detected=true`

Output:
- CryptoFinding node
- `HAS_FINDING` edge
- `private_key_indicator` warning

### Example 5 — Planner result to migration task

Input:
- `priority_score` / `wave` / `planning_reasons`

Output:
- MigrationTask node
- `HAS_MIGRATION_TASK` edge

## Initial Graph Snapshot Build Order

1. Load inventory assets/evidence.
2. Create Asset nodes.
3. Project host evidence nodes/edges.
4. Project network service/certificate nodes/edges.
5. Attach risk findings.
6. Attach migration tasks.
7. Validate node/edge references.
8. Generate warnings.
9. Emit graph snapshot JSON.

## Validation Rules

Validation checks:

- every `edge.from` exists
- every `edge.to` exists
- node IDs unique
- edge IDs unique
- confidence `0.0–1.0`
- required properties present
- no random IDs when deterministic ID is possible
- no graph fact without `evidence_ref`/source
- graph snapshot valid even if partial
- warnings emitted for skipped ambiguous relationships

## Privacy and Local-First Boundary

- graph projection runs inside customer-controlled deployment
- graph data stays local by default
- graph data is sensitive infrastructure intelligence
- external LLMs must not receive graph snapshots unless explicitly configured
- deterministic services must work without LLM
- path-derived IDs should use hashes where needed
- graph export must be deliberate, not automatic

## Future Implementation Tasks

Future tasks (not implemented here):

1. Graph projection module skeleton
2. Graph snapshot JSON generator
3. Graph projection tests using Stage 2 fixtures
4. Graph smoke validation script
5. Optional graph query API design
6. Storage decision: PostgreSQL projection vs graph DB vs hybrid

## Non-Goals

Explicit non-goals for this task:

- no graph implementation in this task
- no graph database dependency
- no graph API endpoints
- no graph traversal engine
- no Neo4j
- no LLM graph reasoning
- no RAG
- no auth/RBAC
- no production deployment
- no autonomous execution
- no Windows agent implementation

## Recommended Next Step

Graph Design Task 4 — Define graph projection validation examples using existing Stage 2 fixtures.
