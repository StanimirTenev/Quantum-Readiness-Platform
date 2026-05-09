# Dependency Graph Implementation Boundary

## Purpose

This document decides the safest minimal implementation path for the first QRP dependency graph layer.

This is a design decision document only.
No implementation is included.
No graph database is introduced.
No graph API is implemented.
This document prevents premature graph overbuild.

## Current Graph Design Status

- The graph design document exists: `docs/dependency-graph-design.md`.
- The graph contract document exists: `docs/dependency-graph-contract.md`.
- The graph projection plan exists: `docs/dependency-graph-projection-plan.md`.
- The graph projection validation examples exist: `docs/dependency-graph-projection-validation-examples.md`.
- Stage 1/2/3 core flow is already proven.
- Graph implementation has not started.

## Problem to Solve

The graph layer is needed to support:

- evidence relationship mapping
- asset/service/certificate/config/package relationships
- explainable high-priority reasoning
- early blast-radius estimation
- migration sequencing support

But it must not immediately introduce:

- heavy graph database dependency
- complex traversal engine
- new operational burden
- premature production architecture
- Copilot/RAG graph reasoning

## Options Considered

### Option A — JSON Snapshot First

Description:
Generate deterministic graph snapshots as JSON files using existing inventory/risk/planner outputs.

Example output:
`reports/graph/latest/graph-snapshot.json`

Pros:
- lightest implementation
- no database dependency
- easiest to test
- works locally/offline
- aligns with current evidence/report pattern
- good for smoke validation
- keeps graph as derived projection, not source of truth

Cons:
- limited querying
- not ideal for large graphs
- no native graph traversal
- file management needed

Best for:
- first implementation
- validation
- investor/demo evidence
- local/offline prototype

### Option B — PostgreSQL Projection Tables

Description:
Store graph-like nodes and edges in relational tables.

Pros:
- familiar storage model
- easier to deploy than graph DB
- can join with inventory/risk data
- better persistence than JSON only

Cons:
- adds schema/migration work
- graph traversal is less natural
- may complicate current prototype too early

Best for:
- later controlled persistence layer
- when graph snapshots need history/search

### Option C — Neo4j / Dedicated Graph DB

Description:
Use dedicated graph database for nodes, edges and traversals.

Pros:
- natural graph queries
- strong traversal support
- better for blast radius and dependency reasoning

Cons:
- new dependency
- heavier local deployment
- more operational complexity
- premature before projection model is proven

Best for:
- later mature graph stage
- larger enterprise deployments
- real blast-radius queries

### Option D — Hybrid

Description:
Keep canonical data in inventory/risk/planner services, generate JSON snapshots, and later project to PostgreSQL or graph DB.

Pros:
- flexible
- keeps deterministic source of truth
- avoids early lock-in
- supports migration to graph DB later

Cons:
- requires discipline
- more design overhead later

Best for:
- long-term direction after JSON snapshot proves useful

## Recommended Decision

Recommended: **JSON Snapshot First**.

The first graph implementation should be a deterministic JSON graph snapshot generator, not a database-backed graph service.

Rationale:
- QRP is still a TRL 5 candidate / operational prototype.
- Stage 2/3 validation already uses reports and evidence artifacts.
- JSON snapshot aligns with current validation style.
- It avoids premature Neo4j/PostgreSQL schema work.
- It keeps graph projection testable and local-first.
- It allows graph model validation before storage commitment.

## Minimal Implementation Boundary

Allowed in first graph implementation:
- read existing official Stage 2 fixtures or inventory/risk/planner outputs
- generate graph snapshot JSON
- validate node/edge references
- generate warnings
- write report under `reports/graph/`
- add tests for deterministic projection helpers
- no persistent graph database

Not allowed in first implementation:
- graph database dependency
- graph API service
- Neo4j
- Cypher
- production persistence
- live graph UI
- LLM graph reasoning
- RAG
- auth/RBAC
- cloud integrations
- autonomous execution

