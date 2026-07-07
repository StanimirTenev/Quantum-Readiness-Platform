#!/usr/bin/env bash
# Linux/CI-friendly port of run_windows_evidence_smoke.ps1.
#
# Starts risk-engine, inventory-service (on an isolated temporary database),
# planner-service and the api-gateway, then drives the committed Windows
# evidence fixture (and a few in-memory variants of it) through
# POST /api/scans/windows. Asserts the same checks as the PowerShell version:
# persistence, aggregate normalized signals, no raw-identifier leakage,
# Windows-aware risk factors, and planner wave-1 prioritization.
# Deterministic/fixture-based (does not require a live Windows host).
#
# Writes reports/windows-evidence-smoke-report.md and exits non-zero on
# any check failure.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
GATEWAY_BASE="http://127.0.0.1:8000"
INVENTORY_BASE="http://127.0.0.1:8001"
PLANNER_BASE="http://127.0.0.1:8004"
FIXTURE_PATH="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/windows_enriched_ingest_example.json"
REPORT_PATH="$ROOT_DIR/reports/windows-evidence-smoke-report.md"

RUN_DIR="$(mktemp -d)"
LOG_DIR="$RUN_DIR/logs"
mkdir -p "$LOG_DIR"
export INVENTORY_DB_PATH="$RUN_DIR/qrp-windows-smoke-inventory.db"
export RISK_ENGINE_URL="http://127.0.0.1:8002"
export INVENTORY_SERVICE_URL="http://127.0.0.1:8001"

declare -a SERVICE_PIDS=()
declare -a RESULT_NAMES=()
declare -a RESULT_STATUSES=()
declare -a RESULT_DETAILS=()

