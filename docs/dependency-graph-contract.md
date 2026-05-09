# Dependency Graph Contract

## Purpose

This document defines the future dependency graph data contract for QRP before any graph-layer implementation is started.

This is a contract-only specification and **not** an implementation.

- No graph database is introduced.
- No graph service or graph API is implemented.
- No graph traversal logic is implemented.
- The purpose is to prevent inconsistent node and edge shapes in future implementation phases.

## Relationship to Dependency Graph Design

This contract builds on `docs/dependency-graph-design.md` and translates that design into concrete node and edge contracts plus JSON examples.

The design document explains graph intent and scope; this contract defines the exact data shape expected by a future graph projection layer.

## Contract Principles

- Use stable deterministic IDs.
- Every node and edge must be evidence-backed or explicitly marked as inferred.
- No LLM-generated graph facts without evidence.
- graph data stays local by default.
- External LLMs must not receive graph data unless explicitly configured.
- Deterministic core behavior must work without LLM.
- Missing relationships are unknown, not invented.
- Low-confidence relationships remain visible but explicitly marked.
- Graph contract changes should remain backward-compatible where possible.

## Common Fields

Every graph node uses this common shape:

```json
{
  "id": "string",
  "type": "string",
  "label": "string",
  "source": "string",
  "scan_id": "string|null",
  "evidence_ref": "string|null",
  "confidence": 0.0,
  "observed_at": "ISO timestamp|null",
  "properties": {}
}
```

Every graph edge uses this common shape:

```json
{
  "id": "string",
  "type": "string",
  "from": "node id",
  "to": "node id",
  "source": "string",
  "scan_id": "string|null",
  "evidence_ref": "string|null",
  "confidence": 0.0,
  "observed_at": "ISO timestamp|null",
  "properties": {}
}
```

## Deterministic ID Rules

### Canonical ID patterns

- Asset: `asset:{asset_id}`
- Service: `service:{asset_id}:{protocol}:{port}:{fqdn_or_target}`
- Certificate: `certificate:{fingerprint_sha256}`
- ConfigFile: `config:{asset_id}:{path_hash}`
- Package: `package:{asset_id}:{package_manager}:{package_name}`
- CryptoFinding: `finding:{scan_id}:{finding_type}:{fingerprint_or_hash}`
- Owner: `owner:{owner_type}:{normalized_owner_name}`
- MigrationTask: `migration_task:{asset_id}:{wave}:{task_type}`
- Edge: `edge:{from_id}:{edge_type}:{to_id}`

### Rules

- IDs must be stable across repeated scans where evidence is unchanged.
- If a natural unique value exists, use it.
- If sensitive values are used, hash them where appropriate.
- Do not use random UUIDs for deterministic graph projection unless no stable evidence exists.

## Node Contracts

### Asset Node

**Required properties**
- `name`
- `asset_type`
- `environment`
- `criticality`

**Optional properties**
- `owner`
- `lifecycle_years`
- `vendor`
- `tags`

**Confidence notes**
- Typically high confidence when sourced from normalized inventory assets.
- Lower confidence only when inferred from partial network-only evidence.

**Example JSON**

```json
{
  "id": "asset:host-001",
  "type": "Asset",
  "label": "payments-api-prod-01",
  "source": "inventory_ingest",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "assets[0]",
  "confidence": 0.99,
  "observed_at": "2026-05-09T11:20:00Z",
  "properties": {
    "name": "payments-api-prod-01",
    "asset_type": "vm",
    "environment": "prod",
    "criticality": "high",
    "owner": "payments-platform",
    "lifecycle_years": 4,
    "vendor": "acme-cloud",
    "tags": ["pci", "linux"]
  }
}
```

### Service Node

**Required properties**
- `protocol`
- `port`
- `target` or `fqdn`
- `asset_id` if known

**Optional properties**
- `exposure_type`
- `server_name`
- `tls_detected`