## Proposed First Implementation Shape

Future script/module name:

`scripts/run_graph_projection_smoke.sh`

Potential future output:

- `reports/graph/latest/graph-snapshot.json`
- `reports/graph/latest/graph-projection-report.md`

Potential future source inputs:

- `services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json`
- `services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json`
- risk-engine sample output
- planner-service sample output

Potential future internal module:

- `tools/graph_projection/`

or

- `scripts/lib/graph_projection.py`

Exact module path should be decided during implementation task. Do not create it now.

## Graph Snapshot Ownership

- Graph snapshot is derived data.
- Inventory/risk/planner remain source of truth.
- Graph projection must be repeatable.
- Graph snapshot can be regenerated.
- Graph snapshot must not become the canonical asset store.

## Versioning

Add version field:

`graph_schema_version: "0.1"`

Rules:
- increment minor version for additive fields
- increment major version for breaking changes
- include schema version in every snapshot
- include `projection_version` if implementation later needs it

Example:

```json
{
  "graph_schema_version": "0.1",
  "projection_version": "0.1.0"
}
```

## Storage Path Convention

Future paths:

- `reports/graph/latest/graph-snapshot.json`
- `reports/graph/latest/graph-projection-report.md`
- `reports/graph/examples/stage2-fixture-graph-snapshot.json`

Optional future timestamped path:

- `reports/graph/runs/<timestamp>/graph-snapshot.json`

Timestamped graph archive is future, not first implementation unless explicitly chosen.

## Validation Boundary

Future first implementation must validate:

- `graph_snapshot_id` exists
- `graph_schema_version` exists
- `generated_at` exists
- `nodes[]` exists
- `edges[]` exists
- `warnings[]` exists
- node ids are unique
- edge ids are unique
- every `edge.from` exists
- every `edge.to` exists
- confidence values are 0.0–1.0
- `source`/`evidence_ref` exists where available
- graph remains valid when partial

## Privacy Boundary

- graph snapshots are sensitive infrastructure intelligence
- graph files must stay inside customer-controlled deployment by default
- do not export graph snapshots automatically
- do not send graph snapshots to external LLMs by default
- local/offline validation must work
- path-derived IDs should be hashed where appropriate
- external sharing must be explicit operator action

## What Would Trigger PostgreSQL Later

PostgreSQL projection tables become reasonable when:

- graph snapshots are useful and stable
- users need history across scans
- users need filtering/search across many graph snapshots
- graph data must be joined with inventory/risk records
- JSON files become difficult to manage

## What Would Trigger Neo4j Later

Neo4j or graph DB becomes reasonable when:

- real dependency traversal is needed
- blast-radius queries require multi-hop traversal
- graph size grows beyond simple snapshots
- users need interactive graph exploration
- query patterns justify graph DB complexity

## Stop Rules

Do not move to graph DB implementation until:

- JSON snapshot projection exists
- projection validation tests exist
- graph snapshot report exists
- sample graph outputs are reviewed
- storage tradeoff is re-evaluated

## Future Implementation Sequence

1. Graph Implementation Task 1 — JSON snapshot projection smoke using Stage 2 fixtures
2. Graph Implementation Task 2 — Add graph projection helper tests
3. Graph Implementation Task 3 — Add graph projection report
4. Graph Implementation Task 4 — Integrate risk/planner sample outputs
5. Graph Implementation Task 5 — Evaluate PostgreSQL vs graph DB after snapshot validation

Do not implement these now.

## Non-Goals

- no graph implementation in this task
- no graph database dependency
- no Neo4j
- no PostgreSQL graph migrations
- no graph API endpoint
- no graph traversal engine
- no graph UI
- no LLM graph reasoning
- no RAG
- no auth/RBAC
- no production deployment
- no autonomous execution
- no Windows agent implementation

## Recommended Next Step

Graph Implementation Task 1 — JSON snapshot projection smoke using Stage 2 fixtures.
