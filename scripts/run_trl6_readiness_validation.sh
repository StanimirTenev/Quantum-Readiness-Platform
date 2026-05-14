#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

REPORT_DIR="reports/trl6"
EVIDENCE_DIR="$REPORT_DIR/evidence"
REPORT_FILE="$REPORT_DIR/trl6-readiness-report.md"

mkdir -p "$REPORT_DIR" "$EVIDENCE_DIR"

UTC_NOW="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

COMMANDS=(
  "bash scripts/run_trl_validation.sh"
  "bash scripts/run_stage2_inventory_smoke.sh"
  "bash scripts/run_stage2_e2e_smoke.sh"
  "bash scripts/run_stage3_risk_planning_smoke.sh"
  "bash scripts/run_graph_projection_smoke.sh"
  "bash scripts/run_graph_snapshot_loader_smoke.sh"
  "bash scripts/run_graph_api_readonly_smoke.sh"
  "bash scripts/run_copilot_offline_smoke.sh"
  "bash scripts/run_copilot_safety_contract_smoke.sh"
  "bash scripts/run_evidence_pack_index.sh"
)

RESULT_ROWS=()
OVERALL_FAIL=0

run_command() {
  local command="$1"
  local command_name
  command_name="$(basename "$(awk '{print $2}' <<<"$command")" .sh)"
  local safe_name
  safe_name="$(echo "$command_name" | tr -c 'a-zA-Z0-9._-' '_')"
  local log_file="$EVIDENCE_DIR/${safe_name}.log"

  local started_at ended_at status
  started_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

  if eval "$command" >"$log_file" 2>&1; then
    status="PASS"
  else
    status="FAIL"
    OVERALL_FAIL=1
  fi

  ended_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  RESULT_ROWS+=("| \`$command\` | $status | $started_at | $ended_at | \`$log_file\` |")
}

for cmd in "${COMMANDS[@]}"; do
  run_command "$cmd"
done

OVERALL_RESULT="PASS"
if [[ "$OVERALL_FAIL" -ne 0 ]]; then
  OVERALL_RESULT="FAIL"
fi

{
  echo "# TRL 6 Readiness Validation Report"
  echo
  echo "- **UTC Timestamp:** $UTC_NOW"
  echo "- **Purpose:** Deterministic orchestration of existing local validation/smoke commands to support TRL 6 readiness assessment evidence collection."
  echo "- **Relevant Environment Assumption:** Local-first execution in a controlled operator environment; no internet, no external LLM, and no graph database required by this orchestration script."
  echo
  echo "## Command Results"
  echo
  echo "| Command | Result | Started (UTC) | Ended (UTC) | Evidence Log |"
  echo "| --- | --- | --- | --- | --- |"
  for row in "${RESULT_ROWS[@]}"; do
    echo "$row"
  done
  echo
  echo "## Evidence Log Paths"
  echo
  echo "- Evidence directory: \`$EVIDENCE_DIR\`"
  echo "- Consolidated report: \`$REPORT_FILE\`"
  echo
  echo "## Acceptance Criteria Checklist"
  echo
  echo "- [x] Existing validation/smoke commands executed in deterministic sequence."
  echo "- [x] Per-command PASS/FAIL recorded."
  echo "- [x] Per-command UTC start/end timestamps recorded."
  echo "- [x] Per-command stdout/stderr persisted to evidence logs."
  if [[ "$OVERALL_RESULT" == "PASS" ]]; then
    echo "- [x] Overall result is PASS because all required commands passed."
  else
    echo "- [x] Overall result is FAIL because one or more required commands failed."
  fi
  echo
  echo "## Boundary Statements"
  echo
  echo "- This report supports TRL 6 readiness assessment only."
  echo "- TRL 6 is not claimed until successful relevant-environment demo execution and operator review."
  echo "- No external LLM, graph database, or autonomous remediation is required."
  echo
  echo "## Overall Result"
  echo
  echo "**$OVERALL_RESULT**"
} > "$REPORT_FILE"

if [[ "$OVERALL_FAIL" -ne 0 ]]; then
  echo "TRL 6 readiness validation completed with FAIL. See $REPORT_FILE" >&2
  exit 1
fi

echo "TRL 6 readiness validation completed with PASS. See $REPORT_FILE"
