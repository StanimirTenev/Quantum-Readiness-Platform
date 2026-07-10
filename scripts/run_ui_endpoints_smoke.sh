#!/usr/bin/env bash
# UI-facing endpoints smoke test: exercises every gateway route
# frontend/web-ui/public/app.js actually calls, on a real full stack. This is
# what "Product Demo v2 / UI Demo Scenario" step 5 asked for -- not a
# reimplementation of the UI, but proof that every endpoint the UI depends on
# (demo load/status, assets, Copilot subagents, graph, fingerprint,
# scenarios, integrations, algorithms) is actually wired and responds.
#
# Uses scripts/start_all.sh / stop_all.sh directly with an isolated
# INVENTORY_DB_PATH, same pattern as run_product_stack_smoke.sh. Seeds data
# via POST /api/demo/load (the same endpoint the "Load Demo" button calls),
# not a hand-built fixture ingest -- so this also proves the demo-seed path
# itself works end to end.
#
# Writes reports/ui-endpoints-smoke-report.md and exits non-zero on any
# check failure.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATEWAY_BASE="http://127.0.0.1:8000"
REPORT_PATH="$ROOT_DIR/reports/ui-endpoints-smoke-report.md"

RUN_DB="$(mktemp -u /tmp/qrp-ui-endpoints-smoke-XXXXXX).db"
export INVENTORY_DB_PATH="$RUN_DB"

declare -a NAMES=()
declare -a STATUSES=()
declare -a DETAILS=()

record() {
    local name="$1" status="$2" detail="${3:-}"
    NAMES+=("$name")
    STATUSES+=("$status")
    DETAILS+=("$detail")
    if [[ "$status" == "PASS" ]]; then
        echo "[PASS] $name"
    else
        echo "[FAIL] $name -> $detail"
    fi
}

check_json_contains() {
    local name="$1" needle="$2" response="$3"
    if echo "$response" | grep -q "$needle"; then
        record "$name" "PASS" ""
    else
        record "$name" "FAIL" "response did not contain: $needle"
    fi
}

cleanup() {
    bash "$ROOT_DIR/scripts/stop_all.sh" >/dev/null 2>&1 || true
    rm -f "$RUN_DB"
    rm -f "$ROOT_DIR/reports/graph/latest/demo-load-graph-report.md"
}
trap cleanup EXIT

echo "== Ensuring a clean slate =="
bash "$ROOT_DIR/scripts/stop_all.sh" >/dev/null 2>&1 || true
rm -f "$RUN_DB"

echo "== Starting full stack (isolated DB: $RUN_DB) =="
if bash "$ROOT_DIR/scripts/start_all.sh"; then
    record "start_all.sh brings up the full stack" "PASS" ""
else
    record "start_all.sh brings up the full stack" "FAIL" "start_all.sh exited non-zero"
fi

echo "== Dashboard: Load Demo button (POST /api/demo/load) =="
load_response="$(curl -sS -f -X POST "$GATEWAY_BASE/api/demo/load" 2>&1)" || true
check_json_contains "POST /api/demo/load seeds host/network/repo/doc evidence" '"overall":"ok"' "$load_response"

echo "== Dashboard: Refresh demo status (GET /api/demo/status) =="
status_response="$(curl -sS -f "$GATEWAY_BASE/api/demo/status" 2>&1)" || true
check_json_contains "GET /api/demo/status reports loaded" '"loaded":true' "$status_response"

echo "== Dashboard/Reports: workspace model (project/workspace) =="
WORKSPACE_ID="$(echo "$status_response" | python3 -c "import json,sys
try:
    print(json.load(sys.stdin).get('workspace_id',''))
except Exception:
    print('')" 2>/dev/null)"
if [[ -n "$WORKSPACE_ID" ]]; then
    record "GET /api/demo/status reports a workspace_id" "PASS" ""
else
    record "GET /api/demo/status reports a workspace_id" "FAIL" "no workspace_id in response"
fi
workspace_response="$(curl -sS -f "$GATEWAY_BASE/api/workspaces/$WORKSPACE_ID" 2>&1)" || true
check_json_contains "GET /api/workspaces/{id} returns the rollup (scans/risks/reports)" '"scans"' "$workspace_response"
report_response="$(curl -sS -f -X POST "$GATEWAY_BASE/api/workspaces/$WORKSPACE_ID/reports" 2>&1)" || true
check_json_contains "POST /api/workspaces/{id}/reports persists an operator report" '"content"' "$report_response"
REPORT_ID="$(echo "$report_response" | python3 -c "import json,sys
try:
    print(json.load(sys.stdin).get('id',''))
except Exception:
    print('')" 2>/dev/null)"
fetched_report_response="$(curl -sS -f "$GATEWAY_BASE/api/reports/$REPORT_ID" 2>&1)" || true
check_json_contains "GET /api/reports/{id} fetches the persisted report back" '"content"' "$fetched_report_response"

echo "== Assets tab: asset list =="
assets_response="$(curl -sS -f "$GATEWAY_BASE/api/assets" 2>&1)" || true
check_json_contains "GET /api/assets returns the seeded assets" "qrp-linux-demo-01" "$assets_response"

echo "== Findings tab: Discovery Analyst findings =="
discover_response="$(curl -sS -f "$GATEWAY_BASE/api/copilot/discover" 2>&1)" || true
check_json_contains "GET /api/copilot/discover returns findings" '"explicit_findings"' "$discover_response"

echo "== Risk / Migration Plan tabs: Migration Planner waves =="
migration_response="$(curl -sS -f "$GATEWAY_BASE/api/copilot/migration-plan" 2>&1)" || true
check_json_contains "GET /api/copilot/migration-plan returns waves" '"waves"' "$migration_response"