**Confidence notes**
- Confidence depends on scan handshake completeness and target resolution reliability.

**Example JSON**

```json
{
  "id": "service:host-001:tcp:443:payments.example.internal",
  "type": "Service",
  "label": "tcp/443 payments.example.internal",
  "source": "network_scan",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "tls_metadata.target",
  "confidence": 0.96,
  "observed_at": "2026-05-09T11:21:00Z",
  "properties": {
    "protocol": "tcp",
    "port": 443,
    "fqdn": "payments.example.internal",
    "asset_id": "host-001",
    "exposure_type": "internal",
    "server_name": "payments.example.internal",
    "tls_detected": true
  }
}
```

### Certificate Node

**Required properties**
- `fingerprint_sha256`
- `subject`
- `issuer`

**Optional properties**
- `not_before`
- `not_after`
- `signature_algorithm`
- `public_key_algorithm`
- `public_key_size`
- `chain_position`

**Confidence notes**
- Fingerprint-based identity is deterministic; chain position can vary by observed chain presentation.

**Example JSON**

```json
{
  "id": "certificate:9f1ec4...ab",
  "type": "Certificate",
  "label": "CN=payments.example.internal",
  "source": "tls_probe",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "tls_metadata.certificate",
  "confidence": 0.98,
  "observed_at": "2026-05-09T11:21:00Z",
  "properties": {
    "fingerprint_sha256": "9f1ec4...ab",
    "subject": "CN=payments.example.internal",
    "issuer": "CN=Corp Intermediate CA",
    "not_before": "2026-01-01T00:00:00Z",
    "not_after": "2027-01-01T00:00:00Z",
    "signature_algorithm": "sha256WithRSAEncryption",
    "public_key_algorithm": "RSA",
    "public_key_size": 2048,
    "chain_position": 0
  }
}
```

### ConfigFile Node

**Required properties**
- `path`
- `config_type`

**Optional properties**
- `readable`
- `extension`
- `source_path_group`

**Confidence notes**
- Existence signals can be high confidence even when readability is false.

**Example JSON**

```json
{
  "id": "config:host-001:d3f31f...2a",
  "type": "ConfigFile",
  "label": "/etc/ssl/openssl.cnf",
  "source": "host_agent",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "crypto_evidence.cert_indicators.config_file_indicators.files[0]",
  "confidence": 0.9,
  "observed_at": "2026-05-09T11:19:00Z",
  "properties": {
    "path": "/etc/ssl/openssl.cnf",
    "config_type": "tls",
    "readable": true,
    "extension": ".cnf",
    "source_path_group": "openssl"
  }
}
```

### Package Node

**Required properties**
- `name`
- `package_manager`

**Optional properties**
- `version`
- `source`

**Confidence notes**
- Confidence may decrease when package manager output is partial or normalized from inconsistent host tools.

**Example JSON**

```json
{
  "id": "package:host-001:dpkg:openssl",
  "type": "Package",
  "label": "openssl",
  "source": "host_agent",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "crypto_evidence.package_metadata.packages[0]",
  "confidence": 0.94,
  "observed_at": "2026-05-09T11:19:00Z",
  "properties": {
    "name": "openssl",
    "package_manager": "dpkg",
    "version": "3.0.2-0ubuntu1",
    "source": "os-package-db"
  }
}
```

### CryptoFinding Node

**Required properties**
- `finding_type`
- `severity`

**Optional properties**
- `algorithm`
- `location`
- `rationale`
- `related_signal`

**Confidence notes**
- Findings from deterministic risk rules are preferred; heuristic findings must carry lower confidence.

**Example JSON**

