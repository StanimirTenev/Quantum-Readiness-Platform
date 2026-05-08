#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_DIR="$ROOT_DIR/reports"
REPORT_FILE="$REPORT_DIR/trl-validation-report.md"
EVIDENCE_DIR="$REPORT_DIR/evidence"
LATEST_EVIDENCE_DIR="$EVIDENCE_DIR/latest"

sanitize_json_file() {
  local input_file="$1"
  local output_file="$2"

  if command -v jq >/dev/null 2>&1; then
    local tmp_file
    tmp_file="$(mktemp)"
    jq '
      walk(
        if type == "object" then
          del(
            .password,
            .token,
            .api_key,
            .secret,
            .authorization,
            .Authorization,
            .access_token,
            .refresh_token
          )
        else
          .
        end
      )
    ' "$input_file" > "$tmp_file"
    mv "$tmp_file" "$output_file"
  else
    cp "$input_file" "$output_file"
  fi
}

INVENTORY_URL="${INVENTORY_URL:-http://127.0.0.1:8001}"
RISK_URL="${RISK_URL:-http://127.0.0.1:8002}"
PLANNER_URL="${PLANNER_URL:-http://127.0.0.1:8004}"
WORKFLOW_URL="${WORKFLOW_URL:-http://127.0.0.1:8005}"
POLICY_URL="${POLICY_URL:-http://127.0.0.1:8007}"
API_GATEWAY_URL="${API_GATEWAY_URL:-http://127.0.0.1:8000}"

mkdir -p "$REPORT_DIR" "$LATEST_EVIDENCE_DIR"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

HEALTH_JSON="$TMP_DIR/health.json"
: > "$HEALTH_JSON"

check_health() {
  local service="$1"
  local endpoint="$2"
  local required="$3"
  local status="UP"

  if ! curl -fsS "$endpoint" >/dev/null 2>&1; then
    if [[ "$required" == "required" ]]; then
      echo "Required service unavailable: $service ($endpoint)" >&2
      exit 1
    fi
    status="SKIPPED"
  fi

  python3 - "$HEALTH_JSON" "$service" "$endpoint" "$status" <<'PY'
import json
import sys
path, service, endpoint, status = sys.argv[1:5]
rows=[]
try:
    with open(path, "r", encoding="utf-8") as f:
        txt=f.read().strip()
        if txt:
            rows=json.loads(txt)
except FileNotFoundError:
    pass
rows.append({"service":service,"endpoint":endpoint,"status":status})
with open(path, "w", encoding="utf-8") as f:
    json.dump(rows, f)
PY
}

check_health "inventory-service" "$INVENTORY_URL/health" "required"
check_health "risk-engine" "$RISK_URL/health" "required"
check_health "planner-service" "$PLANNER_URL/health" "required"
check_health "workflow-service" "$WORKFLOW_URL/health" "required"
check_health "policy-engine" "$POLICY_URL/health" "required"
check_health "api-gateway" "$API_GATEWAY_URL/health" "optional"

HOST_FIXTURE="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json"
NETWORK_FIXTURE="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json"

[[ -f "$HOST_FIXTURE" ]] || { echo "Missing required fixture: $HOST_FIXTURE" >&2; exit 1; }
[[ -f "$NETWORK_FIXTURE" ]] || { echo "Missing required fixture: $NETWORK_FIXTURE" >&2; exit 1; }

HOST_EVIDENCE_ARTIFACT="$LATEST_EVIDENCE_DIR/host-evidence.json"
NETWORK_EVIDENCE_ARTIFACT="$LATEST_EVIDENCE_DIR/network-evidence.json"
INVENTORY_INGEST_ARTIFACT="$LATEST_EVIDENCE_DIR/inventory-ingest-response.json"
ASSETS_ARTIFACT="$LATEST_EVIDENCE_DIR/assets.json"
RISKS_ARTIFACT="$LATEST_EVIDENCE_DIR/risks.json"
POLICY_ARTIFACT="$LATEST_EVIDENCE_DIR/policy-decision.json"
PLAN_ARTIFACT="$LATEST_EVIDENCE_DIR/plan.json"
WAVES_ARTIFACT="$LATEST_EVIDENCE_DIR/waves.json"
WORKFLOW_ARTIFACT="$LATEST_EVIDENCE_DIR/workflow-export.json"

