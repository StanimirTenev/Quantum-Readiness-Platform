#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[stage2-smoke] 1/2 Inventory ingest + scan storage + risk computation"
(
  cd "$ROOT_DIR/services/inventory-service"
  PYTHONPATH=. pytest -q tests/test_stage2_smoke_validation.py
)

echo "[stage2-smoke] 2/2 Planner still returns a plan"
(
  cd "$ROOT_DIR/services/planner-service"
  PYTHONPATH=. pytest -q tests/test_planner_api.py::test_plan
)

echo "[stage2-smoke] DONE"
