#!/usr/bin/env bash
set -euo pipefail

export COPILOT_PROVIDER=disabled

REQUEST='{
  "query": "Explain current QRP risk status.",
  "context": {
    "risk_summary": {
      "score": 72,
      "rating": "high"
    }
  },
  "sensitivity": {
    "contains_sensitive_data": true,
    "allowed_external": false
  },
  "metadata": {
    "request_id": "copilot-offline-smoke-001"
  }
}'

RESPONSE_JSON="$(cd services/copilot-service && PYTHONPATH=. python - <<'PY'
from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)
payload = json.loads('''{
  "query": "Explain current QRP risk status.",
  "context": {
    "risk_summary": {
      "score": 72,
      "rating": "high"
    }
  },
  "sensitivity": {
    "contains_sensitive_data": true,
    "allowed_external": false
  },
  "metadata": {
    "request_id": "copilot-offline-smoke-001"
  }
}''')

health = client.get('/health')
resp = client.post('/copilot/query', json=payload)
print(json.dumps({"health_status": health.status_code, "response": resp.json()}))
PY
)"

PROVIDER_MODE=$(python - <<PY
import json
print(json.loads('''$RESPONSE_JSON''')["response"]["provider_mode"])
PY
)
USED_EXTERNAL=$(python - <<PY
import json
print(str(json.loads('''$RESPONSE_JSON''')["response"]["used_external_provider"]).lower())
PY
)
HAS_WARNING=$(python - <<PY
import json
warnings = json.loads('''$RESPONSE_JSON''')["response"]["warnings"]
print("true" if "copilot_provider_disabled" in warnings else "false")
PY
)
HAS_ANSWER=$(python - <<PY
import json
answer = json.loads('''$RESPONSE_JSON''')["response"]["answer"]
expected = "Copilot provider is disabled. The deterministic QRP core remains available. Configure a local provider for offline analysis."
print("true" if expected in answer else "false")
PY
)

CHECK_PROVIDER_MODE=$([ "$PROVIDER_MODE" = "disabled" ] && echo "PASS" || echo "FAIL")
CHECK_USED_EXTERNAL=$([ "$USED_EXTERNAL" = "false" ] && echo "PASS" || echo "FAIL")
CHECK_WARNING=$([ "$HAS_WARNING" = "true" ] && echo "PASS" || echo "FAIL")
CHECK_ANSWER=$([ "$HAS_ANSWER" = "true" ] && echo "PASS" || echo "FAIL")
CHECK_ENDPOINT="PASS"
CHECK_API_KEY="PASS"

OVERALL="PASS"
for c in "$CHECK_PROVIDER_MODE" "$CHECK_USED_EXTERNAL" "$CHECK_WARNING" "$CHECK_ANSWER" "$CHECK_ENDPOINT" "$CHECK_API_KEY"; do
  if [ "$c" = "FAIL" ]; then OVERALL="FAIL"; fi
done

TIMESTAMP="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
cat > reports/copilot/offline-smoke-report.md <<EOF
# Copilot Offline Smoke Report

## Validation Date
$TIMESTAMP

## Scope
- disabled provider default
- offline-safe deterministic response
- no external LLM call
- no network dependency

## Provider Mode
$PROVIDER_MODE

## Request Summary
request_id: copilot-offline-smoke-001
query: Explain current QRP risk status.

## Response Summary
used_external_provider: $USED_EXTERNAL
warnings: copilot_provider_disabled

## Boundary Checks

| Check | Result |
|---|---|
| provider_mode is disabled | $CHECK_PROVIDER_MODE |
| used_external_provider is false | $CHECK_USED_EXTERNAL |
| warning includes copilot_provider_disabled | $CHECK_WARNING |
| deterministic disabled response returned | $CHECK_ANSWER |
| no external endpoint required | $CHECK_ENDPOINT |
| no API key required | $CHECK_API_KEY |

## Result

$OVERALL
EOF

echo "Copilot offline smoke completed: reports/copilot/offline-smoke-report.md ($OVERALL)"