sanitize_json_file "$HOST_FIXTURE" "$HOST_EVIDENCE_ARTIFACT"
sanitize_json_file "$NETWORK_FIXTURE" "$NETWORK_EVIDENCE_ARTIFACT"

INGEST_HOST="$TMP_DIR/ingest_host.json"
INGEST_NETWORK="$TMP_DIR/ingest_network.json"

curl -fsS -X POST "$INVENTORY_URL/scans/ingest?auto_score=true&scenario=public_timeline" \
  -H 'Content-Type: application/json' \
  --data-binary "@$HOST_FIXTURE" > "$INGEST_HOST"

curl -fsS -X POST "$INVENTORY_URL/scans/ingest?auto_score=true&scenario=public_timeline" \
  -H 'Content-Type: application/json' \
  --data-binary "@$NETWORK_FIXTURE" > "$INGEST_NETWORK"

python3 - "$INGEST_HOST" "$INGEST_NETWORK" "$INVENTORY_INGEST_ARTIFACT" <<'PY'
import json,sys
host_path, network_path, out_path = sys.argv[1:4]
json.dump(
    {
        "host_ingest": json.load(open(host_path, encoding="utf-8")),
        "network_ingest": json.load(open(network_path, encoding="utf-8")),
    },
    open(out_path, "w", encoding="utf-8"),
)
PY
sanitize_json_file "$INVENTORY_INGEST_ARTIFACT" "$INVENTORY_INGEST_ARTIFACT"

python3 - "$INGEST_HOST" "$INGEST_NETWORK" <<'PY'
import json,sys
for path in sys.argv[1:]:
    data=json.load(open(path,encoding='utf-8'))
    if not data.get('scan_id'):
        raise SystemExit(f"Missing scan_id in {path}")
    if data.get('created',0) <= 0:
        raise SystemExit(f"created must be > 0 in {path}")
    if not data.get('asset_ids'):
        raise SystemExit(f"asset_ids must be non-empty in {path}")
PY

ASSETS_JSON="$TMP_DIR/assets.json"
RISKS_JSON="$TMP_DIR/risks.json"
PLAN_JSON="$TMP_DIR/plan.json"
WAVES_JSON="$TMP_DIR/waves.json"
POLICY_JSON="$TMP_DIR/policy.json"
WORKFLOW_EXPORT_JSON="$TMP_DIR/workflow_export.json"

curl -fsS "$INVENTORY_URL/assets" > "$ASSETS_JSON"
curl -fsS "$INVENTORY_URL/risks" > "$RISKS_JSON"
sanitize_json_file "$ASSETS_JSON" "$ASSETS_ARTIFACT"
sanitize_json_file "$RISKS_JSON" "$RISKS_ARTIFACT"

python3 - "$RISKS_JSON" "$POLICY_JSON" "$POLICY_URL" <<'PY'
import json,sys,urllib.request
risks_path, out_path, policy_url = sys.argv[1:4]
risks=json.load(open(risks_path,encoding='utf-8'))
if not risks:
    raise SystemExit('No risk records returned from /risks')
risk=risks[0]
payload={
    "asset_name": risk["asset_name"],
    "environment": "production",
    "criticality": 4,
    "normalized_score_100": risk["normalized_score_100"],
    "rating": risk.get("rating"),
    "vendor_blocked": risk.get("vendor_blocked", False),
    "dependency_count": risk.get("dependency_count", 0),
    "scenario": risk.get("scenario") or "public_timeline",
}
req=urllib.request.Request(
    f"{policy_url}/evaluate",
    data=json.dumps(payload).encode(),
    headers={"Content-Type":"application/json"},
    method="POST",
)
with urllib.request.urlopen(req) as resp:
    body=resp.read().decode()
result=json.loads(body)
for field in ("decision","reasons","rule_id","rule_version"):
    if field not in result:
        raise SystemExit(f"Missing {field} in policy response")
json.dump({"request":payload,"response":result}, open(out_path,'w',encoding='utf-8'))
PY
sanitize_json_file "$POLICY_JSON" "$POLICY_ARTIFACT"

curl -fsS "$PLANNER_URL/plan" > "$PLAN_JSON"
curl -fsS "$PLANNER_URL/waves" > "$WAVES_JSON"
sanitize_json_file "$PLAN_JSON" "$PLAN_ARTIFACT"
sanitize_json_file "$WAVES_JSON" "$WAVES_ARTIFACT"

