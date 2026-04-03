#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/run/logs"
PID_DIR="$ROOT/run/pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

start_service() {
  local name="$1"
  local workdir="$2"
  local port="$3"
  local app="$4"

  local pidfile="$PID_DIR/${name}.pid"
  local logfile="$LOG_DIR/${name}.log"

  if [[ -f "$pidfile" ]]; then
    local oldpid
    oldpid="$(cat "$pidfile" 2>/dev/null || true)"
    if [[ -n "${oldpid}" ]] && kill -0 "$oldpid" 2>/dev/null; then
      echo "[SKIP] $name already running on PID $oldpid"
      return
    else
      rm -f "$pidfile"
    fi
  fi

  echo "[START] $name on port $port"
  (
    cd "$workdir"
    source .venv/bin/activate
    nohup env PYTHONPATH=. uvicorn "$app" --host 127.0.0.1 --port "$port" > "$logfile" 2>&1 &
    echo $! > "$pidfile"
  )

  sleep 1
  local newpid
  newpid="$(cat "$pidfile")"
  if kill -0 "$newpid" 2>/dev/null; then
    echo "[OK] $name started with PID $newpid"
  else
    echo "[FAIL] $name failed to start. Check $logfile"
    exit 1
  fi
}

start_service "inventory-service" "$ROOT/services/inventory-service" "8001" "app.main:app"
start_service "risk-engine" "$ROOT/services/risk-engine" "8002" "app.main:app"
start_service "copilot-service" "$ROOT/services/copilot-service" "8003" "app.main:app"
start_service "planner-service" "$ROOT/services/planner-service" "8004" "app.main:app"
start_service "workflow-service" "$ROOT/services/workflow-service" "8005" "app.main:app"
start_service "retrieval-service" "$ROOT/services/retrieval-service" "8006" "app.main:app"
start_service "dashboard-ui" "$ROOT/services/dashboard-ui" "8010" "app.main:app"

echo
echo "All services started."
echo "Dashboard: http://127.0.0.1:8010"
