# Graph API Read-only Smoke Report

- utc_timestamp: 2026-05-14T04:43:43.571288+00:00
- snapshot_path: /workspace/Quantum-Readiness-Platform/reports/graph/latest/graph-snapshot.json
- graph_schema_version: 0.1
- node_count: 8
- edge_count: 5
- warning_count: 3
- endpoints_checked: /graph/snapshot, /graph/summary, /graph/nodes, /graph/edges, /graph/warnings
- result: PASS

This smoke validates read-only Graph API endpoints over the JSON snapshot only.
No graph database, Neo4j, traversal engine, or mutation endpoint is used.
