#!/usr/bin/env bash
# Product stack wiring smoke test: verifies retrieval-service and
# copilot-service are properly wired into start_all.sh / stop_all.sh /
# status_all.sh and reachable through api-gateway's copilot routes.
#
# Uses scripts/start_all.sh / stop_all.sh / status_all.sh directly (this is
# specifically testing that wiring, not a bespoke reimplementation of it),
# with an isolated INVENTORY_DB_PATH so it never touches the persistent dev
# database. Any already-running stack is stopped first, since start_all.sh
# skips already-healthy services and would otherwise bypass the isolated DB.
#
# Writes reports/product-stack-smoke-report.md and exits non-zero on any
# check failure.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATEWAY_BASE="http://127.0.0.1:8000"
RETRIEVAL_BASE="http://127.0.0.1:8015"
COPILOT_BASE="http://127.0.0.1:8008"
REPORT_PATH="$ROOT_DIR/reports/product-stack-smoke-report.md"

RUN_DB="$(mktemp -u /tmp/qrp-product-stack-smoke-XXXXXX).db"
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

cleanup() {
    bash "$ROOT_DIR/scripts/stop_all.sh" >/dev/null 2>&1 || true
    rm -f "$RUN_DB"
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

echo "== Checking status_all.sh reports retrieval + copilot RUNNING =="
status_output="$(bash "$ROOT_DIR/scripts/status_all.sh" 2>&1)"
if echo "$status_output" | grep -q '\[RUNNING\] retrieval-service'; then
    record "status_all.sh reports retrieval-service RUNNING" "PASS" ""
else
    record "status_all.sh reports retrieval-service RUNNING" "FAIL" "$(echo "$status_output" | grep retrieval-service || true)"
fi
if echo "$status_output" | grep -q '\[RUNNING\] copilot-service'; then
    record "status_all.sh reports copilot-service RUNNING" "PASS" ""
else
    record "status_all.sh reports copilot-service RUNNING" "FAIL" "$(echo "$status_output" | grep copilot-service || true)"
fi

ASSET_NAME="api.example.internal:443"

echo "== Seeding a fixture scan/risk =="
FIXTURE="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json"
ingest_response="$(curl -sS -f -X POST "http://127.0.0.1:8001/scans/ingest?scenario=public_timeline" -H "Content-Type: application/json" --data-binary "@$FIXTURE" 2>&1)" || true
if echo "$ingest_response" | grep -q '"scan_id"'; then
    record "seed fixture scan/risk into inventory" "PASS" ""
else
    record "seed fixture scan/risk into inventory" "FAIL" "ingest did not return a scan_id"
fi

echo "== Querying retrieval-service for the seeded asset =="
retrieval_response="$(curl -sS -f "$RETRIEVAL_BASE/asset?asset_name=$ASSET_NAME" 2>&1)" || true
if echo "$retrieval_response" | grep -q "$ASSET_NAME"; then
    record "retrieval-service returns the seeded asset" "PASS" ""
else
    record "retrieval-service returns the seeded asset" "FAIL" "asset not found in retrieval response"
fi

echo "== Asking Risk Narrator through the gateway =="
narrate_response="$(curl -sS -f "$GATEWAY_BASE/api/copilot/narrate/$ASSET_NAME" 2>&1)" || true
if echo "$narrate_response" | grep -qi "is rated"; then
    record "gateway /api/copilot/narrate returns a real narrative" "PASS" ""
else
    record "gateway /api/copilot/narrate returns a real narrative" "FAIL" "no narrative text in response"
fi

echo "== Verifying no external LLM call is possible =="
copilot_query_response="$(curl -sS -f -X POST "$COPILOT_BASE/copilot/query" -H "Content-Type: application/json" -d '{"query": "hello"}' 2>&1)" || true
if echo "$copilot_query_response" | grep -q '"provider_mode":"disabled"' && echo "$copilot_query_response" | grep -q '"used_external_provider":false'; then
    record "copilot LLM provider stays disabled (no external call possible)" "PASS" ""
else
    record "copilot LLM provider stays disabled (no external call possible)" "FAIL" "provider_mode was not disabled"
fi

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
    echo "# Product Stack Smoke Report"
    echo ""
    echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo ""
    echo "Scope: retrieval-service + copilot-service wired into start_all.sh /"
    echo "stop_all.sh / status_all.sh, gateway copilot routes, and the Copilot"
    echo "disabled-provider safety boundary -- exercised with an isolated"
    echo "inventory DB."
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
