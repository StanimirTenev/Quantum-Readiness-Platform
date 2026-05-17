#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

REPORT_DIR="reports/trl7"
EVIDENCE_DIR="${REPORT_DIR}/operational-evidence"
REPORT_PATH="${REPORT_DIR}/trl7-operational-dry-run-report.md"
KNOWN_LIMITATIONS_PATH="${REPORT_DIR}/trl7-operational-dry-run-known-limitations.md"
TIMESTAMP_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

mkdir -p "${REPORT_DIR}" "${EVIDENCE_DIR}"

COMMANDS=(
  "bash scripts/start_all.sh"
  "bash scripts/status_all.sh"
  "bash scripts/run_trl6_readiness_validation.sh"
  "bash scripts/run_evidence_pack_index.sh"
  "bash scripts/run_trl6_demo_bundle.sh"
  "bash scripts/run_trl6_demo_bundle_smoke.sh"
  "bash scripts/run_graph_api_readonly_smoke.sh"
)

STATUSES=()
LOGS=()
OVERALL_STATUS="PASS"

for cmd in "${COMMANDS[@]}"; do
  cmd_slug="$(echo "${cmd}" | tr ' /' '__' | tr -cd '[:alnum:]_.-')"
  log_path="${EVIDENCE_DIR}/${cmd_slug}.log"
  LOGS+=("${log_path}")

  if [[ -f "${cmd#bash }" ]]; then
    if bash -c "${cmd}" >"${log_path}" 2>&1; then
      status="PASS"
    else
      status="FAIL"
      OVERALL_STATUS="FAIL"
    fi
  else
    printf 'Required command script missing: %s\n' "${cmd}" >"${log_path}"
    status="FAIL"
    OVERALL_STATUS="FAIL"
  fi

  STATUSES+=("${status}")
done

{
  echo "# TRL7 Operational Validation Dry-Run Report"
  echo
  echo "- UTC Timestamp: ${TIMESTAMP_UTC}"
  echo "- Purpose: Deterministic orchestration/reporting rehearsal for TRL7 operational pilot preparation."
  echo "- Mode: DRY_RUN / PILOT_REHEARSAL"
  echo
  echo "## Command Results"
  echo
  echo "| Command | Status | Log |"
  echo "| --- | --- | --- |"

  for i in "${!COMMANDS[@]}"; do
    printf '| `%s` | %s | `%s` |\n' "${COMMANDS[$i]}" "${STATUSES[$i]}" "${LOGS[$i]}"
  done

  echo
  echo "## Log Paths"
  for log in "${LOGS[@]}"; do
    echo "- ${log}"
  done

  echo
  echo "## Evidence Paths Reviewed"
  echo "- reports/trl6/"
  echo "- reports/evidence-pack/"
  echo "- reports/graph/latest/"
  echo "- reports/trl7/operational-evidence/"

  echo
  echo "## Operational Pilot Readiness Checklist Summary"
  echo "- Dry-run orchestration executed local validation/reporting commands only."
  echo "- Command outcomes and logs are captured for operator/reviewer pre-pilot inspection."
  echo "- Any FAIL entry indicates remediation is pending before external/operator pilot scheduling."

  echo
  echo "## Result"
  echo "- ${OVERALL_STATUS}"

  echo
  echo "## Boundaries"
  echo "- This dry-run supports TRL7 operational pilot preparation only."
  echo "- TRL 7 achieved is not claimed by this dry-run."
  echo "- Production readiness is not claimed by this dry-run."
  echo "- No autonomous remediation, graph database, external LLM, Windows agent, or real Copilot provider is required."
  echo "- No new secrets were collected."
  echo "- No production systems were modified."
  echo "- Internet access, external LLM, and graph DB are not required."
  echo "- Remediation actions are not performed by this script."
  echo "- Known limitations: ${KNOWN_LIMITATIONS_PATH}"
} >"${REPORT_PATH}"

if [[ "${OVERALL_STATUS}" != "PASS" ]]; then
  exit 1
fi
