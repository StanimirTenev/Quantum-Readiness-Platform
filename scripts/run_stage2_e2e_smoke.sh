#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPORT_PATH="$ROOT_DIR/reports/stage2-e2e-smoke-report.md"
INVENTORY_URL="http://127.0.0.1:8001"; RISK_URL="http://127.0.0.1:8002"; PLANNER_URL="http://127.0.0.1:8004"
HOST_FIXTURE="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json"
NETWORK_FIXTURE="$ROOT_DIR/services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json"
TMP_DIR="$(mktemp -d)"; trap 'rm -rf "$TMP_DIR"' EXIT

curl -fsS "$INVENTORY_URL/health" >/dev/null; curl -fsS "$RISK_URL/health" >/dev/null; curl -fsS "$PLANNER_URL/health" >/dev/null
curl -fsS -X POST "$INVENTORY_URL/scans/ingest?auto_score=true&scenario=public_timeline" -H "Content-Type: application/json" --data @"$HOST_FIXTURE" > "$TMP_DIR/host_ingest.json"
curl -fsS -X POST "$INVENTORY_URL/scans/ingest?auto_score=true&scenario=public_timeline" -H "Content-Type: application/json" --data @"$NETWORK_FIXTURE" > "$TMP_DIR/network_ingest.json"
python3 - "$TMP_DIR/host_ingest.json" "$TMP_DIR/network_ingest.json" <<'PY'
import json,sys
for p in sys.argv[1:]:
 d=json.load(open(p)); assert all(k in d for k in ('scan_id','created','asset_ids')); assert isinstance(d['asset_ids'],list) and len(d['asset_ids'])>0
PY
cat > "$TMP_DIR/risk_input.json" <<'JSON'
{"contract_version":"stage2-v1","asset_name":"stage2-smoke-risk-asset","criticality":4,"confidentiality_lifetime":4,"quantum_exposure":4,"blast_radius":3,"vendor_lock_in":2,"migration_difficulty":3,"dependency_count":8,"vendor_blocked":false,"scenario":"public_timeline","stage2_notes":"HNDL signal observed","crypto_evidence":{"cert_indicators":{"certificate_file_indicators":{"counts":{"certificate":1,"key":1}},"config_file_indicators":{"counts":{"tls_server_config":1,"ssh_server_config":0}}},"package_metadata":{"packages":["openssl"]}},"tls_metadata":{"collected":true,"certificate":{"public_key_algorithm":"RSA","public_key_size":1024},"certificate_chain":{"available":true,"length":2}}}
JSON
curl -fsS -X POST "$RISK_URL/score" -H "Content-Type: application/json" --data @"$TMP_DIR/risk_input.json" > "$TMP_DIR/risk_score.json"
python3 - "$TMP_DIR/risk_score.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1])); assert ('normalized_score_100' in r or 'final_score' in r)
ev=r.get('stage2_signals',{}).get('evidence_signals',{}); assert isinstance(ev,dict)
assert any(bool(ev.get(k)) for k in ('private_key_files_detected','weak_public_key_detected','tls_detected','certificate_chain_available'))
PY
curl -fsS "$PLANNER_URL/plan" > "$TMP_DIR/plan.json"
python3 - "$TMP_DIR/plan.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); assert all(w in p for w in ('wave_1','wave_2','wave_3'))
PY
python3 - "$ROOT_DIR" > "$TMP_DIR/planner_stage2_check.json" <<'PY'
import json,sys
sys.path.insert(0,f"{sys.argv[1]}/services/planner-service")
from app.planner import build_plan
p=build_plan(assets=[{"name":"stage2-priority-host"}],risks=[{"asset_name":"stage2-priority-host","normalized_score_100":45,"rating":"medium","stage2_signals":{"evidence_signals":{"weak_public_key_detected":True}}}])
aw='wave_3'; reasons=[]
for w in ('wave_1','wave_2','wave_3'):
 if p[w]: aw=w; reasons=p[w][0].get('planning_reasons',[]); break
assert aw in ('wave_1','wave_2')
json.dump({'assigned_wave':aw,'planning_reasons':reasons,'wave2_check':'PASS'},sys.stdout)
PY
python3 - "$TMP_DIR/host_ingest.json" "$TMP_DIR/network_ingest.json" "$TMP_DIR/risk_score.json" "$TMP_DIR/planner_stage2_check.json" "$REPORT_PATH" <<'PY'
import json,sys
from datetime import datetime,UTC
h,n,r,pc=[json.load(open(x)) for x in sys.argv[1:5]]
report=sys.argv[5]
ev=r.get('stage2_signals',{}).get('evidence_signals',{})
true=[k for k,v in ev.items() if v]
content=f"""# Stage 2 E2E Smoke Report

## Validation Date
{datetime.now(UTC).isoformat()}

## Scope
- enriched host evidence ingest
- enriched network TLS evidence ingest
- Stage 2 risk signal derivation
- Stage 2 planner prioritization

## Services Checked

| Service | Endpoint | Status |
|---|---|---|
| inventory-service | http://127.0.0.1:8001/health | UP |
| risk-engine | http://127.0.0.1:8002/health | UP |
| planner-service | http://127.0.0.1:8004/health | UP |

## Fixtures Used

| Fixture | Result |
|---|---|
| services/inventory-service/tests/fixtures/stage2_evidence/host_enriched_ingest.json | PASS |
| services/inventory-service/tests/fixtures/stage2_evidence/network_enriched_ingest.json | PASS |

## Inventory Results

- host scan_id: {h['scan_id']}
- host created: {h['created']}
- host asset_ids count: {len(h['asset_ids'])}
- network scan_id: {n['scan_id']}
- network created: {n['created']}
- network asset_ids count: {len(n['asset_ids'])}

## Risk Results

- score: {r.get('normalized_score_100',r.get('final_score'))}
- stage2 adjustment: {r.get('stage2_adjustment')}
- evidence signals: {', '.join(true)}
- reasons: stage2 evidence signals derived from crypto and TLS metadata

## Planner Results

- assigned wave: {pc['assigned_wave']}
- planning reasons: {', '.join(pc['planning_reasons'])}
- no later than wave_2 check: {pc['wave2_check']}

## Result

PASS
"""
open(report,'w').write(content)
PY
echo "[stage2-e2e-smoke] Report generated at $REPORT_PATH"
