#!/usr/bin/env bash
# Linux/CI-friendly port of the base flow in run_flow.ps1 (no -WindowsEvidence
# support -- that step drives agents/windows-host-agent/collect.ps1, which is
# Windows-only by design; use the .ps1 version on a Windows host for it).
#
# Starts the analysis stack + API Gateway, projects the dependency graph from
# the Stage 2 fixtures, then drives real evidence through the pipeline via the
# gateway: normalize -> assess (fingerprint -> pqc-readiness -> attribution ->
# risk) -> scenario re-scoring -> graph (evidence-path + blast-radius) ->
# integration dry-run (disabled).
#
# Prints a readable narrative, writes reports/flow-run-report.md, and stops
# the services. This is a demonstration runner (not an assertion suite -- see
# scripts/run_full_smoke.sh for that).
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
GATEWAY_BASE="http://127.0.0.1:8000"
FIXTURE_DIR="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence"
REPORT_PATH="$ROOT_DIR/reports/flow-run-report.md"

RUN_DIR="$(mktemp -d)"
LOG_DIR="$RUN_DIR/logs"
mkdir -p "$LOG_DIR"

export CRYPTO_FINGERPRINT_URL="http://127.0.0.1:8003"
export EVIDENCE_NORMALIZER_URL="http://127.0.0.1:8009"
export SCENARIO_ENGINE_URL="http://127.0.0.1:8006"
export INTEGRATION_SERVICE_URL="http://127.0.0.1:8011"
export PQC_READINESS_URL="http://127.0.0.1:8012"
export GRAPH_SERVICE_URL="http://127.0.0.1:8013"
export FINDING_ATTRIBUTION_URL="http://127.0.0.1:8014"
export RISK_ENGINE_URL="http://127.0.0.1:8002"
export INVENTORY_SERVICE_URL="http://127.0.0.1:8001"
export INVENTORY_DB_PATH="$RUN_DIR/qrp-flow-inventory.db"
export GRAPH_SNAPSHOT_PATH="$ROOT_DIR/reports/graph/latest/graph-snapshot.json"

declare -a SERVICE_PIDS=()

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

echo "== QRP flow =="
echo "== Starting services =="
start_service "inventory-service" "services/inventory-service" 8001 "app.main:app"
start_service "risk-engine" "services/risk-engine" 8002 "app.main:app"
start_service "crypto-fingerprint-service" "services/crypto-fingerprint-service" 8003 "app.main:app"
start_service "evidence-normalizer" "services/evidence-normalizer" 8009 "app.main:app"
start_service "scenario-engine" "services/scenario-engine" 8006 "app.main:app"
start_service "integration-service" "services/integration-service" 8011 "app.main:app"
start_service "pqc-readiness-service" "services/pqc-readiness-service" 8012 "app.main:app"
start_service "graph-service" "services/graph-service" 8013 "app.main:app"
start_service "finding-attribution-service" "services/finding-attribution-service" 8014 "app.main:app"
start_service "api-gateway" "services/api-gateway" 8000 "main:app"

echo "== Waiting for health =="
for entry in "inventory-service:8001" "risk-engine:8002" "crypto-fingerprint-service:8003" \
    "evidence-normalizer:8009" "scenario-engine:8006" "integration-service:8011" \
    "pqc-readiness-service:8012" "graph-service:8013" "finding-attribution-service:8014" \
    "api-gateway:8000"; do
    name="${entry%%:*}"
    port="${entry##*:}"
    if ! wait_health "$port"; then
        echo "$name did not become healthy" >&2
        exit 1
    fi
done
echo "All services healthy."

mkdir -p "$ROOT_DIR/reports/graph/latest"

"$PYTHON_BIN" - "$ROOT_DIR" "$GATEWAY_BASE" "$FIXTURE_DIR" "$REPORT_PATH" "$GRAPH_SNAPSHOT_PATH" "$PYTHON_BIN" <<'PY'
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

root_dir, gateway_base, fixture_dir, report_path, snapshot_path, python_bin = sys.argv[1:7]
narrative = []


def say(text=""):
    print(text)
    narrative.append(text)


