# Dependency Graph Design

## Purpose

The dependency graph is the next major Quantum Readiness Platform (QRP) differentiator. It is intended to make relationship-aware reasoning first-class across evidence, risk, and planning.

It should help answer:
- why an asset is high priority
- what depends on what
- where cryptographic exposure exists
- which services/certificates/configs/packages are related
- what the blast radius of a risky asset might be
- which migration tasks should be sequenced earlier or later

This is a design document only. No graph implementation is included yet.

## Current Project Context

Current state summary:
- Stage 1 Core Stabilization is closed.
- Stage 2 enriched evidence layer is frozen.
- Stage 3 risk/planning improvement layer is frozen.

Current proven flow:
- enriched evidence
- → inventory ingest
- → risk scoring with `confidence_score` and `risk_dimensions`
- → planner `priority_score` and wave rationale

## Why Graph Is Needed

Current limitations without a graph layer:
- planner cannot reason about dependencies
- risk score is asset-centric
- no blast radius reasoning
- no relationship model between certificates, services, configs, packages and owners
- migration sequencing is still conservative but not topology-aware

## Graph Design Principles

- deterministic core first
- graph is derived from evidence, not guessed
- no LLM-generated graph facts without evidence
- local/internal deployment
- Evidence stays local
- external LLM not required
- graph must support explainable reasoning
- missing relationships must be represented as unknown, not invented
- initial graph should be small and useful, not complete and complex

## Initial Node Types

### Asset
Represents a host, server, VM, container host, appliance or logical system.

Fields:
- id
- name
- asset_type
- environment
- criticality
- owner
- source
- confidence

### Service
Represents a network/service endpoint or workload.

Fields:
- id
- name
- protocol
- port
- fqdn
- exposure_type
- asset_id
- confidence

### Certificate
Represents a TLS/certificate finding.

Fields:
- id
- subject
- issuer
- not_before
- not_after
- signature_algorithm
- public_key_algorithm
- public_key_size
- fingerprint_sha256
- source
- confidence

### ConfigFile
Represents SSH/TLS/VPN/keystore config indicators.

Fields:
- id
- path
- config_type
- readable
- source
- confidence

### Package
Represents relevant crypto/security package metadata.

Fields:
- id
- name
- version
- package_manager
- source
- confidence

### CryptoFinding
Represents derived crypto evidence or risk-relevant crypto signal.

Fields:
- id
- finding_type
- algorithm
- severity
- evidence_ref
- source
- confidence

### Owner
Represents team/person/system owner if known.

Fields:
- id
- name
- owner_type
- contact
- confidence

### MigrationTask
Represents migration/remediation task candidate.

Fields:
- id
- task_type
- wave
- status
- priority_score
- reason
- confidence

## Later Node Types

Future node types (not now):
- Repo
- Pipeline
- BackupSet
- VendorProduct
- CA
- KMS/HSM
- CloudAccount
- Application
- BusinessProcess
- Document
- PolicyRule

## Initial Edge Types

### Asset RUNS Service
Asset → Service

Meaning:
The asset exposes or runs the service.

### Service USES Certificate
Service → Certificate

Meaning:
The service appears to use the certificate.

### Asset HAS_CONFIG ConfigFile
Asset → ConfigFile

Meaning:
The asset has a relevant config indicator.

### Asset HAS_PACKAGE Package
Asset → Package

Meaning:
The asset has a relevant crypto/security package.

### Certificate SIGNED_BY Certificate
Certificate → Certificate

Meaning:
Certificate chain relationship where one certificate is issued by another.

### Asset HAS_FINDING CryptoFinding
Asset → CryptoFinding

Meaning:
Risk-relevant crypto evidence was found on the asset.

### Service HAS_FINDING CryptoFinding
Service → CryptoFinding

Meaning:
Risk-relevant crypto evidence was found on the service.

### Asset OWNED_BY Owner
Asset → Owner

Meaning:
The asset has a known owner.

### Asset HAS_MIGRATION_TASK MigrationTask
Asset → MigrationTask

Meaning:
The asset has a proposed or active migration task.

## Later Edge Types

Future edge types (not now):
- DEPENDS_ON
- COMMUNICATES_WITH
- DEPLOYED_FROM
- PROTECTS
- BLOCKED_BY_VENDOR
- FEEDS_PIPELINE
- USES_KMS
- STORES_LONG_TERM_DATA
- REFERENCES_DOCUMENT
- VIOLATES_POLICY

## Evidence Mapping

Current Stage 2 evidence mapped into graph objects.

