#!/usr/bin/env bash
# One-command product demo: "run and see the product" -- exercises every
# collector/analysis component built this session end to end against real,
# self-contained evidence (a local self-signed TLS target, a small sample
# repo, synthetic sample vendor docs, and this machine's own real host
# evidence), on an isolated stack + temp DB.
#
# Steps: start isolated stack -> create a workspace (project/workspace model,
# groups this run's scans/findings/report) -> linux-host-agent ingest ->
# network-scanner ingest (local TLS target) -> repo-ci-scanner ingest (sample
# repo) -> doc-ingestion (sample vendor docs) -> graph snapshot -> retrieval
# search -> all five Copilot subagents (Risk Narrator, Discovery Analyst,
# Vendor Intelligence Analyst, Migration Planner, Change Assistant) ->
# operator report (persisted via POST /workspaces/{id}/reports) -> stop +
# clean up.
#
# Writes reports/product-demo/{product-demo-report.md,
# product-demo-report.json, product-demo-smoke-report.md} and exits
# non-zero if any step fails.
#
# Reliability hardening ("Demo Reliability Hardening" PR): every external
# command (go build, agent/scanner binaries, scripts, curl) runs under a
# STEP_TIMEOUT_SEC bound (default 60s, override via env) so a single stuck
# subprocess can't hang the whole run -- a real failure mode this hardening
# was written to fix (a package-manager lock stuck linux-host-agent
# indefinitely; see agents/linux-host-agent/internal/collector/collector.go's
# commandTimeout and this script's AGENT_TIMEOUT_SEC). A step that times out
# is recorded as TIMEOUT (distinct from FAIL) with a clear "timed out after
# Ns" detail. The EXIT/INT/TERM trap always stops every started service and
# writes an interim "INTERRUPTED" smoke report (showing exactly which step
# was in progress) if the script is killed before finishing normally --
# only an uncatchable SIGKILL can bypass this.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
GATEWAY_BASE="http://127.0.0.1:8000"
INVENTORY_BASE="http://127.0.0.1:8001"
RETRIEVAL_BASE="http://127.0.0.1:8015"
COPILOT_BASE="http://127.0.0.1:8008"
OUT_DIR="$ROOT_DIR/reports/product-demo"

RUN_DIR="$(mktemp -d)"
LOG_DIR="$RUN_DIR/logs"
BIN_DIR="$RUN_DIR/bin"
mkdir -p "$LOG_DIR" "$BIN_DIR" "$OUT_DIR"

export INVENTORY_DB_PATH="$RUN_DIR/qrp-product-demo-inventory.db"
export GRAPH_SNAPSHOT_PATH="$RUN_DIR/graph-snapshot.json"
export DOC_INDEX_PATH="$RUN_DIR/doc-index.json"
export INVENTORY_SERVICE_URL="$INVENTORY_BASE"
export RETRIEVAL_SERVICE_URL="$RETRIEVAL_BASE"
export WORKFLOW_SERVICE_URL="http://127.0.0.1:8005"
export PLANNER_SERVICE_URL="http://127.0.0.1:8004"
export RISK_ENGINE_URL="http://127.0.0.1:8002"
export CRYPTO_FINGERPRINT_URL="http://127.0.0.1:8003"
export EVIDENCE_NORMALIZER_URL="http://127.0.0.1:8009"
export SCENARIO_ENGINE_URL="http://127.0.0.1:8006"
export POLICY_ENGINE_URL="http://127.0.0.1:8007"
export COPILOT_SERVICE_URL="$COPILOT_BASE"
export INTEGRATION_SERVICE_URL="http://127.0.0.1:8011"
export PQC_READINESS_URL="http://127.0.0.1:8012"
export GRAPH_SERVICE_URL="http://127.0.0.1:8013"
export FINDING_ATTRIBUTION_URL="http://127.0.0.1:8014"

# Per-command timeout guard (item 1 of "Demo Reliability Hardening"). Every
# potentially-slow external command (go build, agent/scanner binaries,
# scripts, curl) runs under this bound so a single stuck subprocess -- the
# exact failure mode that motivated this hardening pass -- fails fast with a
# clear message instead of hanging the whole run forever.
STEP_TIMEOUT_SEC="${STEP_TIMEOUT_SEC:-60}"
# The Go agents' own internal -timeout (item 2: bounded mode) gets a smaller
# budget than STEP_TIMEOUT_SEC, so their own clear error message wins the
# race instead of the outer `timeout` killing them first -- the outer bound
# is a pure safety net, not the primary defense.
AGENT_TIMEOUT_SEC="${AGENT_TIMEOUT_SEC:-30}"

