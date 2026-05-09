#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT_DIR/reports/graph/latest"
mkdir -p "$OUT_DIR"

HOST_FIXTURE="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json"
NETWORK_FIXTURE="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json"

python "$ROOT_DIR/tools/graph_projection/project_stage2_fixtures.py" \
  --host "$HOST_FIXTURE" \
  --network "$NETWORK_FIXTURE" \
  --snapshot-out "$OUT_DIR/graph-snapshot.json" \
  --report-out "$OUT_DIR/graph-projection-report.md"

echo "Graph projection smoke complete."
echo "- $OUT_DIR/graph-snapshot.json"
echo "- $OUT_DIR/graph-projection-report.md"
