#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

REPORT_PATH="reports/copilot/safety-contract-smoke-report.md"
mkdir -p "$(dirname "$REPORT_PATH")"

TIMESTAMP_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || true)"
if [ -z "$TIMESTAMP_UTC" ]; then
  TIMESTAMP_UTC="unavailable"
fi

CHECK_RESULTS=()
OVERALL="PASS"

required_files=(
  "services/copilot-service/app/provider_config.py"
  "services/copilot-service/app/local_url_validation.py"
  "services/copilot-service/app/context_packaging.py"
)

for file in "${required_files[@]}"; do
  if [ -f "$file" ]; then
    CHECK_RESULTS+=("$file|PASS")
  else
    CHECK_RESULTS+=("$file|FAIL")
    OVERALL="FAIL"
  fi
done

PYTEST_RESULT="PASS"
if ! (cd services/copilot-service && PYTHONPATH=. pytest -q); then
  PYTEST_RESULT="FAIL"
  OVERALL="FAIL"
fi
CHECK_RESULTS+=("services/copilot-service pytest -q|$PYTEST_RESULT")

OPTIONAL_SMOKE_STATUS="SKIPPED"
OPTIONAL_SMOKE_SCRIPT="scripts/run_copilot_offline_smoke.sh"
if [ -r "$OPTIONAL_SMOKE_SCRIPT" ] && [ -x "$OPTIONAL_SMOKE_SCRIPT" ]; then
  OPTIONAL_SMOKE_STATUS="PASS"
  if ! bash "$OPTIONAL_SMOKE_SCRIPT"; then
    OPTIONAL_SMOKE_STATUS="FAIL"
    OVERALL="FAIL"
  fi
fi
CHECK_RESULTS+=("optional $OPTIONAL_SMOKE_SCRIPT|$OPTIONAL_SMOKE_STATUS")

{
  echo "# Copilot Safety Contract Smoke Report"
  echo
  echo "## Timestamp (UTC)"
  echo "$TIMESTAMP_UTC"
  echo
  echo "## Scope"
  echo "- Validate Copilot safety-contract helper module presence."
  echo "- Run focused offline Copilot service tests."
  echo "- Optionally run existing Copilot offline smoke script when available."
  echo
  echo "## Checks Run"
  echo "| Check | Result |"
  echo "|---|---|"
  for row in "${CHECK_RESULTS[@]}"; do
    check_name="${row%%|*}"
    check_result="${row##*|}"
    echo "| $check_name | $check_result |"
  done
  echo
  echo "## Contract Statements"
  echo "- No local or external Copilot provider is implemented or activated by this smoke."
  echo "- No network access is required for this smoke."
  echo
  echo "## Result"
  echo "$OVERALL"
} > "$REPORT_PATH"

echo "Copilot safety-contract smoke completed: $REPORT_PATH ($OVERALL)"

if [ "$OVERALL" = "FAIL" ]; then
  exit 1
fi
