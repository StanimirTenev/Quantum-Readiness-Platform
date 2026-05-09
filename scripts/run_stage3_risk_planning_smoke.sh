#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="$ROOT_DIR/reports/stage3-risk-planning-smoke-report.md"
HOST_FIXTURE="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json"
NETWORK_FIXTURE="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json"

SERVICE_ROWS=()

has_jq=0
if command -v jq >/dev/null 2>&1; then
  has_jq=1
fi

json_get() {
  local file="$1"
  local path="$2"
  if [[ "$has_jq" -eq 1 ]]; then
    jq -r "$path" "$file"
  else
    python3 - "$file" "$path" <<'PY'
import json,sys
file_path,path=sys.argv[1],sys.argv[2]
with open(file_path,encoding='utf-8') as f:
    data=json.load(f)
expr=path.strip().lstrip('.')
if not expr:
    print(json.dumps(data))
    sys.exit(0)
cur=data
for part in expr.split('.'):
    if '[' in part and part.endswith(']'):
        key,idx=part[:-1].split('[')
        if key:
            cur=cur.get(key)
        cur=cur[int(idx)]
    else:
        cur=cur.get(part) if isinstance(cur,dict) else None
if isinstance(cur,(dict,list)):
    print(json.dumps(cur))
elif cur is None:
    print('null')
else:
    print(cur)
PY
  fi
}

json_assert_non_null() {
  local file="$1"
  local path="$2"
  local value
  value="$(json_get "$file" "$path")"
  if [[ -z "$value" || "$value" == "null" ]]; then
    echo "Missing required field $path in $file" >&2
    exit 1
  fi
}

health_check() {
  local service="$1"
  local endpoint="$2"
  local tmp
  tmp="$(mktemp)"
  local status
  status="$(curl -sS -o "$tmp" -w "%{http_code}" "$endpoint" || true)"
  if [[ "$status" == "200" ]]; then
    SERVICE_ROWS+=("| $service | $endpoint | PASS |")
  else
    SERVICE_ROWS+=("| $service | $endpoint | FAIL ($status) |")
    rm -f "$tmp"
    echo "Health check failed for $service ($endpoint)" >&2
    exit 1
  fi
  rm -f "$tmp"
}

health_check "inventory-service" "http://127.0.0.1:8001/health"
health_check "risk-engine" "http://127.0.0.1:8002/health"
health_check "planner-service" "http://127.0.0.1:8004/health"

host_resp="$(mktemp)"
network_resp="$(mktemp)"
risk_resp="$(mktemp)"
plan_resp="$(mktemp)"
trap 'rm -f "$host_resp" "$network_resp" "$risk_resp" "$plan_resp"' EXIT

curl -sS -f -X POST "http://127.0.0.1:8001/scans/ingest?scenario=public_timeline" -H "Content-Type: application/json" --data-binary "@$HOST_FIXTURE" > "$host_resp"
curl -sS -f -X POST "http://127.0.0.1:8001/scans/ingest?scenario=public_timeline" -H "Content-Type: application/json" --data-binary "@$NETWORK_FIXTURE" > "$network_resp"

json_assert_non_null "$host_resp" ".scan_id"
json_assert_non_null "$host_resp" ".created"
json_assert_non_null "$host_resp" ".asset_ids"
json_assert_non_null "$network_resp" ".scan_id"
json_assert_non_null "$network_resp" ".created"
json_assert_non_null "$network_resp" ".asset_ids"

cat > "$ROOT_DIR/reports/.stage3-risk-input.json" <<'JSON'
{
  "contract_version": "stage1-v1",
  "asset_name": "stage3-smoke-endpoint",
  "criticality": 4.5,
  "confidentiality_lifetime": 4.0,
  "quantum_exposure": 4.8,
  "blast_radius": 4.2,
  "vendor_lock_in": 2.5,
  "migration_difficulty": 3.8,
  "dependency_count": 7,
  "environment": "production",
  "vendor_blocked": false,
  "scenario": "public_timeline",
  "stage2_notes": "hndl signal present and migration plan pending",
  "crypto_evidence": {
    "package_metadata": {"packages": ["openssl", "openssh"]},
    "cert_indicators": {
      "certificate_file_indicators": {"counts": {"certificate": 2, "key": 1}},
      "config_file_indicators": {"counts": {"tls_server_config": 1, "ssh_server_config": 1}}
    }
  },
  "tls_metadata": {
    "collected": true,
    "certificate": {
      "public_key_algorithm": "RSA",
      "public_key_size": 1024,
      "not_after": "2026-06-01T00:00:00Z"
    },
    "certificate_chain": {"available": true, "length": 2}
  }
}
JSON

curl -sS -f -X POST "http://127.0.0.1:8002/score" -H "Content-Type: application/json" --data-binary "@$ROOT_DIR/reports/.stage3-risk-input.json" > "$risk_resp"

for p in ".normalized_score_100" ".confidence_score" ".risk_dimensions.exposure" ".risk_dimensions.impact" ".risk_dimensions.urgency" ".risk_dimensions.migration_complexity" ".stage2_signals.evidence_signals"; do
  json_assert_non_null "$risk_resp" "$p"
done

signal_any="$(python3 - "$risk_resp" <<'PY'
import json,sys
with open(sys.argv[1],encoding='utf-8') as f:
    data=json.load(f)