| Evidence Source | Current Field | Graph Node / Edge | Notes |
|---|---|---|---|
| linux-host-agent | `crypto_evidence.package_metadata` | `Package`, `Asset HAS_PACKAGE Package` | Package manager + crypto/security package list project into package nodes and ownership edge. |
| linux-host-agent | `crypto_evidence.cert_indicators.certificate_file_indicators` | `ConfigFile` or `CryptoFinding` | Can be represented as file indicator config objects or finding records depending on certainty and parse depth. |
| linux-host-agent | `crypto_evidence.cert_indicators.config_file_indicators` | `ConfigFile`, `Asset HAS_CONFIG ConfigFile` | Direct config indicator projection on asset. |
| network-scanner | `tls_metadata.certificate` | `Certificate` | Leaf/service certificate node with algorithm + validity metadata. |
| network-scanner | `tls_metadata.certificate_chain` | `Certificate SIGNED_BY Certificate` | Chain links become directed certificate issuer relationships. |
| network-scanner | `tls_metadata.target` / `port` / `server_name` | `Service` | Service endpoint identity and network attributes. |
| network-scanner | `tls_metadata.protocol_version` / `cipher_suite` | `CryptoFinding` or `Service` properties | Weak protocol/cipher can become finding; stable endpoint attrs may remain service properties. |
| inventory-service | asset metadata | `Asset` | Canonical asset identity/metadata projection. |
| inventory-service | `scan_id` / evidence refs | `source` / `evidence_ref` | Traceability fields retained on nodes/findings/edges for explainability. |
| risk-engine | `risk_dimensions` | properties on risk snapshot / future `RiskScore` node | Keep now as attached properties; future dedicated score node possible. |
| risk-engine | `stage2_signals` | `CryptoFinding` candidates | Signals can be transformed into typed findings with confidence. |
| planner-service | `priority_score` / `wave` | `MigrationTask` | Planner outputs project as graph task nodes linked to assets. |

## Initial Queries

Useful first graph queries:

1. Show all high-risk assets with certificates using RSA keys.
2. Show services using certificates expiring in the next 90 days.
3. Show assets with private key indicators.
4. Show assets with TLS config indicators but no certificate metadata.
5. Show all assets owned by a team with wave_1 migration tasks.
6. Show certificate chain for a given service.
7. Show assets with weak public keys and production environment.
8. Show evidence path explaining why an asset is high priority.

## Blast Radius Concept

Early blast radius (without full dependency model) can be estimated from:
- number of services on an asset
- number of certificates attached to services
- number of findings
- environment
- criticality
- owner grouping if available

This is not a full dependency graph yet. It is an evidence relationship graph.

## Graph Confidence Model

Confidence levels per node/edge:
- 1.0 direct scanner evidence
- 0.8 normalized evidence
- 0.6 inferred from config indicator
- 0.4 user/manual metadata
- 0.2 weak or incomplete evidence

Rules:
- Never hide low-confidence relationships.
- Mark them clearly.
- Do not let low-confidence inferred relationships drive critical automation.

## Privacy / Deployment Boundary

- graph data is sensitive infrastructure intelligence
- graph must run inside customer-controlled deployment
- graph data must not leave the deployment boundary by default
- external LLM must not receive graph data unless explicitly configured
- deterministic services must work without LLM

## Storage Options

### Option A — PostgreSQL tables
Pros:
- simpler
- already aligned with relational data
- easier local deployment

Cons:
- graph traversal less natural

### Option B — Neo4j / graph DB
Pros:
- natural graph traversal
- good for blast radius queries

Cons:
- new dependency
- heavier deployment

### Option C — Hybrid
Pros:
- keep canonical records in PostgreSQL
- derive graph projection later

Cons:
- more moving parts

Recommended for current stage:
Design for graph model now, but implement later.
Do not add graph DB yet.

## API Design Sketch

Design only, no implementation.

Potential future endpoints:
- `GET /graph/assets/{asset_id}`
- `GET /graph/assets/{asset_id}/neighbors`
- `GET /graph/assets/{asset_id}/evidence-path`
- `GET /graph/certificates/{fingerprint_sha256}/chain`
- `GET /graph/queries/high-risk-services`
- `GET /graph/queries/blast-radius/{asset_id}`

## Stage 4 Implementation Plan — Future

Future implementation breakdown:
1. Graph model contract document
2. Graph projection from inventory evidence
3. Graph query API skeleton
4. Certificate/service graph projection
5. Asset/package/config graph projection
6. Risk/planner graph enrichment
7. Graph smoke validation

Do not implement these now.

## Non-Goals

- no graph implementation in this task
- no graph database dependency
- no LLM graph reasoning
- no RAG
- no production auth/RBAC
- no cloud integrations
- no autonomous execution
- no Windows agent implementation

## Recommended Next Step

Graph Design Task 2 — Define graph model contract and JSON schema examples.
