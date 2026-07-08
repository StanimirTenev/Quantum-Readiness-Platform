#!/usr/bin/env bash
# Linux/CI-friendly port of the base flow in run_report.ps1 (no -WindowsEvidence
# support -- that step drives agents/windows-host-agent/collect.ps1, which is
# Windows-only by design; use the .ps1 version on a Windows host for it).
#
# Starts the assessment stack + API Gateway, assesses a set of fixture assets
# through /api/assess, and renders an operator/exec Markdown report via
# tools/report/build_operator_report.py (executive summary, migration waves,
# findings, attribution/evidence chains, boundaries).
#
# Usage:
#   bash scripts/run_report.sh [--out <path>]
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
GATEWAY_BASE="http://127.0.0.1:8000"
FIXTURE_DIR="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence"
OUT_FILE="$ROOT_DIR/reports/operator-report.md"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out) OUT_FILE="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

RUN_DIR="$(mktemp -d)"
LOG_DIR="$RUN_DIR/logs"
mkdir -p "$LOG_DIR"

export CRYPTO_FINGERPRINT_URL="http://127.0.0.1:8003"
export PQC_READINESS_URL="http://127.0.0.1:8012"
export FINDING_ATTRIBUTION_URL="http://127.0.0.1:8014"
export RISK_ENGINE_URL="http://127.0.0.1:8002"

declare -a SERVICE_PIDS=()

cleanup() {
    for pid in "${SERVICE_PIDS[@]:-}"; do
        [[ -n "$pid" ]] && kill "$pid" >/dev/null 2>&1 || true
    done
    rm -rf "$RUN_DIR"
    echo "Services stopped."
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

echo "Starting assessment stack..."
start_service "risk-engine" "services/risk-engine" 8002 "app.main:app"
start_service "crypto-fingerprint-service" "services/crypto-fingerprint-service" 8003 "app.main:app"
start_service "pqc-readiness-service" "services/pqc-readiness-service" 8012 "app.main:app"
start_service "finding-attribution-service" "services/finding-attribution-service" 8014 "app.main:app"
start_service "api-gateway" "services/api-gateway" 8000 "main:app"

for entry in "risk-engine:8002" "crypto-fingerprint-service:8003" "pqc-readiness-service:8012" "finding-attribution-service:8014" "api-gateway:8000"; do
    name="${entry%%:*}"
    port="${entry##*:}"
    if ! wait_health "$port"; then
        echo "$name did not become healthy" >&2
        exit 1
    fi
done

echo "Assessing assets..."
BUNDLE_PATH="$RUN_DIR/qrp-assessment-bundle.json"

"$PYTHON_BIN" - "$GATEWAY_BASE" "$FIXTURE_DIR" "$BUNDLE_PATH" <<'PY'
import json
import sys
import urllib.request
from datetime import datetime, timezone

gateway_base, fixture_dir, bundle_path = sys.argv[1:4]

HIGH_RISK = {"criticality": 5, "confidentiality_lifetime": 4, "quantum_exposure": 4, "blast_radius": 4, "vendor_lock_in": 3, "migration_difficulty": 3}
MED_RISK = {"criticality": 3, "confidentiality_lifetime": 3, "quantum_exposure": 3, "blast_radius": 3, "vendor_lock_in": 2, "migration_difficulty": 2}


def post(path, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{gateway_base}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


with open(f"{fixture_dir}/network_enriched_ingest.json", encoding="utf-8") as f:
    fixture = json.load(f)

assets = [
    {"asset_name": "payments-api", "application": "payments", "assess": post("/api/assess", {"asset_name": "payments-api", "application": "payments", "tls_metadata": fixture["tls_metadata"], "risk_factors": HIGH_RISK})},
    {"asset_name": "legacy-vpn", "application": "network", "assess": post("/api/assess", {"asset_name": "legacy-vpn", "application": "network", "tls_metadata": {"certificate": {"algorithms": {"public_key": "RSA", "signature": "sha1WithRSAEncryption"}, "key": {"size_bits": 1024}}}, "risk_factors": HIGH_RISK})},
    {"asset_name": "modern-api", "application": "platform", "assess": post("/api/assess", {"asset_name": "modern-api", "application": "platform", "algorithms": ["ML-KEM-768", "ML-DSA-65"], "risk_factors": MED_RISK})},
]

bundle = {"generated_at": datetime.now(timezone.utc).isoformat(), "environment": "local-fixtures", "assets": assets}
with open(bundle_path, "w", encoding="utf-8") as f:
    json.dump(bundle, f)
PY

"$PYTHON_BIN" "$ROOT_DIR/tools/report/build_operator_report.py" --input "$BUNDLE_PATH" --out "$OUT_FILE"

echo ""
echo "== Executive summary =="
tail -n +10 "$OUT_FILE" | head -12
echo ""
echo "Report: $OUT_FILE"
