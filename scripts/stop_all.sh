#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT/run/pids"

stop_service() {
  local name="$1"
  local pidfile="$PID_DIR/${name}.pid"

  if [[ ! -f "$pidfile" ]]; then
    echo "[SKIP] $name pid file not found"
    return
  fi

  local pid
  pid="$(cat "$pidfile" 2>/dev/null || true)"

  if [[ -z "$pid" ]]; then
    echo "[SKIP] $name pid file empty"
    rm -f "$pidfile"
    return
  fi

  if kill -0 "$pid" 2>/dev/null; then
    echo "[STOP] $name PID $pid"
    kill "$pid" || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      echo "[KILL] $name PID $pid"
      kill -9 "$pid" || true
    fi
  else
    echo "[SKIP] $name PID $pid not running"
  fi

  rm -f "$pidfile"
}

stop_service "api-gateway"
stop_service "crypto-fingerprint-service"
stop_service "policy-engine"
stop_service "workflow-service"
stop_service "planner-service"
stop_service "risk-engine"
stop_service "inventory-service"

echo
echo "All required services stopped."
