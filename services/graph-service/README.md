# Graph Service

Deterministic **in-memory** graph traversal over the QRP JSON graph snapshot
(architecture &sect;5). It answers the relationship questions a flat list cannot,
**without a graph database or Neo4j** &mdash; staying inside the repo's
"JSON Snapshot First" boundary.

## Why
The snapshot projection and the read-only gateway `/graph/*` endpoints list
nodes/edges but cannot traverse. This service adds the actual analytical queries
&sect;5 calls out: blast radius, trust chain, neighbours.

## Queries
- **blast-radius** &mdash; if a node is compromised, which nodes are affected?
  Computed as the transitive **predecessors** (things that depend on it), by
  walking edges backwards. E.g. compromise a root CA &rarr; the leaf cert, the
  service using it and the asset running the service are all affected.
- **trust-chain** &mdash; a certificate's chain to its root, following
  `SIGNED_BY` edges.
- **neighbors** &mdash; direct neighbours of a node, filtered by direction
  (`in` / `out` / `both`) and edge type.
- **evidence-path** &mdash; the attribution chain around a node:
  `vulnerability &rarr; service/location &rarr; asset &rarr; certificate/library/pipeline`.
  Works best from a `CryptoFinding`, also from a Service / Asset / Certificate.

## Main endpoints
- `GET /health`
- `GET /queries`
- `POST /blast-radius` &mdash; `{ node_id, edge_types?, max_depth?, snapshot? }`
- `POST /trust-chain` &mdash; `{ node_id, snapshot? }`
- `POST /neighbors` &mdash; `{ node_id, direction?, edge_types?, snapshot? }`

If `snapshot` is omitted, the service loads `GRAPH_SNAPSHOT_PATH` (or the default
projected snapshot at `reports/graph/latest/graph-snapshot.json`). Remote URLs
are rejected; a missing snapshot returns `graph_snapshot_missing`. An unknown
`node_id` returns `node_not_found` (404).

## Example

```json
POST /blast-radius
{ "node_id": "cert:root" }
->
{
  "node_id": "cert:root",
  "affected_count": 3,
  "affected": [
    {"node_id": "cert:leaf", "depth": 1, "node": {...}},
    {"node_id": "service:s", "depth": 2, "node": {...}},
    {"node_id": "asset:a",   "depth": 3, "node": {...}}
  ],
  "affected_node_ids": ["cert:leaf", "service:s", "asset:a"]
}
```

## Run locally

```bash
cd services/graph-service
pip install -r requirements.txt
PYTHONPATH=. uvicorn app.main:app --port 8013
```

## Tests

```bash
cd services/graph-service
PYTHONPATH=. pytest -q
```

## Known limitations / boundary
- In-memory traversal over a single JSON snapshot; **no graph DB, no Neo4j, no
  persistence** &mdash; consistent with the graph freeze status.
- Blast radius is structural (edge reachability); it does not weight by
  confidence or criticality (that is risk-engine's concern).
- Backs the API Gateway `POST /api/graph/{blast-radius,trust-chain,neighbors}`.