curl -fsS -X POST "$PLANNER_URL/export-tasks" \
  -H 'Content-Type: application/json' \
  --data '{"waves":["wave_1"],"auto_submit":false}' > "$WORKFLOW_EXPORT_JSON"
sanitize_json_file "$WORKFLOW_EXPORT_JSON" "$WORKFLOW_ARTIFACT"

python3 - "$HEALTH_JSON" "$INGEST_HOST" "$RISKS_JSON" "$POLICY_JSON" "$WAVES_JSON" "$WORKFLOW_EXPORT_JSON" "$REPORT_FILE" <<'PY'
import json,sys
from datetime import datetime, timezone
health_path, ingest_path, risks_path, policy_path, waves_path, export_path, report_file = sys.argv[1:8]
health=json.load(open(health_path,encoding='utf-8'))
ingest=json.load(open(ingest_path,encoding='utf-8'))
risks=json.load(open(risks_path,encoding='utf-8'))
policy=json.load(open(policy_path,encoding='utf-8'))
waves=json.load(open(waves_path,encoding='utf-8'))
export=json.load(open(export_path,encoding='utf-8'))

sample_risk=risks[0]
policy_resp=policy['response']
status = "PASS" if all(r['status'] in ("UP","SKIPPED") for r in health) else "FAIL"

lines=[
"# TRL Validation Report",
"",
"## Validation Date",
datetime.now(timezone.utc).isoformat(),
"",
"## Validation Scope",
"- inventory ingest",
"- risk scoring",
"- policy evaluation",
"- planning",
"- workflow task export",
"",
"## Services Checked",
"| Service | Endpoint | Status |",
"|---|---|---|",
]
for row in health:
    lines.append(f"| {row['service']} | {row['endpoint']} | {row['status']} |")
lines += [
"",
"## Evidence Ingest Result",
f"- scan_id: {ingest['scan_id']}",
f"- created assets: {ingest['created']}",
f"- asset_ids: {', '.join(ingest['asset_ids'])}",
"",
"## Risk Result",
f"- total risk records: {len(risks)}",
f"- sample asset: {sample_risk['asset_name']}",
f"- normalized score: {sample_risk['normalized_score_100']}",
f"- rating: {sample_risk['rating']}",
"",
"## Policy Decision",
f"- asset: {policy_resp['asset_name']}",
f"- decision: {policy_resp['decision']}",
f"- reasons: {', '.join(policy_resp['reasons'])}",
f"- rule_id: {policy_resp['rule_id']}",
f"- rule_version: {policy_resp['rule_version']}",
"",
"## Planning Result",
f"- wave_1 count: {len(waves.get('wave_1', []))}",
f"- wave_2 count: {len(waves.get('wave_2', []))}",
f"- wave_3 count: {len(waves.get('wave_3', []))}",
"",
"## Workflow Result",
f"- created task count: {export.get('created_count', 0)}",
"",
"## Evidence Artifacts",
"| Artifact | Path |",
"|---|---|",
"| Host evidence | reports/evidence/latest/host-evidence.json |",
"| Network evidence | reports/evidence/latest/network-evidence.json |",
"| Inventory ingest response | reports/evidence/latest/inventory-ingest-response.json |",
"| Assets | reports/evidence/latest/assets.json |",
"| Risks | reports/evidence/latest/risks.json |",
"| Policy decision | reports/evidence/latest/policy-decision.json |",
"| Plan | reports/evidence/latest/plan.json |",
"| Waves | reports/evidence/latest/waves.json |",
"| Workflow export | reports/evidence/latest/workflow-export.json |",
"",
"## TRL Assessment",
"Current technical maturity:",
"TRL 4 -> TRL 5 candidate",
"",
"Reason:",
"The system demonstrates a repeatable local validation flow across discovery evidence, inventory, risk, policy, planning and workflow.",
"",
"Remaining gaps before claiming stronger TRL 5:",
"- run against real infrastructure sample",
"- preserve evidence artifacts across timestamped runs",
"- add failure/retry handling",
"- add operator-facing validation checklist",
"- document environment assumptions",
"",
"## Result",
status,
]
with open(report_file,'w',encoding='utf-8') as f:
    f.write("\n".join(lines)+"\n")
print(f"Wrote report to {report_file}")
PY

echo "TRL validation completed. Report: $REPORT_FILE"