s=data.get('stage2_signals',{}).get('evidence_signals',{})
print(str(bool(s.get('weak_public_key_detected') or s.get('private_key_files_detected') or s.get('expiring_certificate_detected'))).lower())
PY
)"
[[ "$signal_any" == "true" ]] || { echo "No required stage2 evidence signal present" >&2; exit 1; }

curl -sS -f "http://127.0.0.1:8004/plan" > "$plan_resp"

python3 - "$plan_resp" <<'PY'
import json,sys
with open(sys.argv[1],encoding='utf-8') as f:
    data=json.load(f)
all_items=[]
for w in ('wave_1','wave_2','wave_3'):
    all_items.extend(data.get(w,[]))
if not all_items:
    raise SystemExit('Planner returned no items')
match=None
for item in all_items:
    reasons=item.get('planning_reasons') or []
    if 'priority_score_computed' in reasons:
        match=item
        break
if not match:
    raise SystemExit('No planner item contains priority_score_computed reason')
if match.get('priority_score') is None:
    raise SystemExit('priority_score is missing')
if not match.get('planning_reasons'):
    raise SystemExit('planning_reasons missing')
reasons=set(match.get('planning_reasons',[]))
wave='unknown'
for w in ('wave_1','wave_2','wave_3'):
    if match in data.get(w,[]):
        wave=w
        break
if ('stage2_weak_public_key' in reasons or 'stage2_private_key_files' in reasons) and wave=='wave_3':
    raise SystemExit('Wave cap check failed: weak/public/private key signal landed in wave_3')
print(json.dumps({'wave':wave,'priority_score':match.get('priority_score'),'reasons':match.get('planning_reasons')}))
PY

planner_summary="$(python3 - "$plan_resp" <<'PY'
import json,sys
with open(sys.argv[1],encoding='utf-8') as f:
    data=json.load(f)
for wave in ('wave_1','wave_2','wave_3'):
    for item in data.get(wave,[]):
        if 'priority_score_computed' in (item.get('planning_reasons') or []):
            print(wave)
            print(item.get('priority_score'))
            print(', '.join(item.get('planning_reasons') or []))
            has_cap=('stage2_weak_public_key' in (item.get('planning_reasons') or []) or 'stage2_private_key_files' in (item.get('planning_reasons') or []))
            print('PASS' if (not has_cap or wave != 'wave_3') else 'FAIL')
            sys.exit(0)
raise SystemExit('no planner summary item')
PY
)"

wave_assigned="$(echo "$planner_summary" | sed -n '1p')"
priority_score="$(echo "$planner_summary" | sed -n '2p')"
planning_reasons="$(echo "$planner_summary" | sed -n '3p')"
wave_cap_check="$(echo "$planner_summary" | sed -n '4p')"

host_scan_id="$(json_get "$host_resp" ".scan_id")"
host_created="$(json_get "$host_resp" ".created")"
host_assets_count="$(python3 - "$host_resp" <<'PY'
import json,sys
with open(sys.argv[1],encoding='utf-8') as f:data=json.load(f)
print(len(data.get('asset_ids',[])))
PY
)"
network_scan_id="$(json_get "$network_resp" ".scan_id")"
network_created="$(json_get "$network_resp" ".created")"
network_assets_count="$(python3 - "$network_resp" <<'PY'
import json,sys
with open(sys.argv[1],encoding='utf-8') as f:data=json.load(f)
print(len(data.get('asset_ids',[])))
PY
)"

risk_score="$(json_get "$risk_resp" ".normalized_score_100")"
risk_confidence="$(json_get "$risk_resp" ".confidence_score")"
risk_dimensions="$(json_get "$risk_resp" ".risk_dimensions")"
risk_signals="$(json_get "$risk_resp" ".stage2_signals.evidence_signals")"
risk_reasons="$(json_get "$risk_resp" ".rationale")"

now_iso="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

{
  echo "# Stage 3 Risk/Planning Smoke Report"
  echo
  echo "## Validation Date"
  echo "$now_iso"
  echo
  echo "## Scope"
  echo "- enriched evidence ingest"
  echo "- risk confidence_score"
  echo "- risk_dimensions"
  echo "- Stage 2 evidence signals"
  echo "- planner priority_score"
  echo "- planner wave rationale"
  echo
  echo "## Services Checked"
  echo
  echo "| Service | Endpoint | Status |"
  echo "|---|---|---|"
  printf '%s
' "${SERVICE_ROWS[@]}"
  echo
  echo "## Inventory Results"
  echo
  echo "- host scan_id: $host_scan_id"
  echo "- host created: $host_created"
  echo "- host asset_ids count: $host_assets_count"
  echo "- network scan_id: $network_scan_id"
  echo "- network created: $network_created"
  echo "- network asset_ids count: $network_assets_count"
  echo
  echo "## Risk Results"
  echo
  echo "- score: $risk_score"
  echo "- confidence_score: $risk_confidence"
  echo "- risk_dimensions: $risk_dimensions"
  echo "- evidence signals: $risk_signals"
  echo "- reasons: $risk_reasons"
  echo
  echo "## Planner Results"
  echo
  echo "- assigned wave: $wave_assigned"
  echo "- priority_score: $priority_score"
  echo "- planning reasons: $planning_reasons"
  echo "- wave cap check: $wave_cap_check"
  echo
  echo "## Result"
  echo
  echo "PASS"
} > "$REPORT_PATH"

rm -f "$ROOT_DIR/reports/.stage3-risk-input.json"
echo "[stage3-smoke] PASS -> $REPORT_PATH"
