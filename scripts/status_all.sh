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
    if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
      echo "[RUNNING] $name PID=$pid PORT=$port"
      return
    fi
  fi

  echo "[STOPPED] $name PORT=$port"
}

check_service "inventory-service" "8001"
check_service "risk-engine" "8002"
check_service "copilot-service" "8003"
check_service "planner-service" "8004"
check_service "workflow-service" "8005"
check_service "retrieval-service" "8006"
check_service "dashboard-ui" "8010"