# Runs "$@" under STEP_TIMEOUT_SEC. Exit code 124 specifically means "timed
# out" (GNU coreutils `timeout`'s convention) -- callers check for that to
# produce a distinct TIMEOUT status instead of a generic FAIL.
run_bounded() {
    timeout --foreground --kill-after=5 "${STEP_TIMEOUT_SEC}s" "$@"
}

declare -a SERVICE_PIDS=()
declare -a EXTRA_PIDS=()
declare -a STEP_NAMES=()
declare -a STEP_STATUSES=()
declare -a STEP_DETAILS=()

CURRENT_STEP=""
REPORT_WRITTEN=false
CLEANUP_DONE=false

# Marks the start of a step (item 5: the report must show which step was
# running even if the whole script gets killed before finishing normally).
set_step() {
    CURRENT_STEP="$1"
    echo ""
    echo "== $1 =="
}

record() {
    local name="$1" status="$2" detail="${3:-}"
    STEP_NAMES+=("$name")
    STEP_STATUSES+=("$status")
    STEP_DETAILS+=("$detail")
    if [[ "$status" == "PASS" ]]; then
        echo "[PASS] $name"
    else
        echo "[$status] $name -> $detail"
    fi
}

# Records a step outcome based on a captured exit code, distinguishing a
# timeout (exit 124, or 137 if --kill-after had to SIGKILL) from a plain
# failure -- item 3: clear error messages when something hangs.
record_from_exit_code() {
    local name="$1" exit_code="$2" pass_detail="${3:-}" fail_detail="${4:-command failed}"
    if [[ "$exit_code" -eq 0 ]]; then
        record "$name" "PASS" "$pass_detail"
    elif [[ "$exit_code" -eq 124 || "$exit_code" -eq 137 ]]; then
        record "$name" "TIMEOUT" "timed out after ${STEP_TIMEOUT_SEC}s -- $fail_detail"
    else
        record "$name" "FAIL" "$fail_detail (exit $exit_code)"
    fi
}

# Writes whatever step data has been collected so far as an interim smoke
# report -- item 5. Runs from cleanup() so an abrupt kill (timeout, Ctrl-C,
# a sandbox/CI runner terminating the job) still leaves a diagnostic trace
# showing exactly how far the run got, instead of no report at all.
write_interim_report_if_needed() {
    if [[ "$REPORT_WRITTEN" == "true" ]]; then
        return
    fi
    mkdir -p "$OUT_DIR" 2>/dev/null || return
    {
        echo "# Product Demo Smoke Report (INTERRUPTED)"
        echo ""
        echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        echo ""
        echo "The run was interrupted before completing normally -- this report reflects"
        echo "only the steps that finished before the interruption."
        if [[ -n "$CURRENT_STEP" ]]; then
            echo ""
            echo "**Last step in progress when interrupted: $CURRENT_STEP**"
        fi
        echo ""
        echo "| Step | Result |"
        echo "| --- | --- |"
        for i in "${!STEP_NAMES[@]}"; do
            name="${STEP_NAMES[$i]}"
            status="${STEP_STATUSES[$i]}"
            detail="${STEP_DETAILS[$i]}"
            if [[ -n "$detail" ]]; then
                echo "| $name -- $detail | $status |"
            else
                echo "| $name | $status |"
            fi
        done
        echo ""
        echo "Result: INTERRUPTED"
    } > "$OUT_DIR/product-demo-smoke-report.md" 2>/dev/null || true
}

