# Graph Snapshot Loader Smoke Report

- utc_timestamp: 2026-05-13T07:55:59.515265+00:00
- snapshot_path: reports/graph/latest/graph-snapshot.json
- graph_schema_version: 0.1
- node_count: 8
- edge_count: 5
- warning_count: 3
- node_types: Asset, Certificate, ConfigFile, Package, Service
- edge_types: HAS_CONFIG, HAS_PACKAGE, SIGNED_BY, USES_CERTIFICATE
- result: PASS

This smoke validates the read-only Graph Snapshot Loader helper only.

This smoke does not implement or start a Graph API.