echo "== Dependency graph summary (used by the graph tab) =="
graph_summary_response="$(curl -sS -f "$GATEWAY_BASE/graph/summary" 2>&1)" || true
check_json_contains "GET /graph/summary responds" '{' "$graph_summary_response"

echo "== Migration Plan tab: Vendor Intelligence Analyst =="
vendor_response="$(curl -sS -f "$GATEWAY_BASE/api/copilot/vendor-intelligence" 2>&1)" || true
check_json_contains "GET /api/copilot/vendor-intelligence returns readiness_matrix" '"readiness_matrix"' "$vendor_response"

echo "== Asset detail: Risk Narrator per asset =="
narrate_response="$(curl -sS -f "$GATEWAY_BASE/api/copilot/narrate/qrp-linux-demo-01" 2>&1)" || true
check_json_contains "GET /api/copilot/narrate/{asset} returns a narrative" '"narrative"' "$narrate_response"

echo "== Asset detail: Change Assistant checklist per asset =="
change_plan_response="$(curl -sS -f "$GATEWAY_BASE/api/copilot/change-plan/qrp-linux-demo-01" 2>&1)" || true
check_json_contains "GET /api/copilot/change-plan/{asset} returns a checklist" '"pre_change_checklist"' "$change_plan_response"

echo "== Dashboard / Reports tabs: operational summary =="
operational_response="$(curl -sS -f "$GATEWAY_BASE/api/copilot/operational-summary" 2>&1)" || true
check_json_contains "GET /api/copilot/operational-summary returns platform stats" '"platform"' "$operational_response"

echo "== Copilot tab: free-text query =="
query_response="$(curl -sS -f -X POST "$GATEWAY_BASE/api/copilot/query" -H "Content-Type: application/json" -d '{"question": "what crypto dependencies did we discover?"}' 2>&1)" || true
check_json_contains "POST /api/copilot/query answers a question" '"intent"' "$query_response"

echo "== Graph tab: nodes/edges/blast-radius =="
nodes_response="$(curl -sS -f "$GATEWAY_BASE/graph/nodes" 2>&1)" || true
check_json_contains "GET /graph/nodes responds" '"nodes"' "$nodes_response"
edges_response="$(curl -sS -f "$GATEWAY_BASE/graph/edges" 2>&1)" || true
check_json_contains "GET /graph/edges responds" '"edges"' "$edges_response"

echo "== Algorithms tab / Scenarios warm-connection =="
algorithms_response="$(curl -sS -f "$GATEWAY_BASE/api/algorithms" 2>&1)" || true
check_json_contains "GET /api/algorithms returns the reference knowledge base" '"algorithms"' "$algorithms_response"

echo "== Fingerprint tab: assess pipeline =="
assess_response="$(curl -sS -f -X POST "$GATEWAY_BASE/api/assess" -H "Content-Type: application/json" -d '{"asset_name":"ui-smoke-asset","algorithms":["RSA","ML-KEM-768"]}' 2>&1)" || true
check_json_contains "POST /api/assess returns a pqc_readiness verdict" '"pqc_readiness"' "$assess_response"

echo "== Scenarios tab: re-score =="
scenario_response="$(curl -sS -f -X POST "$GATEWAY_BASE/api/scenarios/run" -H "Content-Type: application/json" -d '{"scenario":"hidden_capability","assets":[{"asset_name":"ui-smoke-asset","base_score":3.0}]}' 2>&1)" || true
check_json_contains "POST /api/scenarios/run returns rescored results" '"results"' "$scenario_response"

echo "== Integrations tab: dry-run preview =="
integration_response="$(curl -sS -f -X POST "$GATEWAY_BASE/api/integrations/dry-run" -H "Content-Type: application/json" -d '{"action":"rotate_certificate","target_type":"ca","asset_name":"ui-smoke-asset","approved":true,"approvals_provided":["security_review","change_approval"]}' 2>&1)" || true
check_json_contains "POST /api/integrations/dry-run responds and stays disabled" '"executed":false' "$integration_response"

passed=0
failed=0
for status in "${STATUSES[@]:-}"; do
    if [[ "$status" == "PASS" ]]; then
        passed=$((passed + 1))
    elif [[ "$status" == "FAIL" ]]; then
        failed=$((failed + 1))
    fi
done
overall="PASS"
if [[ $failed -gt 0 || $passed -eq 0 ]]; then
    overall="FAIL"
fi

echo ""
echo "== Summary: $overall ($passed passed, $failed failed) =="

mkdir -p "$ROOT_DIR/reports"
{
    echo "# UI-Facing Endpoints Smoke Report"
    echo ""
    echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo ""
    echo "Scope: every gateway route frontend/web-ui/public/app.js calls,"
    echo "including the demo-load/demo-status endpoints behind the Dashboard's"
    echo "\"Load Demo\" / \"Refresh demo status\" buttons -- exercised on a real"
    echo "full stack with an isolated inventory DB."
    echo ""
    echo "| Check | Result |"
    echo "| --- | --- |"
    for i in "${!NAMES[@]}"; do
        name="${NAMES[$i]}"
        status="${STATUSES[$i]}"
        detail="${DETAILS[$i]}"
        if [[ "$status" == "FAIL" && -n "$detail" ]]; then
            echo "| $name -- $detail | $status |"
        else
            echo "| $name | $status |"
        fi
    done
    echo ""
    echo "Result: $overall"
} > "$REPORT_PATH"
echo "Report: $REPORT_PATH"

[[ "$overall" == "PASS" ]]