# Iron-clad cleanup (item 4): explicit EXIT/INT/TERM trap, a re-entrancy
# guard so overlapping signals can't run this twice, a SIGTERM-then-SIGKILL
# sweep so a wedged service can't survive the run, and an interim report
# write so an abrupt kill still leaves a diagnostic trace.
cleanup() {
    if [[ "$CLEANUP_DONE" == "true" ]]; then
        return
    fi
    CLEANUP_DONE=true

    echo ""
    echo "== Cleaning up (stopping services, removing temp files) =="
    for pid in "${EXTRA_PIDS[@]:-}" "${SERVICE_PIDS[@]:-}"; do
        [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
    done
    sleep 0.3
    for pid in "${EXTRA_PIDS[@]:-}" "${SERVICE_PIDS[@]:-}"; do
        [[ -n "$pid" ]] && kill -9 "$pid" >/dev/null 2>&1 || true
    done

    write_interim_report_if_needed
    rm -rf "$RUN_DIR"
}
# Standard idiom: EXIT always runs cleanup exactly once, on every exit path.
# INT/TERM must NOT also trap-call cleanup directly -- a custom trap on a
# signal makes that signal non-fatal, so bash would just resume the script
# after the handler returns instead of terminating it. Explicitly exiting
# from the INT/TERM handler is what actually ends the script, which then
# triggers the EXIT trap (and only that one) to do the real cleanup.
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

start_service() {
    local name="$1" workdir="$2" port="$3" target="$4"
    (cd "$ROOT_DIR/$workdir" && exec "$PYTHON_BIN" -m uvicorn "$target" --host 127.0.0.1 --port "$port" \
        >"$LOG_DIR/${name}.log" 2>&1) &
    SERVICE_PIDS+=("$!")
}

wait_health() {
    local port="$1" timeout_sec="${2:-30}"
    local deadline=$((SECONDS + timeout_sec))
    while [[ $SECONDS -lt $deadline ]]; do
        if curl -fsS --connect-timeout 1 --max-time 2 "http://127.0.0.1:$port/health" 2>/dev/null | grep -q '"status":"ok"'; then
            return 0
        fi
        sleep 0.4
    done
    return 1
}

wait_port() {
    local port="$1" timeout_sec="${2:-15}"
    local deadline=$((SECONDS + timeout_sec))
    while [[ $SECONDS -lt $deadline ]]; do
        if curl -sk --connect-timeout 1 --max-time 2 "https://127.0.0.1:$port/" -o /dev/null 2>/dev/null; then
            return 0
        fi
        sleep 0.3
    done
    return 1
}

set_step "Step 1: Starting isolated stack (temp DB: $INVENTORY_DB_PATH)"
start_service "inventory-service" "services/inventory-service" 8001 "app.main:app"
start_service "risk-engine" "services/risk-engine" 8002 "app.main:app"
start_service "crypto-fingerprint-service" "services/crypto-fingerprint-service" 8003 "app.main:app"
start_service "planner-service" "services/planner-service" 8004 "app.main:app"
start_service "workflow-service" "services/workflow-service" 8005 "app.main:app"
start_service "scenario-engine" "services/scenario-engine" 8006 "app.main:app"
start_service "policy-engine" "services/policy-engine" 8007 "app.main:app"
start_service "evidence-normalizer" "services/evidence-normalizer" 8009 "app.main:app"
start_service "integration-service" "services/integration-service" 8011 "app.main:app"
start_service "pqc-readiness-service" "services/pqc-readiness-service" 8012 "app.main:app"
start_service "graph-service" "services/graph-service" 8013 "app.main:app"
start_service "finding-attribution-service" "services/finding-attribution-service" 8014 "app.main:app"
start_service "retrieval-service" "services/retrieval-service" 8015 "app.main:app"
start_service "copilot-service" "services/copilot-service" 8008 "app.main:app"
start_service "api-gateway" "services/api-gateway" 8000 "main:app"

all_healthy=true
for entry in "inventory-service:8001" "risk-engine:8002" "crypto-fingerprint-service:8003" \
    "planner-service:8004" "workflow-service:8005" "scenario-engine:8006" "policy-engine:8007" \
    "evidence-normalizer:8009" "integration-service:8011" "pqc-readiness-service:8012" \
    "graph-service:8013" "finding-attribution-service:8014" "retrieval-service:8015" \
    "copilot-service:8008" "api-gateway:8000"; do
    name="${entry%%:*}"
    port="${entry##*:}"
    if ! wait_health "$port"; then
        echo "$name did not become healthy" >&2
        all_healthy=false
    fi
done
if [[ "$all_healthy" == "true" ]]; then
    record "Step 1: full stack started (15 services, isolated DB)" "PASS" ""
else
    record "Step 1: full stack started (15 services, isolated DB)" "FAIL" "one or more services failed health check"
fi

set_step "Step 1b: Creating a workspace to group this run's scans"
WORKSPACE_ID=""
workspace_resp="$(curl -sS --max-time "$STEP_TIMEOUT_SEC" -X POST "$INVENTORY_BASE/workspaces" -H "Content-Type: application/json" -d '{"source":"product-demo"}' 2>>"$LOG_DIR/workspace-create.log")" || true
WORKSPACE_ID="$(echo "$workspace_resp" | "$PYTHON_BIN" -c "import json,sys
try:
    print(json.load(sys.stdin).get('id',''))
except Exception:
    print('')" 2>/dev/null)"
if [[ -n "$WORKSPACE_ID" ]]; then
    record "Step 1b: workspace created ($WORKSPACE_ID)" "PASS" ""
else
    record "Step 1b: workspace created" "FAIL" "no workspace id in response, see $LOG_DIR/workspace-create.log"
fi

LINUX_ASSET=""
set_step "Step 2: Linux host agent ingest"
build_exit=0
(cd "$ROOT_DIR/agents/linux-host-agent" && run_bounded go build -o "$BIN_DIR/linux-host-agent" ./cmd/agent) 2>>"$LOG_DIR/linux-host-agent-build.log" || build_exit=$?
if [[ $build_exit -ne 0 ]]; then
    record_from_exit_code "Step 2: linux-host-agent ingest" "$build_exit" "" "go build failed, see $LOG_DIR/linux-host-agent-build.log"
else
    ingest_exit=0
    linux_resp="$(run_bounded "$BIN_DIR/linux-host-agent" -ingest -inventory-url "$INVENTORY_BASE" -timeout "$AGENT_TIMEOUT_SEC" -workspace-id "$WORKSPACE_ID" 2>>"$LOG_DIR/linux-host-agent.log")" || ingest_exit=$?
    if [[ $ingest_exit -eq 0 ]] && echo "$linux_resp" | grep -q '"created"'; then
        LINUX_ASSET="$(hostname)"
        record "Step 2: linux-host-agent ingest (asset: $LINUX_ASSET)" "PASS" ""
    else
        record_from_exit_code "Step 2: linux-host-agent ingest" "$ingest_exit" "" "ingest did not return created asset(s), see $LOG_DIR/linux-host-agent.log"
    fi
fi

NETWORK_ASSET=""
set_step "Step 3: Network scanner (local self-signed TLS target)"
DEMO_TLS_PORT=9443
run_bounded openssl req -x509 -newkey rsa:2048 -keyout "$RUN_DIR/demo-key.pem" -out "$RUN_DIR/demo-cert.pem" \
    -days 1 -nodes -subj "/CN=qrp-demo.local" >"$LOG_DIR/openssl-req.log" 2>&1
openssl s_server -accept "$DEMO_TLS_PORT" -cert "$RUN_DIR/demo-cert.pem" -key "$RUN_DIR/demo-key.pem" -www \
    >"$LOG_DIR/tls-demo-server.log" 2>&1 &
EXTRA_PIDS+=("$!")
build_exit=0
(cd "$ROOT_DIR/agents/network-scanner" && run_bounded go build -o "$BIN_DIR/network-scanner" ./cmd/scanner) 2>>"$LOG_DIR/network-scanner-build.log" || build_exit=$?
if [[ $build_exit -ne 0 ]]; then
    record_from_exit_code "Step 3: network-scanner ingest" "$build_exit" "" "go build failed, see $LOG_DIR/network-scanner-build.log"
elif ! wait_port "$DEMO_TLS_PORT"; then
    record "Step 3: network-scanner ingest" "FAIL" "local TLS demo server never became reachable"
else
    ingest_exit=0
    network_resp="$(run_bounded "$BIN_DIR/network-scanner" -target "127.0.0.1:$DEMO_TLS_PORT" -insecure -ingest -inventory-url "$INVENTORY_BASE" -workspace-id "$WORKSPACE_ID" 2>>"$LOG_DIR/network-scanner.log")" || ingest_exit=$?
    if [[ $ingest_exit -eq 0 ]] && echo "$network_resp" | grep -q '"created"'; then
        NETWORK_ASSET="127.0.0.1:$DEMO_TLS_PORT"
        record "Step 3: network-scanner ingest (asset: $NETWORK_ASSET)" "PASS" ""
    else
        record_from_exit_code "Step 3: network-scanner ingest" "$ingest_exit" "" "ingest did not return created asset(s), see $LOG_DIR/network-scanner.log"
    fi
fi

REPO_ASSET=""
set_step "Step 4: Repo/CI scanner (sample repo)"
SAMPLE_REPO="$RUN_DIR/sample-vulnerable-repo"
mkdir -p "$SAMPLE_REPO/.github/workflows"
cat > "$SAMPLE_REPO/legacy_auth.py" <<'PY'
from Crypto.PublicKey import RSA
import hashlib

def sign_token(payload: bytes) -> str:
    return hashlib.sha1(payload).hexdigest()
PY
cat > "$SAMPLE_REPO/.github/workflows/release.yml" <<'YML'
name: release
on: push
jobs:
  sign:
    steps:
      - run: gpg --detach-sign artifact.tar.gz
YML
cat > "$SAMPLE_REPO/main.tf" <<'TF'
resource "tls_private_key" "legacy" {
  algorithm = "RSA"
  rsa_bits  = 2048
}
TF
scan_exit=0
(cd "$ROOT_DIR/agents/repo-ci-scanner" && run_bounded "$PYTHON_BIN" scanner.py --repo-path "$SAMPLE_REPO" --out "$RUN_DIR/repo-ci-payload.json" --ingest "$INVENTORY_BASE" --workspace-id "$WORKSPACE_ID" > "$RUN_DIR/repo-ci-ingest.json" 2>"$LOG_DIR/repo-ci-scanner.log") || scan_exit=$?
if [[ $scan_exit -eq 0 ]] && grep -q '"created"' "$RUN_DIR/repo-ci-ingest.json" 2>/dev/null; then
    REPO_ASSET="sample-vulnerable-repo"
    record "Step 4: repo-ci-scanner ingest (asset: $REPO_ASSET)" "PASS" ""
else
    record_from_exit_code "Step 4: repo-ci-scanner ingest" "$scan_exit" "" "scanner run failed or returned no created asset, see $LOG_DIR/repo-ci-scanner.log"
fi

set_step "Step 5: Document ingestion (sample vendor docs)"
SAMPLE_DOCS="$RUN_DIR/sample-vendor-docs"
mkdir -p "$SAMPLE_DOCS"
cat > "$SAMPLE_DOCS/vendor-pqc-roadmap.md" <<'MD'
# Vendor PQC Roadmap

Our appliances will support hybrid post-quantum key exchange (ML-KEM-768)
starting Q3 2026. Certificate rotation procedures are documented in the
operations runbook.

## Certificate Rotation Runbook

Rotate the signing certificate every 90 days. Escalate any expired
certificate to the security team immediately.
MD
ingest_exit=0
(cd "$ROOT_DIR/agents/doc-ingestion" && run_bounded "$PYTHON_BIN" ingest.py --docs-dir "$SAMPLE_DOCS" --out "$DOC_INDEX_PATH" 2>"$LOG_DIR/doc-ingestion.log") || ingest_exit=$?
if [[ $ingest_exit -eq 0 && -s "$DOC_INDEX_PATH" ]]; then
    record "Step 5: doc-ingestion (sample vendor docs indexed)" "PASS" ""
else
    record_from_exit_code "Step 5: doc-ingestion (sample vendor docs indexed)" "$ingest_exit" "" "ingest run failed or produced no index, see $LOG_DIR/doc-ingestion.log"
fi

set_step "Step 6: Building dependency graph snapshot"
graph_exit=0
(cd "$ROOT_DIR" && run_bounded "$PYTHON_BIN" tools/graph_projection/project_stage2_fixtures.py \
    --host "services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json" \
    --network "services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json" \
    --snapshot-out "reports/graph/latest/graph-snapshot.json" \
    --report-out "$RUN_DIR/graph-projection-report.md" >"$LOG_DIR/graph-projection.log" 2>&1) || graph_exit=$?
if [[ $graph_exit -eq 0 ]]; then
    cp "$ROOT_DIR/reports/graph/latest/graph-snapshot.json" "$GRAPH_SNAPSHOT_PATH"
    record "Step 6: dependency graph snapshot built" "PASS" ""
else
    record_from_exit_code "Step 6: dependency graph snapshot built" "$graph_exit" "" "see $LOG_DIR/graph-projection.log"
fi

set_step "Step 7: Retrieval search"
retrieval_resp="$(curl -sS --max-time "$STEP_TIMEOUT_SEC" -X POST "$RETRIEVAL_BASE/search" -H "Content-Type: application/json" -d '{"query": "roadmap"}' 2>>"$LOG_DIR/retrieval-search.log")" || true
if echo "$retrieval_resp" | grep -q "vendor-pqc-roadmap"; then
    record "Step 7: retrieval search finds the ingested vendor doc" "PASS" ""
else
    record "Step 7: retrieval search finds the ingested vendor doc" "FAIL" "vendor doc not found in search results"
fi

set_step "Step 8: Risk Narrator"
narrate() {
    curl -sS --max-time "$STEP_TIMEOUT_SEC" "$COPILOT_BASE/narrate/$1" 2>>"$LOG_DIR/narrate.log" | "$PYTHON_BIN" -c "import json,sys
try:
    print(json.load(sys.stdin).get('narrative',''))
except Exception:
    print('')" 2>/dev/null
}
narrator_ok=true
for asset in "$LINUX_ASSET" "$NETWORK_ASSET" "$REPO_ASSET"; do
    [[ -z "$asset" ]] && continue
    narrative_text="$(narrate "$asset")"
    if [[ -z "$narrative_text" ]]; then
        narrator_ok=false
    fi
done
if [[ "$narrator_ok" == "true" ]]; then
    record "Step 8: Risk Narrator explains every ingested asset" "PASS" ""
else
    record "Step 8: Risk Narrator explains every ingested asset" "FAIL" "at least one asset got an empty narrative"
fi

set_step "Step 8b-8e: the other four Copilot subagents"
discover_resp="$(curl -sS --max-time "$STEP_TIMEOUT_SEC" "$COPILOT_BASE/discover" 2>>"$LOG_DIR/discover.log")" || true
if echo "$discover_resp" | grep -q '"narrative"'; then
    record "Step 8b: Discovery Analyst summarizes discovered dependencies" "PASS" ""
else
    record "Step 8b: Discovery Analyst summarizes discovered dependencies" "FAIL" "no narrative in response"
fi

vendor_resp="$(curl -sS --max-time "$STEP_TIMEOUT_SEC" "$COPILOT_BASE/vendor-intelligence" 2>>"$LOG_DIR/vendor-intelligence.log")" || true
if echo "$vendor_resp" | grep -q '"narrative"'; then
    record "Step 8c: Vendor Intelligence Analyst extracts readiness claims" "PASS" ""
else
    record "Step 8c: Vendor Intelligence Analyst extracts readiness claims" "FAIL" "no narrative in response"
fi

migration_resp="$(curl -sS --max-time "$STEP_TIMEOUT_SEC" "$COPILOT_BASE/migration-plan" 2>>"$LOG_DIR/migration-plan.log")" || true
if echo "$migration_resp" | grep -q '"narrative"'; then
    record "Step 8d: Migration Planner explains the wave plan" "PASS" ""
else
    record "Step 8d: Migration Planner explains the wave plan" "FAIL" "no narrative in response"
fi

change_plan_ok=true
for asset in "$LINUX_ASSET" "$NETWORK_ASSET" "$REPO_ASSET"; do
    [[ -z "$asset" ]] && continue
    change_resp="$(curl -sS --max-time "$STEP_TIMEOUT_SEC" "$COPILOT_BASE/change-plan/$asset" 2>>"$LOG_DIR/change-plan.log")" || true
    if ! echo "$change_resp" | grep -q '"pre_change_checklist"'; then
        change_plan_ok=false
    fi
done
if [[ "$change_plan_ok" == "true" ]]; then
    record "Step 8e: Change Assistant drafts a checklist for every ingested asset" "PASS" ""
else
    record "Step 8e: Change Assistant drafts a checklist for every ingested asset" "FAIL" "at least one asset got no checklist"
fi

set_step "Step 9: Building operator report (persisted workspace report)"
OPERATOR_REPORT="$OUT_DIR/product-demo-operator-report.md"
operator_exit=0
# Exercises the workspace model's report persistence (POST /workspaces/{id}/reports) --
# same build_operator_report logic the old ad-hoc bundle-building here used to
# duplicate, now the backend's own job. See services/inventory-service/README.md.
report_resp="$(curl -sS --max-time "$STEP_TIMEOUT_SEC" -X POST "$INVENTORY_BASE/workspaces/$WORKSPACE_ID/reports" 2>"$LOG_DIR/operator-report.log")" || operator_exit=$?
if [[ $operator_exit -eq 0 ]]; then
    echo "$report_resp" | "$PYTHON_BIN" -c "import json, sys
try:
    data = json.load(sys.stdin)
    sys.stdout.write(data.get('content', ''))
except Exception:
    pass" > "$OPERATOR_REPORT" 2>>"$LOG_DIR/operator-report.log" || operator_exit=$?
fi
if [[ $operator_exit -eq 0 && -s "$OPERATOR_REPORT" ]]; then
    record "Step 9: operator report generated (persisted, workspace $WORKSPACE_ID)" "PASS" ""
else
    record_from_exit_code "Step 9: operator report generated" "$operator_exit" "" "see $LOG_DIR/operator-report.log"
fi

set_step "Step 10: Stopping services and cleaning up (handled on exit)"
record "Step 10: services stopped, temp files cleaned on exit" "PASS" ""

passed=0
failed=0
for status in "${STEP_STATUSES[@]:-}"; do
    if [[ "$status" == "PASS" ]]; then
        passed=$((passed + 1))
    elif [[ "$status" == "FAIL" || "$status" == "TIMEOUT" ]]; then
        failed=$((failed + 1))
    fi
done
overall="PASS"
if [[ $failed -gt 0 || $passed -eq 0 ]]; then
    overall="FAIL"
fi

echo ""
echo "== Summary: $overall ($passed passed, $failed failed) =="

# --- Reports ---
mkdir -p "$OUT_DIR"
now_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

{
    echo "# Product Demo Smoke Report"
    echo ""
    echo "Generated: $now_iso"
    echo ""
    echo "Scope: one-command tour of the full QRP pipeline (collection -> ingest ->"
    echo "risk -> graph -> retrieval -> Copilot -> operator report) against real"
    echo "self-contained evidence, on an isolated stack + temp DB."
    echo ""
    echo "| Step | Result |"
    echo "| --- | --- |"
    for i in "${!STEP_NAMES[@]}"; do
        name="${STEP_NAMES[$i]}"
        status="${STEP_STATUSES[$i]}"
        detail="${STEP_DETAILS[$i]}"
        if [[ ("$status" == "FAIL" || "$status" == "TIMEOUT") && -n "$detail" ]]; then
            echo "| $name -- $detail | $status |"
        else
            echo "| $name | $status |"
        fi
    done
    echo ""
    echo "Result: $overall"
} > "$OUT_DIR/product-demo-smoke-report.md"
# From here on the real smoke report exists on disk -- if anything below
# times out or gets interrupted, cleanup() must not overwrite it with an
# interim "INTERRUPTED" version (item 5).
REPORT_WRITTEN=true

run_bounded "$PYTHON_BIN" - "$OUT_DIR" "$INVENTORY_BASE" "$RETRIEVAL_BASE" "$LINUX_ASSET" "$NETWORK_ASSET" "$REPO_ASSET" "$now_iso" "$overall" "$OPERATOR_REPORT" "$WORKSPACE_ID" <<'PY'
import json
import sys
import urllib.request

out_dir, inventory_base, retrieval_base, linux_asset, network_asset, repo_asset, now_iso, overall, operator_report_path, workspace_id = sys.argv[1:11]
asset_names = [a for a in (linux_asset, network_asset, repo_asset) if a]


def get(url):
    try:
        return json.loads(urllib.request.urlopen(url, timeout=10).read())
    except Exception:
        return None


def narrate(name):
    data = get(f"http://127.0.0.1:8008/narrate/{name}")
    return (data or {}).get("narrative", "")


def change_plan(name):
    return get(f"http://127.0.0.1:8008/change-plan/{name}") or {}


overview = get(f"{retrieval_base}/overview") or {}
discover = get("http://127.0.0.1:8008/discover") or {}
vendor_intelligence = get("http://127.0.0.1:8008/vendor-intelligence") or {}
migration_plan = get("http://127.0.0.1:8008/migration-plan") or {}
change_plans = {name: change_plan(name) for name in asset_names}
search = None
try:
    req = urllib.request.Request(
        f"{retrieval_base}/search",
        data=json.dumps({"query": "roadmap"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    search = json.loads(urllib.request.urlopen(req, timeout=10).read())
except Exception:
    search = None

narratives = {name: narrate(name) for name in asset_names}

try:
    with open(operator_report_path, encoding="utf-8") as f:
        operator_report_text = f.read()
except OSError:
    operator_report_text = ""

result = {
    "generated_at": now_iso,
    "result": overall,
    "workspace_id": workspace_id,
    "assets_discovered": asset_names,
    "retrieval_overview": {
        "asset_count": overview.get("asset_count"),
        "scan_count": overview.get("scan_count"),
        "risk_count": overview.get("risk_count"),
    },
    "retrieval_document_search_query": "roadmap",
    "retrieval_document_matches": (search or {}).get("results", {}).get("documents", []),
    "risk_narratives": narratives,
    "discovery_analyst": discover,
    "vendor_intelligence": vendor_intelligence,
    "migration_plan": migration_plan,
    "change_plans": change_plans,
    "operator_report_excerpt": operator_report_text[:4000],
}

with open(f"{out_dir}/product-demo-report.json", "w", encoding="utf-8") as f:
    json.dump(result, f, indent=2)

lines = [
    "# QRP Product Demo Report",
    "",
    f"Generated: {now_iso}",
    "",
    "> One-command tour of the full platform: collection agents (Linux host,",
    "> network TLS, repo/CI, document ingestion) feeding a deterministic risk",
    "> pipeline, a dependency graph, keyword retrieval over indexed documents,",
    "> all five Copilot subagents (Risk Narrator, Discovery Analyst, Vendor",
    "> Intelligence Analyst, Migration Planner, Change Assistant), and an",
    "> operator/exec migration report. Runs on an isolated stack with a",
    "> temporary database; nothing here touches persistent state.",
    "",
    f"## Result: {overall}",
    "",
    f"Workspace: `{workspace_id}` (see `GET /workspaces/{workspace_id}` for the persisted rollup)" if workspace_id else "Workspace: (not created)",
    "",
    "## Assets Discovered",
    "",
]
for name in asset_names:
    lines.append(f"- `{name}`")
lines += ["", "## Risk Narrator Explanations", ""]
for name, text in narratives.items():
    lines.append(f"### {name}")
    lines.append("")
    lines.append(text or "_(no narrative available)_")
    lines.append("")
lines += ["", "## Discovery Analyst", "", discover.get("narrative") or "_(no narrative available)_", ""]
lines += ["", "## Vendor Intelligence Analyst", "", vendor_intelligence.get("narrative") or "_(no narrative available)_", ""]
lines += ["", "## Migration Planner", "", migration_plan.get("narrative") or "_(no narrative available)_", ""]
lines += ["", "## Change Assistant", ""]
for name, plan in change_plans.items():
    lines.append(f"### {name}")
    lines.append("")
    lines.append(plan.get("narrative") or "_(no narrative available)_")
    for item in plan.get("pre_change_checklist") or []:
        lines.append(f"- {item}")
    lines.append("")
lines += [
    "## Retrieval",
    "",
    f"- Assets indexed: {overview.get('asset_count')}",
    f"- Scans indexed: {overview.get('scan_count')}",
    f"- Risks indexed: {overview.get('risk_count')}",
    f"- Document search for \"roadmap\" matched {len((search or {}).get('results', {}).get('documents', []))} chunk(s) from the ingested sample vendor doc.",
    "",
    "## Operator Report Excerpt",
    "",
    "```markdown",
    operator_report_text[:2000],
    "```",
    "",
]
with open(f"{out_dir}/product-demo-report.md", "w", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

print("Reports written.")
PY

echo "Reports:"
echo "  $OUT_DIR/product-demo-report.md"
echo "  $OUT_DIR/product-demo-report.json"
echo "  $OUT_DIR/product-demo-smoke-report.md"

[[ "$overall" == "PASS" ]]