```json
{
  "id": "finding:scan-2026-05-09-001:weak_signature:9f1ec4",
  "type": "CryptoFinding",
  "label": "Weak signature algorithm detected",
  "source": "risk_engine",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "stage2_signals.evidence_signals[2]",
  "confidence": 0.82,
  "observed_at": "2026-05-09T11:25:00Z",
  "properties": {
    "finding_type": "weak_signature",
    "severity": "medium",
    "algorithm": "sha1WithRSAEncryption",
    "location": "tls leaf certificate",
    "rationale": "Signature algorithm is not quantum-resilient and below policy baseline.",
    "related_signal": "legacy_signature_algorithm"
  }
}
```

### Owner Node

**Required properties**
- `name`
- `owner_type`

**Optional properties**
- `contact`
- `team_id`

**Confidence notes**
- Ownership may be authoritative (CMDB/team map) or inferred (naming convention); inference must be marked.

**Example JSON**

```json
{
  "id": "owner:team:payments-platform",
  "type": "Owner",
  "label": "Payments Platform Team",
  "source": "inventory_enrichment",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "assets[0].owner",
  "confidence": 0.88,
  "observed_at": "2026-05-09T11:20:00Z",
  "properties": {
    "name": "payments-platform",
    "owner_type": "team",
    "contact": "payments-platform@example.internal",
    "team_id": "TEAM-142"
  }
}
```

### MigrationTask Node

**Required properties**
- `task_type`
- `wave`
- `priority_score`

**Optional properties**
- `status`
- `reason`
- `planning_reasons`

**Confidence notes**
- Planner-derived priority can be deterministic from fixed scoring inputs; reason text may include best-effort narrative.

**Example JSON**

```json
{
  "id": "migration_task:host-001:2:replace_legacy_cert",
  "type": "MigrationTask",
  "label": "Replace legacy certificate",
  "source": "planner_service",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "planner.plan.tasks[0]",
  "confidence": 0.9,
  "observed_at": "2026-05-09T11:30:00Z",
  "properties": {
    "task_type": "replace_legacy_cert",
    "wave": 2,
    "priority_score": 78,
    "status": "proposed",
    "reason": "High-risk service with expiring certificate and critical workload.",
    "planning_reasons": ["critical_asset", "crypto_finding_present", "near_term_expiry"]
  }
}
```

## Edge Contracts

### 1) RUNS
- **From:** `Asset`
- **To:** `Service`
- **Meaning:** Asset hosts or runs a service endpoint.
- **Required edge properties:** none
- **Confidence notes:** May be lower when inferred from indirect network observation.

```json
{
  "id": "edge:asset:host-001:RUNS:service:host-001:tcp:443:payments.example.internal",
  "type": "RUNS",
  "from": "asset:host-001",
  "to": "service:host-001:tcp:443:payments.example.internal",
  "source": "inventory_projection",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "asset_service_mapping[0]",
  "confidence": 0.91,
  "observed_at": "2026-05-09T11:21:00Z",
  "properties": {}
}
```

### 2) USES_CERTIFICATE
- **From:** `Service`
- **To:** `Certificate`
- **Meaning:** Service presented or is configured to use the certificate.
- **Required edge properties:** none
- **Confidence notes:** Strong when directly observed in TLS handshake.

### 3) HAS_CONFIG
- **From:** `Asset`
- **To:** `ConfigFile`
- **Meaning:** Config file belongs to or is observed on asset.
- **Required edge properties:** none
- **Confidence notes:** Readability not required for relationship; existence evidence is sufficient.

### 4) HAS_PACKAGE
- **From:** `Asset`
- **To:** `Package`
- **Meaning:** Package is installed on asset.
- **Required edge properties:** none
- **Confidence notes:** Based on package manager evidence quality.

### 5) SIGNED_BY
- **From:** `Certificate`
- **To:** `Certificate`
- **Meaning:** Child certificate is signed by parent certificate.
- **Required edge properties:** none
- **Confidence notes:** High when chain parse and issuer/subject/fingerprint linkage match.

### 6) HAS_FINDING
- **From:** `Asset`
- **To:** `CryptoFinding`
- **Meaning:** Finding applies to asset-level crypto posture.
- **Required edge properties:** none
- **Confidence notes:** Derived from risk/evidence mapping confidence.

