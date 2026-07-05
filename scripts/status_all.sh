#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT/run/pids"

check_service() {
  local name="$1"
  local port="$2"
  local pidfile="$PID_DIR/${name}.pid"

  if [[ -f "$pidfile" ]]; then
    local pid
    pid="$(cat "$pidfile" 2>/dev/null || true)"
    local state
    state="$(ps -p "$pid" -o stat= 2>/dev/null | tr -d ' ' || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null && [[ "$state" != Z* ]] && curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      echo "[RUNNING] $name PID=$pid PORT=$port"
      return
    fi
  fi

  echo "[STOPPED] $name PORT=$port"
}

check_service "inventory-service" "8001"
check_service "risk-engine" "8002"
check_service "planner-service" "8004"
check_service "workflow-service" "8005"
check_service "policy-engine" "8007"
check_service "crypto-fingerprint-service" "8003"
check_service "evidence-normalizer" "8009"
check_service "scenario-engine" "8006"
check_service "integration-service" "8011"
check_service "pqc-readiness-service" "8012"
check_service "graph-service" "8013"
check_service "finding-attribution-service" "8014"
check_service "api-gateway" "8000"