def post(path, body):
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(f"{gateway_base}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def write_report(ok):
    lines = ["# QRP Flow Run", "", f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}", "", "```"]
    lines += narrative
    lines += ["```", ""]
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nReport: {report_path}")


try:
    say("")
    say("== 1. Discovery -> graph projection ==")
    fixture_dir_rel = f"services/inventory-service/tests/fixtures/stage2_evidence"
    subprocess.run(
        [
            python_bin, "tools/graph_projection/project_stage2_fixtures.py",
            "--host", f"{fixture_dir_rel}/host_enriched_ingest.json",
            "--network", f"{fixture_dir_rel}/network_enriched_ingest.json",
            "--snapshot-out", "reports/graph/latest/graph-snapshot.json",
            "--report-out", "reports/graph/latest/graph-projection-report.md",
        ],
        check=True, stdout=subprocess.DEVNULL, cwd=root_dir,
    )
    with open(snapshot_path, encoding="utf-8") as f:
        snap = json.load(f)
    say(f"Projected snapshot: {len(snap['nodes'])} nodes, {len(snap['edges'])} edges.")

    say("")
    say("== 2. Evidence normalization ==")
    with open(f"{fixture_dir}/network_enriched_ingest.json", encoding="utf-8") as f:
        fixture = json.load(f)
    norm = post("/api/normalize", fixture)
    cert = norm["network_evidence"]["certificate"]
    say(f"Canonical certificate: subject={cert['subject']}, sig={cert['signature_algorithm']}, pubkey={cert['public_key_algorithm']}, tls={norm['network_evidence']['tls_version']}")

    say("")
    say("== 3. Assessment pipeline ==")
    assess = post("/api/assess", {
        "asset_name": "payments-api",
        "application": "payments",
        "tls_metadata": fixture["tls_metadata"],
        "risk_factors": {"criticality": 5, "confidentiality_lifetime": 4, "quantum_exposure": 4, "blast_radius": 4, "vendor_lock_in": 3, "migration_difficulty": 3},
    })
    say("Pipeline ran: " + " -> ".join(assess["pipeline"]))
    fp = assess["fingerprint"]["summary"]
    say(f"Fingerprint readiness: {fp['pqc_readiness']} (q-vulnerable {fp['quantum_vulnerable_count']}, pqc-ready {fp['pqc_ready_count']}, HNDL {fp['hndl_exposure']})")
    say(f"PQC readiness: {assess['pqc_readiness']['readiness']} (confidence {assess['pqc_readiness']['confidence']})")
    say(f"Risk: {assess['risk']['rating']} (normalized {assess['risk']['normalized_score_100']})")
    attributed = (assess.get("attribution") or {}).get("attributed_findings") or []
    if attributed:
        say("Attribution chain: " + " -> ".join(attributed[0]["chain"]))

    say("")
    say("== 4. Scenario re-scoring (hidden_capability) ==")
    base_score = round((assess["risk"]["normalized_score_100"] / 100.0) * 5.0, 2)
    scenario = post("/api/scenarios/run", {"scenario": "hidden_capability", "assets": [{"asset_name": "payments-api", "base_score": base_score}]})
    sr = scenario["results"][0]
    say(f"payments-api under {scenario['scenario']} (x{scenario['scenario_multiplier']}): normalized {sr['base_score']} -> {sr['normalized_score_100']} ({sr['rating']})")

    say("")
    say("== 5. Graph traversal ==")
    finding = next((n for n in snap["nodes"] if n.get("type") == "CryptoFinding"), None)
    if finding:
        ep = post("/api/graph/evidence-path", {"node_id": finding["id"]})
        say("Evidence path: " + " -> ".join(f"{c['role']}={c['label']}" for c in ep["chain"]))
    certs = [n for n in snap["nodes"] if n.get("type") == "Certificate"]
    root_ca = next((n for n in certs if not re.search(r"internal$", n.get("label", ""))), None)
    target_node = root_ca if root_ca else (certs[-1] if certs else None)
    if target_node:
        blast = post("/api/graph/blast-radius", {"node_id": target_node["id"]})
        types = ", ".join(a["node"]["type"] for a in blast.get("affected", []))
        say(f"Blast radius of {target_node['label']}: {blast['affected_count']} affected -> {types}")

    say("")
    say("== 6. Integration dry-run (Trust Zone 4) ==")
    dry = post("/api/integrations/dry-run", {"action": "rotate_certificate", "target_type": "ca", "asset_name": "payments-api", "approved": True, "approvals_provided": ["security_review", "change_approval"]})
    say(f"rotate_certificate: executed={dry['executed']}, would_execute_if_enabled={dry['would_execute_if_enabled']}, blocked={','.join(dry['blocked_reasons'])}")

    say("")
    say("== Flow complete ==")
    write_report(True)
except (subprocess.CalledProcessError, urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, OSError) as exc:
    say("")
    say(f"== Flow FAILED: {exc} ==")
    write_report(False)
    sys.exit(1)
PY