### 7) SERVICE_HAS_FINDING
- **From:** `Service`
- **To:** `CryptoFinding`
- **Meaning:** Finding applies specifically to a service endpoint.
- **Required edge properties:** none
- **Confidence notes:** Use when finding location or signal is service-scoped.

### 8) OWNED_BY
- **From:** `Asset`
- **To:** `Owner`
- **Meaning:** Owner is accountable for asset remediation.
- **Required edge properties:** none
- **Confidence notes:** Lower confidence when mapped via naming heuristics.

### 9) HAS_MIGRATION_TASK
- **From:** `Asset`
- **To:** `MigrationTask`
- **Meaning:** Migration task is planned for that asset.
- **Required edge properties:** none
- **Confidence notes:** Strong when planner output includes explicit asset linkage.

**Generic edge example (applies to all edge types):**

```json
{
  "id": "edge:service:host-001:tcp:443:payments.example.internal:USES_CERTIFICATE:certificate:9f1ec4...ab",
  "type": "USES_CERTIFICATE",
  "from": "service:host-001:tcp:443:payments.example.internal",
  "to": "certificate:9f1ec4...ab",
  "source": "inventory_projection",
  "scan_id": "scan-2026-05-09-001",
  "evidence_ref": "tls_metadata.certificate",
  "confidence": 0.98,
  "observed_at": "2026-05-09T11:21:00Z",
  "properties": {}
}
```

## Evidence Mapping Examples

### Host Package Evidence

**Input**
- `crypto_evidence.package_metadata.packages[]`

**Output**
- `Package` node
- `Asset HAS_PACKAGE Package` edge

### Host Config Evidence

**Input**
- `crypto_evidence.cert_indicators.config_file_indicators.files[]`

**Output**
- `ConfigFile` node
- `Asset HAS_CONFIG ConfigFile` edge

### Network TLS Certificate Evidence

**Input**
- `tls_metadata.certificate`

**Output**
- `Service` node
- `Certificate` node
- `Service USES_CERTIFICATE Certificate` edge

### Certificate Chain Evidence

**Input**
- `tls_metadata.certificate_chain.certificates[]`

**Output**
- `Certificate` nodes
- `Certificate SIGNED_BY Certificate` edges

### Risk Signal Evidence

**Input**
- `stage2_signals.evidence_signals`

**Output**
- `CryptoFinding` node
- `Asset HAS_FINDING CryptoFinding` edge

### Planner Evidence

**Input**
- planner `priority_score` / `wave` / `planning_reasons`

**Output**
- `MigrationTask` node
- `Asset HAS_MIGRATION_TASK MigrationTask` edge

## JSON Schema Sketches

### Graph Node Schema

```json
{
  "type": "object",
  "required": ["id", "type", "label", "source", "confidence", "properties"],
  "properties": {
    "id": {"type": "string"},
    "type": {"type": "string"},
    "label": {"type": "string"},
    "source": {"type": "string"},
    "scan_id": {"type": ["string", "null"]},
    "evidence_ref": {"type": ["string", "null"]},
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "observed_at": {"type": ["string", "null"], "format": "date-time"},
    "properties": {"type": "object"}
  },
  "additionalProperties": false
}
```

### Graph Edge Schema

```json
{
  "type": "object",
  "required": ["id", "type", "from", "to", "source", "confidence", "properties"],
  "properties": {
    "id": {"type": "string"},
    "type": {"type": "string"},
    "from": {"type": "string"},
    "to": {"type": "string"},
    "source": {"type": "string"},
    "scan_id": {"type": ["string", "null"]},
    "evidence_ref": {"type": ["string", "null"]},
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    "observed_at": {"type": ["string", "null"], "format": "date-time"},
    "properties": {"type": "object"}
  },
  "additionalProperties": false
}
```

### Graph Snapshot Schema