cleanup() {
    for pid in "${SERVICE_PIDS[@]:-}"; do
        [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
    done
    rm -rf "$RUN_DIR"
}
trap cleanup EXIT

start_service() {
    local name="$1" workdir="$2" port="$3" target="$4"
    (cd "$ROOT_DIR/$workdir" && exec "$PYTHON_BIN" -m uvicorn "$target" --host 127.0.0.1 --port "$port" \
        >"$LOG_DIR/${name}.log" 2>&1) &
    SERVICE_PIDS+=("$!")
    echo "  started $name (PID $!, port $port)"
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

record() {
    local name="$1" status="$2" detail="${3:-}"
    RESULT_NAMES+=("$name")
    RESULT_STATUSES+=("$status")
    RESULT_DETAILS+=("$detail")
    if [[ "$status" == "PASS" ]]; then
        echo "[PASS] $name"
    else
        echo "[FAIL] $name -> $detail"
    fi
}

run_check() {
    local check_id="$1"
    "$PYTHON_BIN" - "$FIXTURE_PATH" "$GATEWAY_BASE" "$INVENTORY_BASE" "$PLANNER_BASE" "$check_id" <<'PY'
import json
import sys
import urllib.error
import urllib.request

fixture_path, gateway_base, inventory_base, planner_base, check_id = sys.argv[1:6]


def load_fixture():
    with open(fixture_path, encoding="utf-8") as f:
        return json.load(f)


def post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def persist(doc):
    resp = post_json(f"{gateway_base}/api/scans/windows", doc)
    assert resp.get("created") == 1, f"expected created=1, got {resp.get('created')}"
    assert resp.get("source") == "host", f"expected source=host, got {resp.get('source')}"
    scan_id = resp.get("scan_id")
    assert scan_id, "missing scan_id"
    return get_json(f"{inventory_base}/scans/{scan_id}")


def set_cert_store(doc, count, expired, weak):
    csi = doc["windows_evidence"]["certificate_store_indicators"]
    csi["certificates_observed_count"] = count
    csi["expired_certificates_count"] = expired
    csi["weak_signature_indicators_count"] = weak


try:
    if check_id == "persist_single_asset":
        detail = persist(load_fixture())
        assert detail["scan"]["source"] == "host", f"source={detail['scan']['source']}"

    elif check_id == "aggregate_signals":
        detail = persist(load_fixture())
        sig = detail["scan"]["crypto_evidence"]["windows_normalized_signals"]
        assert sig["certificates_observed_count"] == 12, f"certs={sig['certificates_observed_count']}"
        assert sig["domain_joined"] is True, f"domain_joined={sig['domain_joined']}"
        assert sig["private_keys_exported"] is False, f"private_keys_exported={sig['private_keys_exported']}"

    elif check_id == "no_leak":
        detail = persist(load_fixture())
        assets = get_json(f"{inventory_base}/assets")
        matching = [a for a in assets if a.get("name") == "redacted-windows-host"]
        assert len(matching) >= 1, "redacted asset missing"
        hostname = detail["scan"]["host_inventory"].get("hostname") if detail["scan"].get("host_inventory") else None
        assert not hostname, f"hostname leaked: {hostname}"
        ips = (detail["scan"].get("host_inventory") or {}).get("ips") or []
        assert len(ips) == 0, "ips leaked"

    elif check_id == "domain_joined_widens":
        detail = persist(load_fixture())
        r = detail["risks"][0]
        assert r is not None, "no risk persisted"
        assert r["rationale"]["blast_radius"] == 4, f"blast_radius={r['rationale']['blast_radius']}"
        assert r["rationale"]["migration_difficulty"] == 5, f"migration_difficulty={r['rationale']['migration_difficulty']}"

    elif check_id == "domain_controller_max":
        doc = load_fixture()
        doc["asset"]["asset_type"] = "server"
        doc["windows_evidence"]["machine_role_indicators"]["domain_controller_role_observed"] = True
        set_cert_store(doc, 80, 3, 2)
        detail = persist(doc)
        r = detail["risks"][0]
        assert r["rationale"]["blast_radius"] == 5, f"blast_radius={r['rationale']['blast_radius']}"
        assert r["rationale"]["migration_difficulty"] == 5, f"migration_difficulty={r['rationale']['migration_difficulty']}"

    elif check_id == "standalone_clean":
        doc = load_fixture()
        doc["windows_evidence"]["domain_membership_indicators"]["domain_joined"] = False
        doc["windows_evidence"]["machine_role_indicators"]["domain_controller_role_observed"] = False
        set_cert_store(doc, 3, 0, 0)
        detail = persist(doc)
        r = detail["risks"][0]
        assert r["rationale"]["blast_radius"] == 3, f"blast_radius={r['rationale']['blast_radius']}"
        assert r["rationale"]["migration_difficulty"] == 3, f"migration_difficulty={r['rationale']['migration_difficulty']}"

    elif check_id == "planner_wave1":
        plan = get_json(f"{planner_base}/plan")
        item = next((i for i in plan.get("wave_1", []) if i.get("asset_name") == "redacted-windows-host"), None)
        assert item is not None, "redacted-windows-host not in wave_1"
        reasons = item.get("planning_reasons") or []
        assert "windows_expired_certificates" in reasons, f"missing windows planning reason: {','.join(reasons)}"

    else:
        raise SystemExit(f"unknown check_id: {check_id}")

    print("PASS")
except AssertionError as exc:
    print(f"FAIL: {exc}")
    sys.exit(1)
except (urllib.error.URLError, urllib.error.HTTPError, OSError) as exc:
    print(f"FAIL: {exc}")
    sys.exit(1)
PY
}

check() {
    local name="$1" check_id="$2"
    local output
    if output="$(run_check "$check_id" 2>&1)"; then
        record "$name" "PASS" ""
    else
        record "$name" "FAIL" "${output#FAIL: }"
    fi
}

echo "== Starting services =="
rm -f "$INVENTORY_DB_PATH"
start_service "risk-engine" "services/risk-engine" 8002 "app.main:app"
start_service "inventory-service" "services/inventory-service" 8001 "app.main:app"
start_service "planner-service" "services/planner-service" 8004 "app.main:app"
start_service "api-gateway" "services/api-gateway" 8000 "main:app"

echo "== Waiting for health =="
overall="PASS"
for entry in "risk-engine:8002" "inventory-service:8001" "planner-service:8004" "api-gateway:8000"; do
    name="${entry%%:*}"
    port="${entry##*:}"
    if wait_health "$port"; then
        echo "  healthy: $name"
    else
        echo "Service '$name' did not become healthy" >&2
        overall="FAIL"
    fi
done

if [[ "$overall" == "PASS" ]]; then
    echo "== Running checks =="
    if [[ ! -f "$FIXTURE_PATH" ]]; then
        echo "fixture not found: $FIXTURE_PATH" >&2
        overall="FAIL"
    else
        check "fixture persists as a host scan with a single asset" "persist_single_asset"
        check "stored scan carries the aggregate normalized signals" "aggregate_signals"
        check "no raw identifiers leak into the persisted scan" "no_leak"
        check "domain-joined host widens blast radius and migration difficulty" "domain_joined_widens"
        check "domain controller maximizes blast radius" "domain_controller_max"
        check "standalone host with a small clean store keeps base factors" "standalone_clean"
        check "planner places the Windows host in wave 1 with Windows reasons" "planner_wave1"
    fi
fi

passed=0
failed=0
for status in "${RESULT_STATUSES[@]:-}"; do
    if [[ "$status" == "PASS" ]]; then
        passed=$((passed + 1))
    elif [[ "$status" == "FAIL" ]]; then
        failed=$((failed + 1))
    fi
done
if [[ $failed -gt 0 || $passed -eq 0 ]]; then
    overall="FAIL"
fi

echo ""
echo "== Summary: $overall ($passed passed, $failed failed) =="

mkdir -p "$ROOT_DIR/reports"
{
    echo "# Windows Evidence Smoke Report"
    echo ""
    echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo ""
    echo "Scope: Windows evidence -> inventory persistence + Windows-aware risk"
    echo "scoring + planner wave prioritization, exercised through api-gateway"
    echo "and planner-service with an isolated database."
    echo ""
    echo "| Check | Result |"
    echo "| --- | --- |"
    for i in "${!RESULT_NAMES[@]}"; do
        name="${RESULT_NAMES[$i]}"
        status="${RESULT_STATUSES[$i]}"
        detail="${RESULT_DETAILS[$i]}"
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
