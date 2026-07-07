#!/usr/bin/env bash
# Linux/CI-friendly port of run_full_smoke.ps1.
#
# Starts risk-engine, crypto-fingerprint-service, evidence-normalizer,
# scenario-engine, integration-service, pqc-readiness-service, graph-service,
# finding-attribution-service and api-gateway locally, waits for health, then
# runs the same assertions against the gateway routes as the PowerShell
# version: /health, /api/algorithms, /api/fingerprint, /api/normalize,
# /api/scenarios/run, /api/assess, /api/attribute, /api/readiness-states,
# /api/pqc-readiness, /api/graph/*, /api/integrations, /api/integrations/dry-run.
#
# Writes reports/new-services-smoke-report.md and exits non-zero on any
# check failure.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
GATEWAY_BASE="http://127.0.0.1:8000"
FIXTURE_DIR="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence"
REPORT_PATH="$ROOT_DIR/reports/new-services-smoke-report.md"

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
    "$PYTHON_BIN" - "$GATEWAY_BASE" "$FIXTURE_DIR" "$check_id" <<'PY'
import json
import sys
import urllib.error
import urllib.request

gateway_base, fixture_dir, check_id = sys.argv[1:4]


def post_json(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(f"{gateway_base}{path}", data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_raw(path, raw_body):
    req = urllib.request.Request(f"{gateway_base}{path}", data=raw_body.encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(path):
    with urllib.request.urlopen(f"{gateway_base}{path}", timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


try:
    if check_id == "gateway_health":
        r = get_json("/health")
        assert r.get("status") == "ok", f"expected status ok, got {r.get('status')}"

    elif check_id == "algorithms_list":
        r = get_json("/api/algorithms")
        families = [a.get("family") for a in r.get("algorithms", [])]
        assert "RSA" in families, "RSA not in algorithm list"
        assert "ML-KEM" in families, "ML-KEM not in algorithm list"

    elif check_id == "fingerprint_hybrid_partial":
        r = post_json("/api/fingerprint", {"asset_name": "smoke", "algorithms": ["RSA", "ECDSA", "ML-KEM-768"]})
        s = r["summary"]
        assert s["pqc_readiness"] == "hybrid_partial", f"readiness={s['pqc_readiness']}"
        assert s["quantum_vulnerable_count"] >= 2, f"vuln count={s['quantum_vulnerable_count']}"
        assert s["pqc_ready_count"] >= 1, f"pqc count={s['pqc_ready_count']}"
        assert s["hndl_exposure"] is True, "expected hndl exposure"

    elif check_id == "fingerprint_weak_rsa":
        body = {"asset_name": "smoke", "tls_metadata": {"certificate": {"algorithms": {"public_key": "RSA"}, "key": {"size_bits": 1024}}}}
        r = post_json("/api/fingerprint", body)
        finding = r["findings"][0]
        assert finding["weak_key"] is True, "expected weak_key"
        assert finding["severity"] == "critical", f"severity={finding['severity']}"

    elif check_id == "normalize_certificate":
        with open(f"{fixture_dir}/network_enriched_ingest.json", encoding="utf-8") as f:
            raw = f.read()
        r = post_raw("/api/normalize", raw)
        cert = r["network_evidence"]["certificate"]
        assert cert["signature_algorithm"] == "RSA-PSS-SHA256", f"sig={cert['signature_algorithm']}"
        assert r["network_evidence"]["tls_version"] == "TLS 1.3", f"tls={r['network_evidence']['tls_version']}"

    elif check_id == "normalize_host_packages":
        with open(f"{fixture_dir}/host_enriched_ingest.json", encoding="utf-8") as f:
            raw = f.read()
        r = post_raw("/api/normalize", raw)
        host_ev = r["host_evidence"]
        assert host_ev["package_manager"] == "dnf", f"pkg mgr={host_ev['package_manager']}"
        assert host_ev["packages"][0]["name"] == "openssl", f"first pkg={host_ev['packages'][0]['name']}"

    elif check_id == "scenarios_run":
        body = {"scenario": "hidden_capability", "assets": [{"asset_name": "high", "base_score": 3.2}, {"asset_name": "low", "base_score": 1.0}]}
        r = post_json("/api/scenarios/run", body)
        assert r["scenario_multiplier"] == 1.35, f"mult={r['scenario_multiplier']}"
        assert r["results"][0]["asset_name"] == "high", f"top={r['results'][0]['asset_name']}"
        assert r["highest_rating"] == "critical", f"highest={r['highest_rating']}"

    elif check_id == "assess_chains":
        r = post_json("/api/assess", {"asset_name": "smoke", "algorithms": ["RSA", "ML-KEM-768"]})
        assert r["fingerprint"]["summary"]["pqc_readiness"] == "hybrid_partial", f"fp={r['fingerprint']['summary']['pqc_readiness']}"
        assert r["pqc_readiness"]["readiness"] == "hybrid_capable", f"readiness={r['pqc_readiness']['readiness']}"
        assert r.get("risk") is None, "expected no risk without risk_factors"
        assert len(r["pipeline"]) == 3, f"pipeline={','.join(r['pipeline'])}"

    elif check_id == "assess_with_risk":
        body = {
            "asset_name": "smoke", "algorithms": ["RSA"],
            "risk_factors": {"criticality": 5, "confidentiality_lifetime": 4, "quantum_exposure": 3, "blast_radius": 4, "vendor_lock_in": 3, "migration_difficulty": 3},
        }
        r = post_json("/api/assess", body)
        assert r.get("risk") is not None, "expected risk block"
        assert r["risk"].get("rating") is not None, "expected risk.rating"
        assert "risk-engine" in r["pipeline"], "risk-engine not in pipeline"

    elif check_id == "attribute_chain":
        body = {
            "asset_name": "payments-api", "application": "payments",
            "findings": [{"source": "tls_certificate", "location": "tls_metadata.certificate.public_key", "algorithm_family": "RSA", "classification": "classical_vulnerable", "severity": "high", "quantum_vulnerable": True, "raw_value": "RSA"}],
            "network_evidence": {"target": "api.example.internal", "port": 443, "certificate": {"subject": "CN=api.example.internal", "fingerprint_sha256": "abc123"}},
        }
        r = post_json("/api/attribute", body)
        f = r["attributed_findings"][0]
        assert f["location"]["value"] == "api.example.internal:443", f"location={f['location']['value']}"
        assert f["attribution"]["crypto_object"]["kind"] == "certificate", f"crypto_object={f['attribution']['crypto_object']['kind']}"
        assert f["chain"][3] == "asset:payments-api", f"chain asset={f['chain'][3]}"
        assert f["chain"][-1] == "certificate:CN=api.example.internal", f"chain tail={f['chain'][-1]}"

    elif check_id == "assess_includes_attribution":
        r = post_json("/api/assess", {"asset_name": "demo", "algorithms": ["RSA"]})
        assert r.get("attribution") is not None, "expected attribution block"
        assert "finding-attribution-service" in r["pipeline"], "attribution not in pipeline"

    elif check_id == "readiness_states":
        r = get_json("/api/readiness-states")
        states = [s.get("state") for s in r.get("states", [])]
        for expected in ("classical_only", "hybrid_capable", "pqc_ready", "vendor_blocked", "unknown"):
            assert expected in states, f"missing readiness state {expected}"

    elif check_id == "pqc_readiness_classical":
        r = post_json("/api/pqc-readiness", {"asset_name": "smoke", "findings": [{"classification": "classical_vulnerable"}]})
        assert r["readiness"] == "classical_only", f"readiness={r['readiness']}"

    elif check_id == "pqc_readiness_hybrid_and_blocked":
        hybrid = post_json("/api/pqc-readiness", {"asset_name": "smoke", "findings": [{"classification": "classical_vulnerable"}, {"classification": "pqc_ready"}]})
        assert hybrid["readiness"] == "hybrid_capable", f"hybrid={hybrid['readiness']}"
        blocked = post_json("/api/pqc-readiness", {"asset_name": "smoke", "findings": [{"classification": "pqc_ready"}], "vendor_blocked": True})
        assert blocked["readiness"] == "vendor_blocked", f"blocked={blocked['readiness']}"

    elif check_id == "graph_queries_list":
        r = get_json("/api/graph/queries")
        names = [q.get("name") for q in r.get("queries", [])]
        for expected in ("blast-radius", "trust-chain", "neighbors"):
            assert expected in names, f"missing graph query {expected}"

    elif check_id == "graph_blast_radius":
        snapshot = {
            "graph_schema_version": "0.1",
            "nodes": [
                {"id": "asset:a", "type": "Asset", "label": "asset-a"},
                {"id": "service:s", "type": "Service", "label": "svc"},
                {"id": "cert:leaf", "type": "Certificate", "label": "leaf"},
                {"id": "cert:root", "type": "Certificate", "label": "root-ca"},
            ],
            "edges": [
                {"from": "asset:a", "to": "service:s", "type": "RUNS"},
                {"from": "service:s", "to": "cert:leaf", "type": "USES_CERTIFICATE"},
                {"from": "cert:leaf", "to": "cert:root", "type": "SIGNED_BY"},
            ],
            "warnings": [],
        }
        r = post_json("/api/graph/blast-radius", {"node_id": "cert:root", "snapshot": snapshot})
        assert r["affected_count"] == 3, f"affected={r['affected_count']}"
        assert "asset:a" in r["affected_node_ids"], "asset not in blast radius"

    elif check_id == "graph_trust_chain":
        snapshot = {
            "graph_schema_version": "0.1",
            "nodes": [
                {"id": "asset:a", "type": "Asset", "label": "asset-a"},
                {"id": "service:s", "type": "Service", "label": "svc"},
                {"id": "cert:leaf", "type": "Certificate", "label": "leaf"},
                {"id": "cert:root", "type": "Certificate", "label": "root-ca"},
            ],
            "edges": [
                {"from": "asset:a", "to": "service:s", "type": "RUNS"},
                {"from": "service:s", "to": "cert:leaf", "type": "USES_CERTIFICATE"},
                {"from": "cert:leaf", "to": "cert:root", "type": "SIGNED_BY"},
            ],
            "warnings": [],
        }
        r = post_json("/api/graph/trust-chain", {"node_id": "cert:leaf", "snapshot": snapshot})
        assert r["root"] == "cert:root", f"root={r['root']}"
        assert r["length"] == 2, f"length={r['length']}"

    elif check_id == "graph_evidence_path":
        snapshot = {
            "graph_schema_version": "0.1",
            "nodes": [
                {"id": "asset:a", "type": "Asset", "label": "host-a"},
                {"id": "service:s", "type": "Service", "label": "api:443"},
                {"id": "cert:leaf", "type": "Certificate", "label": "CN=api"},
                {"id": "finding:v", "type": "CryptoFinding", "label": "quantum-vulnerable public key (RSA)"},
            ],
            "edges": [
                {"from": "asset:a", "to": "service:s", "type": "RUNS"},
                {"from": "service:s", "to": "cert:leaf", "type": "USES_CERTIFICATE"},
                {"from": "service:s", "to": "finding:v", "type": "SERVICE_HAS_FINDING"},
            ],
            "warnings": [],
        }
        r = post_json("/api/graph/evidence-path", {"node_id": "finding:v", "snapshot": snapshot})
        roles = [c.get("role") for c in r["chain"]]
        assert ",".join(roles) == "vulnerability,service,asset,crypto_object", f"roles={','.join(roles)}"
        assert r["chain"][-1]["node_id"] == "cert:leaf", f"tail={r['chain'][-1]['node_id']}"

    elif check_id == "integrations_disabled":
        r = get_json("/api/integrations")
        assert r["mode"] == "dry_run_disabled", f"mode={r['mode']}"
        assert r["executed_changes_supported"] is False, "expected executed_changes_supported false"

    elif check_id == "integrations_dry_run_approved":
        body = {"action": "rotate_certificate", "target_type": "ca", "asset_name": "smoke", "approved": True, "approvals_provided": ["security_review", "change_approval"]}
        r = post_json("/api/integrations/dry-run", body)
        assert r["executed"] is False, "expected executed false"
        assert r["would_execute_if_enabled"] is True, "expected would_execute_if_enabled true"
        assert "integration_execution_disabled" in r["blocked_reasons"], "missing execution-disabled block"

    elif check_id == "integrations_dry_run_rejects_secret":
        body = {"action": "rotate_key", "target_type": "hsm", "asset_name": "smoke", "parameters": {"private_key": "-----BEGIN"}}
        r = post_json("/api/integrations/dry-run", body)
        assert "sensitive_material_rejected" in r["blocked_reasons"], "secret not rejected"
        assert len(r.get("parameter_keys") or []) == 0, "secret keys echoed back"

    else:
        raise SystemExit(f"unknown check_id: {check_id}")

    print("PASS")
except AssertionError as exc:
    print(f"FAIL: {exc}")
    sys.exit(1)
except (urllib.error.URLError, urllib.error.HTTPError, KeyError, IndexError, OSError) as exc:
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
overall="PASS"
for entry in "risk-engine:8002" "crypto-fingerprint-service:8003" "evidence-normalizer:8009" \
    "scenario-engine:8006" "integration-service:8011" "pqc-readiness-service:8012" \
    "graph-service:8013" "finding-attribution-service:8014" "api-gateway:8000"; do
    name="${entry%%:*}"
    port="${entry##*:}"
    if wait_health "$port"; then
        echo "  healthy: $name"
    else
        echo "Service '$name' did not become healthy on port $port" >&2
        overall="FAIL"
    fi
done

if [[ "$overall" == "PASS" ]]; then
    echo "== Running checks =="
    check "gateway health" "gateway_health"
    check "GET /api/algorithms lists known families" "algorithms_list"
    check "POST /api/fingerprint classical+pqc mix is hybrid_partial" "fingerprint_hybrid_partial"
    check "POST /api/fingerprint flags weak RSA key as critical" "fingerprint_weak_rsa"
    check "POST /api/normalize canonicalizes nested certificate" "normalize_certificate"
    check "POST /api/normalize extracts host packages" "normalize_host_packages"
    check "POST /api/scenarios/run applies multiplier and ranks" "scenarios_run"
    check "POST /api/assess chains fingerprint -> pqc-readiness" "assess_chains"
    check "POST /api/assess includes risk when risk_factors given" "assess_with_risk"
    check "POST /api/attribute builds the vuln->location->service->asset->cert chain" "attribute_chain"
    check "POST /api/assess includes finding attribution" "assess_includes_attribution"
    check "GET /api/readiness-states lists five states" "readiness_states"
    check "POST /api/pqc-readiness classifies classical-only" "pqc_readiness_classical"
    check "POST /api/pqc-readiness classifies hybrid and vendor_blocked" "pqc_readiness_hybrid_and_blocked"
    check "GET /api/graph/queries lists traversal queries" "graph_queries_list"
    check "POST /api/graph/blast-radius reaches the dependent asset" "graph_blast_radius"
    check "POST /api/graph/trust-chain follows SIGNED_BY to root" "graph_trust_chain"
    check "POST /api/graph/evidence-path builds vuln->service->asset->cert chain" "graph_evidence_path"
    check "GET /api/integrations reports everything disabled" "integrations_disabled"
    check "POST /api/integrations/dry-run never executes when approved" "integrations_dry_run_approved"
    check "POST /api/integrations/dry-run rejects secret material" "integrations_dry_run_rejects_secret"
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
    echo "# New Services Smoke Report"
    echo ""
    echo "Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    echo ""
    echo "Scope: crypto-fingerprint-service, evidence-normalizer, scenario-engine,"
    echo "integration-service (dry-run), web-ui gateway routes -- exercised through api-gateway."
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