```json
{
  "graph_snapshot_id": "string",
  "generated_at": "ISO timestamp",
  "source": "inventory_projection",
  "nodes": [],
  "edges": [],
  "warnings": []
}
```

## Graph Snapshot Example

```json
{
  "graph_snapshot_id": "graph-snap-2026-05-09-scan-001",
  "generated_at": "2026-05-09T11:35:00Z",
  "source": "inventory_projection",
  "nodes": [
    {"id": "asset:host-001", "type": "Asset", "label": "payments-api-prod-01", "source": "inventory_ingest", "scan_id": "scan-2026-05-09-001", "evidence_ref": "assets[0]", "confidence": 0.99, "observed_at": "2026-05-09T11:20:00Z", "properties": {"name": "payments-api-prod-01", "asset_type": "vm", "environment": "prod", "criticality": "high"}},
    {"id": "service:host-001:tcp:443:payments.example.internal", "type": "Service", "label": "tcp/443 payments.example.internal", "source": "network_scan", "scan_id": "scan-2026-05-09-001", "evidence_ref": "tls_metadata.target", "confidence": 0.96, "observed_at": "2026-05-09T11:21:00Z", "properties": {"protocol": "tcp", "port": 443, "fqdn": "payments.example.internal", "asset_id": "host-001"}},
    {"id": "certificate:9f1ec4...ab", "type": "Certificate", "label": "CN=payments.example.internal", "source": "tls_probe", "scan_id": "scan-2026-05-09-001", "evidence_ref": "tls_metadata.certificate", "confidence": 0.98, "observed_at": "2026-05-09T11:21:00Z", "properties": {"fingerprint_sha256": "9f1ec4...ab", "subject": "CN=payments.example.internal", "issuer": "CN=Corp Intermediate CA"}},
    {"id": "package:host-001:dpkg:openssl", "type": "Package", "label": "openssl", "source": "host_agent", "scan_id": "scan-2026-05-09-001", "evidence_ref": "crypto_evidence.package_metadata.packages[0]", "confidence": 0.94, "observed_at": "2026-05-09T11:19:00Z", "properties": {"name": "openssl", "package_manager": "dpkg", "version": "3.0.2-0ubuntu1"}},
    {"id": "config:host-001:d3f31f...2a", "type": "ConfigFile", "label": "/etc/ssl/openssl.cnf", "source": "host_agent", "scan_id": "scan-2026-05-09-001", "evidence_ref": "crypto_evidence.cert_indicators.config_file_indicators.files[0]", "confidence": 0.9, "observed_at": "2026-05-09T11:19:00Z", "properties": {"path": "/etc/ssl/openssl.cnf", "config_type": "tls"}},
    {"id": "finding:scan-2026-05-09-001:weak_signature:9f1ec4", "type": "CryptoFinding", "label": "Weak signature algorithm detected", "source": "risk_engine", "scan_id": "scan-2026-05-09-001", "evidence_ref": "stage2_signals.evidence_signals[2]", "confidence": 0.82, "observed_at": "2026-05-09T11:25:00Z", "properties": {"finding_type": "weak_signature", "severity": "medium"}},
    {"id": "migration_task:host-001:2:replace_legacy_cert", "type": "MigrationTask", "label": "Replace legacy certificate", "source": "planner_service", "scan_id": "scan-2026-05-09-001", "evidence_ref": "planner.plan.tasks[0]", "confidence": 0.9, "observed_at": "2026-05-09T11:30:00Z", "properties": {"task_type": "replace_legacy_cert", "wave": 2, "priority_score": 78}}
  ],
  "edges": [
    {"id": "edge:asset:host-001:RUNS:service:host-001:tcp:443:payments.example.internal", "type": "RUNS", "from": "asset:host-001", "to": "service:host-001:tcp:443:payments.example.internal", "source": "inventory_projection", "scan_id": "scan-2026-05-09-001", "evidence_ref": "asset_service_mapping[0]", "confidence": 0.91, "observed_at": "2026-05-09T11:21:00Z", "properties": {}},
    {"id": "edge:service:host-001:tcp:443:payments.example.internal:USES_CERTIFICATE:certificate:9f1ec4...ab", "type": "USES_CERTIFICATE", "from": "service:host-001:tcp:443:payments.example.internal", "to": "certificate:9f1ec4...ab", "source": "inventory_projection", "scan_id": "scan-2026-05-09-001", "evidence_ref": "tls_metadata.certificate", "confidence": 0.98, "observed_at": "2026-05-09T11:21:00Z", "properties": {}},
    {"id": "edge:asset:host-001:HAS_PACKAGE:package:host-001:dpkg:openssl", "type": "HAS_PACKAGE", "from": "asset:host-001", "to": "package:host-001:dpkg:openssl", "source": "inventory_projection", "scan_id": "scan-2026-05-09-001", "evidence_ref": "crypto_evidence.package_metadata.packages[0]", "confidence": 0.94, "observed_at": "2026-05-09T11:19:00Z", "properties": {}},
    {"id": "edge:asset:host-001:HAS_CONFIG:config:host-001:d3f31f...2a", "type": "HAS_CONFIG", "from": "asset:host-001", "to": "config:host-001:d3f31f...2a", "source": "inventory_projection", "scan_id": "scan-2026-05-09-001", "evidence_ref": "crypto_evidence.cert_indicators.config_file_indicators.files[0]", "confidence": 0.9, "observed_at": "2026-05-09T11:19:00Z", "properties": {}},
    {"id": "edge:asset:host-001:HAS_FINDING:finding:scan-2026-05-09-001:weak_signature:9f1ec4", "type": "HAS_FINDING", "from": "asset:host-001", "to": "finding:scan-2026-05-09-001:weak_signature:9f1ec4", "source": "inventory_projection", "scan_id": "scan-2026-05-09-001", "evidence_ref": "stage2_signals.evidence_signals[2]", "confidence": 0.82, "observed_at": "2026-05-09T11:25:00Z", "properties": {}},
    {"id": "edge:asset:host-001:HAS_MIGRATION_TASK:migration_task:host-001:2:replace_legacy_cert", "type": "HAS_MIGRATION_TASK", "from": "asset:host-001", "to": "migration_task:host-001:2:replace_legacy_cert", "source": "inventory_projection", "scan_id": "scan-2026-05-09-001", "evidence_ref": "planner.plan.tasks[0]", "confidence": 0.9, "observed_at": "2026-05-09T11:30:00Z", "properties": {}}
  ],
  "warnings": ["Partial snapshot: owner and chain nodes not present in this compact example."]
}
```

## Validation Rules

- Every `edge.from` must reference an existing node `id`.
- Every `edge.to` must reference an existing node `id`.
- Node IDs must be unique within a snapshot.
- Edge IDs must be unique within a snapshot.
- `confidence` must be between `0.0` and `1.0`.
- `observed_at` must be a valid ISO timestamp or `null`.
- Required properties must exist for each node/edge type.
- Unknown fields should be stored inside `properties` only.
- A graph snapshot must remain valid even when partial.

## Privacy and Sensitive Data Rules

- Graph data can expose internal infrastructure relationships.
- Do not export graph data outside the deployment boundary by default.
- Paths, hostnames, and owner names may be sensitive.
- Hash sensitive path-derived IDs where appropriate.
- External LLM cannot receive graph data unless explicitly configured.
- Local/offline operation is the default design assumption.

## Non-Goals

- No graph database implementation.
- No graph API implementation.
- No graph traversal engine.
- No Neo4j dependency.
- No LLM graph reasoning.
- No RAG.
- No auth/RBAC.
- No production deployment.
- No Windows agent implementation.

## Recommended Next Step

Graph Design Task 3 — Define graph projection plan from inventory/risk/planner outputs.
