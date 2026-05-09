#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INVENTORY_URL="http://127.0.0.1:8001"
INGEST_URL="${INVENTORY_URL}/scans/ingest"
FIXTURE_DIR="${ROOT_DIR}/services/inventory-service/tests/fixtures/stage2_evidence"
REPORT_PATH="${ROOT_DIR}/reports/stage2-inventory-smoke-report.md"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

has_jq=0
if command -v jq >/dev/null 2>&1; then
  has_jq=1
fi

require_success_fields() {
  local response_file="$1"
  if [[ "$has_jq" -eq 1 ]]; then
    jq -e '.scan_id and .created and (.asset_ids | type == "array")' "$response_file" >/dev/null
  else
    python3 - "$response_file" <<'PY'
import json,sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data=json.load(f)
assert data.get('scan_id')
assert data.get('created')
assert isinstance(data.get('asset_ids'), list)
PY
  fi
}

extract_field() {
  local response_file="$1"
  local field="$2"
  if [[ "$has_jq" -eq 1 ]]; then
    jq -r ".$field" "$response_file"
  else
    python3 - "$response_file" "$field" <<'PY'
import json,sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data=json.load(f)
print(data.get(sys.argv[2], ""))
PY
  fi
}

extract_asset_count() {
  local response_file="$1"
  if [[ "$has_jq" -eq 1 ]]; then
    jq -r '(.asset_ids | length)' "$response_file"
  else
    python3 - "$response_file" <<'PY'
import json,sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data=json.load(f)
print(len(data.get('asset_ids') or []))
PY
  fi
}

check_health() {
  local status
  status=$(curl -sS -o /dev/null -w "%{http_code}" "${INVENTORY_URL}/health")
  [[ "$status" == "200" ]]
}

post_fixture_expect_success() {
  local fixture_name="$1"
  local response_file="$2"
  local status
  status=$(curl -sS -o "$response_file" -w "%{http_code}" -X POST "$INGEST_URL" -H "Content-Type: application/json" --data-binary "@${FIXTURE_DIR}/${fixture_name}")
  [[ "$status" =~ ^2[0-9][0-9]$ ]]
  require_success_fields "$response_file"
  echo "$status"
}

post_fixture_expect_failure() {
  local fixture_name="$1"
  local response_file="$2"
  local status
  status=$(curl -sS -o "$response_file" -w "%{http_code}" -X POST "$INGEST_URL" -H "Content-Type: application/json" --data-binary "@${FIXTURE_DIR}/${fixture_name}")
  if [[ "$status" =~ ^2[0-9][0-9]$ ]]; then
    echo "Invalid fixture ${fixture_name} was unexpectedly accepted with HTTP ${status}." >&2
    return 1
  fi
  [[ "$status" =~ ^4[0-9][0-9]$ ]]
  echo "$status"
}

check_health

min_response="${TMP_DIR}/minimal.json"
host_response="${TMP_DIR}/host.json"
network_response="${TMP_DIR}/network.json"
invalid_tls_response="${TMP_DIR}/invalid_tls.json"
invalid_pkg_response="${TMP_DIR}/invalid_package.json"

post_fixture_expect_success "minimal_ingest.json" "$min_response" >/dev/null
post_fixture_expect_success "host_enriched_ingest.json" "$host_response" >/dev/null
post_fixture_expect_success "network_enriched_ingest.json" "$network_response" >/dev/null

invalid_tls_status=$(post_fixture_expect_failure "invalid_tls_metadata.json" "$invalid_tls_response")
invalid_package_status=$(post_fixture_expect_failure "invalid_package_metadata.json" "$invalid_pkg_response")

mkdir -p "${ROOT_DIR}/reports"
validation_date="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat > "$REPORT_PATH" <<REPORT
# Stage 2 Inventory Smoke Report

## Validation Date
${validation_date}

## Scope
- minimal Stage 1-compatible ingest
- enriched host evidence ingest
- enriched network TLS evidence ingest
- invalid enriched payload rejection

## Fixtures Used

| Fixture | Expected | Result |
|---|---|---|
| minimal_ingest.json | 2xx + scan metadata fields | PASS |
| host_enriched_ingest.json | 2xx + scan metadata fields | PASS |
| network_enriched_ingest.json | 2xx + scan metadata fields | PASS |
| invalid_tls_metadata.json | HTTP 4xx validation failure | HTTP ${invalid_tls_status} |
| invalid_package_metadata.json | HTTP 4xx validation failure | HTTP ${invalid_package_status} |

## Success Responses

- minimal scan_id: $(extract_field "$min_response" "scan_id"), created: $(extract_field "$min_response" "created"), asset_ids count: $(extract_asset_count "$min_response")
- host enriched scan_id: $(extract_field "$host_response" "scan_id"), created: $(extract_field "$host_response" "created"), asset_ids count: $(extract_asset_count "$host_response")
- network enriched scan_id: $(extract_field "$network_response" "scan_id"), created: $(extract_field "$network_response" "created"), asset_ids count: $(extract_asset_count "$network_response")

## Invalid Fixture Results

- invalid_tls_metadata.json status: HTTP ${invalid_tls_status}
- invalid_package_metadata.json status: HTTP ${invalid_package_status}

## Result

PASS
REPORT

echo "Stage 2 inventory smoke report written to: ${REPORT_PATH}"
