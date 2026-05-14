# Graph API Design

**Status:** Minimal read-only Graph API over JSON snapshot is implemented. Graph DB/Neo4j/UI/traversal remain not implemented.

## 1. Purpose

This document defines a future design for a Graph API that can expose the existing JSON dependency graph snapshot in a controlled, safe, and local-first way.

This document is design-only and does not implement an API.

## 2. Current state

- JSON graph snapshot prototype exists.
- Snapshot generation is offline and deterministic.
- Graph database is not present.
- Minimal read-only Graph API is present in `services/api-gateway/main.py` (`GET /graph/snapshot`, `/graph/summary`, `/graph/nodes`, `/graph/edges`, `/graph/warnings`).
- Graph UI is not present.
- Neo4j is not present.
- Graph remains JSON Snapshot First.

## 3. Non-goals

- no graph API implementation
- no new service
- no graph database
- no Neo4j
- no Postgres graph tables
- no graph UI
- no traversal engine
- no blast-radius engine
- no LLM graph reasoning
- no autonomous remediation

## 4. Design principles

- JSON Snapshot First
- read-only API initially
- no mutation endpoints
- deterministic output
- schema-versioned responses
- local-first
- no external service dependency
- no sensitive evidence exposure by default
- preserve existing graph projection behavior

## 5. Proposed API scope

The first future Graph API scope is read-only and snapshot-backed only.

Conceptual endpoints:

- `GET /graph/snapshot`
- `GET /graph/nodes`
- `GET /graph/edges`
- `GET /graph/summary`
- `GET /graph/warnings`

These endpoints are implemented as read-only snapshot-backed routes. Node-by-id endpoint is intentionally deferred.

## 6. Out-of-scope endpoints

Not planned for first API version:

- `POST`/`PUT`/`PATCH`/`DELETE` graph mutations
- graph traversal query language
- blast radius query endpoint
- remediation endpoint
- LLM graph reasoning endpoint
- external graph export endpoint

## 7. Data source model

- Initial API should read from generated JSON graph snapshot only.
- No graph DB backing store.
- No live traversal engine.
- No live inventory query fan-out.
- Snapshot path should be configurable in a later phase.
- Missing snapshot should fail safely.

## 8. Response contract design

Conceptual envelope:

- `graph_schema_version`
- `generated_at`
- `source`
- `nodes`
- `edges`
- `warnings`
- `metadata`

Conceptual node response fields:

- `id`
- `type`
- `labels`
- `properties`
- `confidence`
- `source_refs` (if available)

Conceptual edge response fields:

- `id`
- `source`
- `target`
- `type`
- `confidence`
- `warnings`

## 9. Filtering and pagination design

Future simple filters:

- node type
- edge type
- asset id
- warning type
- confidence threshold

Pagination should stay simple in first version:

- offset/limit (or cursor in a later revision)
- no complex query language in first version

## 10. Safety/privacy boundaries

- no secrets
- no private keys
- no raw tokens
- no credentials
- no raw package lists unless already present in safe snapshot
- no raw hostnames/IPs by default if redacted source is available
- no mutation/remediation
- no external export by default

## 11. Error handling design

Future error classes:

- `snapshot_missing`
- `snapshot_invalid_json`
- `unsupported_graph_schema_version`
- `node_not_found`
- `invalid_filter`
- `unsafe_request_rejected`

## 12. Validation approach

- Phase 0 — docs-only design
- Phase 1 — API contract tests with static fixture only
- Phase 2 — read-only snapshot loader helper
- Phase 3 — minimal read-only API endpoints
- Phase 4 — smoke script against static snapshot
- Phase 5 — optional UI/design later, not now

## 13. Compatibility with current graph projection

- Existing graph projection tests/smoke must keep passing.
- Graph API must not require Neo4j or DB.
- Graph API must not change snapshot generation.
- Graph API must consume the existing snapshot contract.

## 14. Stop conditions

Stop if any of the following become required:

- graph DB is required
- Neo4j is introduced
- mutation endpoint is added
- traversal engine is required
- blast-radius logic is required
- LLM graph reasoning is introduced
- sensitive raw evidence must be exposed
- existing graph projection behavior changes

## 15. Status wording

Graph API status: minimal read-only snapshot endpoints implemented; graph DB/Neo4j/UI/traversal/blast-radius/LLM graph reasoning remain not implemented.
