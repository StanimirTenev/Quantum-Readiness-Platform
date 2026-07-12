# ADR 0001 — Product v1 Architecture Decisions

- Status: Accepted
- Date: 2026-07-12
- Driven by: `docs/product-v1-roadmap.md`, `docs/product-v1-scope.md`

## Context

QRP has a working local product demo: 16 FastAPI microservices, two Go network/host agents, a
Python repo/CI scanner, a buildless web console, Docker Compose packaging (with an opt-in Caddy
HTTPS reverse-proxy profile and PostgreSQL for the deployed product), and five deterministic
Copilot subagents. The next goal is to move from demo/prototype to a finished on-prem Product
v1. This ADR records the technical decisions that shape that work, so later phases don't
re-litigate them piecemeal.

## Decisions

### Deployment
- **On-prem, Docker Compose single-node first.** Matches the already-shipped
  `infra/docker/docker-compose.yml` and the project's local-first positioning
  (`README.md`: "designed for internal/customer-controlled deployment").
- **Kubernetes/Helm later**, not a v1 requirement. `infra/k8s/` remains a placeholder until
  there's a real driver for it (e.g. a customer needing multi-node scale).

### Database
- **PostgreSQL** is the v1 production data store. `inventory-service` and `workflow-service`
  already support it (`DATABASE_URL`, `tools/db_compat.py`), used by `infra/docker`'s default
  Compose stack.
- **SQLite remains a local/dev-only fallback**, not a production deployment target -- preserves
  the zero-setup bare-metal dev loop (`make dev-up`) and keeps CI free of a Postgres dependency
  for routine test runs. `DATABASE_URL` unset (the default outside Docker) keeps today's
  SQLite behavior unchanged.
- **Schema migrations**: v1 needs a real migration tool (Alembic or equivalent) for the
  Postgres path specifically, replacing "production mode silently creates tables on first
  connect." The SQLite fallback's existing ALTER-TABLE-if-missing pattern
  (`_ensure_*_columns` in each repository) is adequate for dev/test and does not need to adopt
  Alembic itself -- only the Postgres/production path is in scope for versioned migrations.

### Auth
- **v1: local users + sessions/JWT.** Replaces `QRP_API_KEY` (a single shared secret, adequate
  for a demo, not for a real multi-user product) with real per-user accounts and RBAC (see
  Phase 3 of the roadmap). `QRP_API_KEY` and `QRP_DEMO_MODE` remain available as
  deployment-time options (e.g. a temporary public demo instance) even after real auth ships --
  they are orthogonal mechanisms, not replaced outright.
- **OIDC later**, not a v1 requirement.

### Graph
- **Persistent graph in Postgres first** (`graph_nodes`/`graph_edges` tables -- Phase 9),
  replacing the current in-memory/JSON-snapshot-based `graph-service`.
- **Neo4j later, only if needed** -- no committed timeline; revisit if query complexity or
  scale genuinely outgrows a relational graph representation.

### Copilot
- **Deterministic by default**, unchanged from today -- all five subagents (Risk Narrator,
  Discovery Analyst, Vendor Intelligence Analyst, Migration Planner, Change Assistant) stay
  template-based, no external LLM call.
- **Local LLM adapter optional, later, disabled by default** (Phase 10) -- only after the
  deterministic Copilot layer gains citations (Phase 10, item 27) and only with: no external
  provider by default, no execution permission, customer-approved documents only.

### Execution boundary
- **No production-changing actions**, unchanged from today's Trust Zone 4 dry-run-only
  boundary (`services/integration-service`, `services/copilot-service/app/change_assistant.py`).
  Migration workflows (Phase 8) generate tasks/checklists/exports only -- an operator executes
  the actual change outside QRP and reports back status/validation.

## Engineering sequence

`docs/product-v1-roadmap.md`'s "Recommended Engineering Order" section is the authoritative,
dependency-ordered task sequence (scope -> foundation -> auth/RBAC -> data model -> scan jobs ->
agents -> evidence -> risk/policy -> workflow -> graph -> reports -> backup/restore -> security
-> lab validation -> release). This ADR does not duplicate it; each phase's own task files
record progress as it happens.

## Consequences

- Larger, from-scratch subsystems (real auth/RBAC, a worker queue for scan jobs, agent
  enrollment/identity, a Postgres-backed persistent graph) are now in scope for v1, not deferred
  indefinitely -- this is a substantial, multi-phase engineering effort, not incremental
  polish.
- The dual SQLite/Postgres model built for the public-demo work stays intact and gets a clearer
  purpose: SQLite for dev/test, Postgres (with real migrations) for production. No forced
  migration path for existing SQLite dev databases -- they were never production data.
- Every later roadmap phase inherits these decisions; a phase that wants to deviate (e.g. an
  early OIDC requirement, or an early Neo4j migration) should record a new ADR explaining why,
  not silently drift from this one.
