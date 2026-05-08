#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
PID_DIR="$ROOT/run/pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

start_service() {
  local name="$1"
  local workdir="$2"
  local port="$3"
  local app_target="$4"
  local env_vars="${5:-}"

  local pidfile="$PID_DIR/${name}.pid"
  local logfile="$LOG_DIR/${name}.log"

  if [[ -f "$pidfile" ]]; then
    local oldpid
    oldpid="$(cat "$pidfile" 2>/dev/null || true)"
    if [[ -n "$oldpid" ]] && kill -0 "$oldpid" 2>/dev/null; then
      if curl -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
        echo "[SKIP] $name already running on PID $oldpid and healthy"
        return
      fi
      echo "[RESTART] $name has live PID $oldpid but failed health check"
      kill "$oldpid" >/dev/null 2>&1 || true
      sleep 1
      kill -9 "$oldpid" >/dev/null 2>&1 || true
      rm -f "$pidfile"
    else
      rm -f "$pidfile"
    fi
  fi

  echo "[START] $name on port $port"
  pushd "$workdir" >/dev/null
  setsid bash -c "echo \$\$ > '$pidfile'; exec env PYTHONUNBUFFERED=1 $env_vars python -m uvicorn '$app_target' --host 127.0.0.1 --port '$port' </dev/null >>'$logfile' 2>&1" >/dev/null 2>&1 &
  popd >/dev/null

  local attempt
  for attempt in {1..60}; do
    local newpid
    newpid="$(cat "$pidfile" 2>/dev/null || true)"
    if [[ -n "$newpid" ]] && kill -0 "$newpid" 2>/dev/null && curl -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
      echo "[OK] $name started with PID $newpid"
      return
    fi
    sleep 1
  done

  echo "[FAIL] $name failed to start or became unhealthy. Check $logfile"
  tail -n 80 "$logfile" || true
  exit 1
}

start_service "inventory-service" "$ROOT/services/inventory-service" "8001" "app.main:app"
start_service "risk-engine" "$ROOT/services/risk-engine" "8002" "app.main:app"
start_service "planner-service" "$ROOT/services/planner-service" "8004" "app.main:app"
start_service "workflow-service" "$ROOT/services/workflow-service" "8005" "app.main:app"
start_service "policy-engine" "$ROOT/services/policy-engine" "8007" "app.main:app"
start_service "api-gateway" "$ROOT/services/api-gateway" "8000" "main:app" "INVENTORY_SERVICE_URL=http://127.0.0.1:8001 RISK_ENGINE_URL=http://127.0.0.1:8002 POLICY_ENGINE_URL=http://127.0.0.1:8007 PLANNER_SERVICE_URL=http://127.0.0.1:8004 WORKFLOW_SERVICE_URL=http://127.0.0.1:8005 SCENARIO_ENGINE_URL=http://127.0.0.1:8006 COPILOT_SERVICE_URL=http://127.0.0.1:8008"

echo
echo "Required services started. Logs: $LOG_DIR"
