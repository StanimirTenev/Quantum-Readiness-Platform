#!/usr/bin/env bash
# Evidence-to-risk-engine smoke test: proves that a *normal* ingest (not a
# hand-built /score call) forwards crypto_evidence/tls_metadata into
# risk-engine's stage2 evidence-signal extraction, and that Risk Narrator
# explains the resulting signals in plain language.
#
# Covers the four scenarios from the "Forward Evidence Into Risk Engine" plan:
#   1. network TLS ingest with RSA-1024 -> weak_public_key_detected
#   2. TLS cert expiring soon -> expiring_certificate_detected
#   3. host crypto packages/configs -> crypto_packages/tls_config/ssh_config
#   4. repo-ci-scanner findings -> non-empty, signal-bearing rationale
#
# Writes reports/evidence-to-risk-smoke-report.md and exits non-zero on any
# check failure.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
INVENTORY_BASE="http://127.0.0.1:8001"
COPILOT_BASE="http://127.0.0.1:8008"
REPORT_PATH="$ROOT_DIR/reports/evidence-to-risk-smoke-report.md"

RUN_DIR="$(mktemp -d)"
LOG_DIR="$RUN_DIR/logs"
mkdir -p "$LOG_DIR"
export INVENTORY_DB_PATH="$RUN_DIR/qrp-evidence-smoke-inventory.db"
export INVENTORY_SERVICE_URL="$INVENTORY_BASE"
export WORKFLOW_SERVICE_URL="http://127.0.0.1:8005"
export RETRIEVAL_SERVICE_URL="http://127.0.0.1:8015"
export PLANNER_SERVICE_URL="http://127.0.0.1:8004"

declare -a SERVICE_PIDS=()
declare -a NAMES=()
declare -a STATUSES=()
declare -a DETAILS=()

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
    NAMES+=("$name")
    STATUSES+=("$status")
    DETAILS+=("$detail")
    if [[ "$status" == "PASS" ]]; then
        echo "[PASS] $name"
    else
        echo "[FAIL] $name -> $detail"
    fi
}

rationale_bool() {
    # $1=scan_id $2=rationale key
    curl -sS "$INVENTORY_BASE/scans/$1" | "$PYTHON_BIN" -c "
import json, sys
d = json.load(sys.stdin)
print(d['risks'][0]['rationale'].get('$2'))
"
}

echo "== Starting services =="
start_service "inventory-service" "services/inventory-service" 8001 "app.main:app"
start_service "risk-engine" "services/risk-engine" 8002 "app.main:app"
start_service "workflow-service" "services/workflow-service" 8005 "app.main:app"
start_service "retrieval-service" "services/retrieval-service" 8015 "app.main:app"
start_service "copilot-service" "services/copilot-service" 8008 "app.main:app"

for entry in "inventory-service:8001" "risk-engine:8002" "workflow-service:8005" "retrieval-service:8015" "copilot-service:8008"; do
    name="${entry%%:*}"
    port="${entry##*:}"
    if ! wait_health "$port"; then
        echo "$name did not become healthy" >&2
        exit 1
    fi
done

echo "== Scenario 1: weak RSA-1024 TLS cert -> weak_public_key_detected =="
resp="$("$PYTHON_BIN" - "$INVENTORY_BASE" <<'PY'
import json, sys, urllib.request
base = sys.argv[1]
payload = {
    "source": "network",
    "assets": [{"asset_type": "endpoint", "name": "legacy-vpn.internal:443", "criticality": 4}],
    "tls_evidence": {
        "collected": True, "target": "legacy-vpn.internal", "port": 443,
        "certificate": {"subject": "CN=legacy-vpn.internal", "public_key_algorithm": "RSA", "public_key_size": 1024},
    },
}
req = urllib.request.Request(f"{base}/scans/ingest?scenario=public_timeline", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
print(json.loads(urllib.request.urlopen(req, timeout=10).read())["scan_id"])
PY
)"
if [[ "$(rationale_bool "$resp" weak_public_key_detected)" == "True" ]]; then
    record "network ingest RSA-1024 sets weak_public_key_detected" "PASS" ""
else
    record "network ingest RSA-1024 sets weak_public_key_detected" "FAIL" "weak_public_key_detected was not True"
fi
NARRATE_WEAK_ASSET="legacy-vpn.internal:443"

echo "== Scenario 2: expiring TLS cert -> expiring_certificate_detected =="
resp="$("$PYTHON_BIN" - "$INVENTORY_BASE" <<'PY'
import json, sys, urllib.request
from datetime import datetime, timedelta, timezone
base = sys.argv[1]
not_after = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
payload = {
    "source": "network",
    "assets": [{"asset_type": "endpoint", "name": "expiring-cert.internal:443", "criticality": 3}],
    "tls_evidence": {
        "collected": True, "target": "expiring-cert.internal", "port": 443,
        "certificate": {"subject": "CN=expiring-cert.internal", "public_key_algorithm": "ECDSA", "public_key_size": 256, "not_after": not_after},
    },
}
req = urllib.request.Request(f"{base}/scans/ingest?scenario=public_timeline", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
print(json.loads(urllib.request.urlopen(req, timeout=10).read())["scan_id"])
PY
)"
if [[ "$(rationale_bool "$resp" expiring_certificate_detected)" == "True" ]]; then
    record "network ingest with near-expiry cert sets expiring_certificate_detected" "PASS" ""
