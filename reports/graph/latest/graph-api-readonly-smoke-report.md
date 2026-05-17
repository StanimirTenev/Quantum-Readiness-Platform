# Graph API Read-only Smoke Report

- utc_timestamp: 2026-05-17T06:52:12.591994+00:00
- snapshot_path: /workspace/Quantum-Readiness-Platform/reports/graph/latest/graph-snapshot.json
- graph_schema_version: 0.1
- node_count: 8
- edge_count: 5
- warning_count: 3
- endpoints_checked: /graph/snapshot, /graph/summary, /graph/nodes, /graph/edges, /graph/warnings
- result: PASS

Graph API remains read-only over the local JSON snapshot.
No graph database, Neo4j, traversal engine, blast-radius engine, or mutation endpoint is used.
