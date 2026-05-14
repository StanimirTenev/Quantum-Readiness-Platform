# Graph API Read-only Freeze Status

## Status Wording

Graph API Read-only Freeze Status — minimal read-only API implemented; production graph infrastructure not implemented.

## Purpose

This document freezes the current Graph API boundary after the minimal read-only implementation.

## Current Implemented Scope

- GET /graph/snapshot
- GET /graph/summary
- GET /graph/nodes
- GET /graph/edges
- GET /graph/warnings
- local JSON snapshot as source
- Graph Snapshot Loader helper
- GRAPH_SNAPSHOT_PATH support
- safe structured loader errors
- optional node_type / edge_type filters
- focused API tests
- read-only smoke script/report

## Explicitly Out of Scope

- POST/PUT/PATCH/DELETE graph endpoints
- graph mutation
- graph DB
- Neo4j
- PostgreSQL graph tables/migrations
- graph UI
- graph traversal engine
- blast-radius analysis
- LLM graph reasoning
- autonomous remediation
- production graph infrastructure

## Allowed Behavior

- read-only access to current graph snapshot
- local file snapshot only
- safe error responses
- simple filtering only
- no snapshot mutation
- no snapshot regeneration
- no live inventory/risk/planner fan-out

## Disallowed Behavior

- no graph writes
- no mutation endpoints
- no graph DB
- no DB-backed graph
- no Neo4j
- no traversal query language
- no blast-radius endpoint
- no LLM graph reasoning endpoint
- no external graph export endpoint
- no production graph claims

## Validation Commands

- pytest services/api-gateway/tests/test_gateway_api.py -q
- python -m pytest tools/graph_projection -q
- bash scripts/run_graph_api_readonly_smoke.sh
- bash scripts/run_graph_snapshot_loader_smoke.sh

## Safe Product Wording

Use:

“QRP includes a minimal read-only Graph API over the local JSON graph snapshot.”

Do NOT use:

- full graph API
- production graph platform
- graph database
- Neo4j graph
- blast-radius engine
- dependency traversal engine

## Stop Rules

Future work must stop if it introduces:

- mutation endpoints
- graph DB
- Neo4j
- Postgres graph tables
- graph UI
- traversal/blast-radius logic
- LLM graph reasoning
- production graph infrastructure claims

## Recommended Next Graph Options

- A. Graph API response hardening tests
- B. Graph API documentation examples
- C. Graph API pagination/filter design
- D. Stop graph work and review full repo checkpoint

Recommended default:

- D. Stop graph work and review full repo checkpoint