else
    record "network ingest with near-expiry cert sets expiring_certificate_detected" "FAIL" "expiring_certificate_detected was not True"
fi

echo "== Scenario 3: host crypto packages/configs -> crypto_packages/tls_config/ssh_config =="
resp="$("$PYTHON_BIN" - "$INVENTORY_BASE" <<'PY'
import json, sys, urllib.request
base = sys.argv[1]
payload = {
    "source": "host",
    "assets": [{"asset_type": "server", "name": "linux-configs-host", "criticality": 3}],
    "crypto_evidence": {
        "openssl_available": True,
        "package_metadata": {"packages": [{"name": "openssl"}]},
        "cert_indicators": {
            "certificate_file_indicators": {"counts": {"certificate": 2, "key": 1}},
            "config_file_indicators": {"counts": {"tls_server_config": 1, "ssh_server_config": 1}},
        },
    },
}
req = urllib.request.Request(f"{base}/scans/ingest?scenario=public_timeline", data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
print(json.loads(urllib.request.urlopen(req, timeout=10).read())["scan_id"])
PY
)"
scenario3_pass=true
for key in crypto_packages_detected tls_config_detected ssh_config_detected certificate_files_detected private_key_files_detected; do
    if [[ "$(rationale_bool "$resp" "$key")" != "True" ]]; then
        scenario3_pass=false
    fi
done
if [[ "$scenario3_pass" == "true" ]]; then
    record "host ingest with configs sets crypto_packages/tls_config/ssh_config signals" "PASS" ""
else
    record "host ingest with configs sets crypto_packages/tls_config/ssh_config signals" "FAIL" "one or more evidence signals were not True"
fi
NARRATE_HOST_ASSET="linux-configs-host"

echo "== Scenario 4: repo-ci-scanner findings -> non-empty, signal-bearing rationale =="
SCAN_TARGET="$RUN_DIR/vulnerable-repo"
mkdir -p "$SCAN_TARGET"
cat > "$SCAN_TARGET/crypto.py" <<'PY'
from Crypto.PublicKey import RSA
import hashlib
digest = hashlib.sha1(b"x").hexdigest()
PY
(cd "$ROOT_DIR/agents/repo-ci-scanner" && "$PYTHON_BIN" scanner.py --repo-path "$SCAN_TARGET" --out "$RUN_DIR/repo-ci-payload.json" --ingest "$INVENTORY_BASE" > "$RUN_DIR/repo-ci-ingest.json" 2>&1)
repo_scan_id="$("$PYTHON_BIN" -c "import json; print(json.load(open('$RUN_DIR/repo-ci-ingest.json'))['scan_id'])" 2>/dev/null || true)"
if [[ -n "$repo_scan_id" ]] && [[ "$(rationale_bool "$repo_scan_id" crypto_packages_detected)" == "True" ]]; then
    record "repo-ci-scanner ingest produces a signal-bearing rationale" "PASS" ""
else
    record "repo-ci-scanner ingest produces a signal-bearing rationale" "FAIL" "crypto_packages_detected was not True (see $RUN_DIR/repo-ci-ingest.json)"
fi
NARRATE_REPO_ASSET="vulnerable-repo"

echo "== Risk Narrator explains the real signals =="
narrate() {
    curl -sS "$COPILOT_BASE/narrate/$1" | "$PYTHON_BIN" -c "import json,sys; print(json.load(sys.stdin)['narrative'])"
}
weak_narrative="$(narrate "$NARRATE_WEAK_ASSET")"
if echo "$weak_narrative" | grep -qi "weak public key"; then
    record "Risk Narrator explains the weak-key signal" "PASS" ""
else
    record "Risk Narrator explains the weak-key signal" "FAIL" "narrative did not mention a weak public key"
fi

host_narrative="$(narrate "$NARRATE_HOST_ASSET")"
if echo "$host_narrative" | grep -qi "crypto-related packages"; then
    record "Risk Narrator explains the host evidence signals" "PASS" ""
else
    record "Risk Narrator explains the host evidence signals" "FAIL" "narrative did not mention crypto packages/config signals"
fi

repo_narrative="$(narrate "$NARRATE_REPO_ASSET")"
if echo "$repo_narrative" | grep -qi "crypto-related packages"; then
    record "Risk Narrator explains the repo-ci-scanner signal" "PASS" ""
else
    record "Risk Narrator explains the repo-ci-scanner signal" "FAIL" "narrative did not mention crypto packages"
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
    echo "# Evidence-to-Risk-Engine Smoke Report"
    echo ""
    echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo ""
    echo "Scope: a normal /scans/ingest (network/host/repo) forwards"
    echo "crypto_evidence/tls_metadata into risk-engine's stage2 evidence-signal"
    echo "extraction, and Risk Narrator explains the resulting signals."
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
