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
PREFLIGHT_LOG_PATH="${EVIDENCE_DIR}/preflight.log"

mkdir -p "${REPORT_DIR}" "${EVIDENCE_DIR}"

PREFLIGHT_CHECKS=()
PREFLIGHT_REQUIRED=()
PREFLIGHT_STATUSES=()
PREFLIGHT_DETAILS=()
REQUIRED_PREFLIGHT_FAILURES=0
OPTIONAL_PREFLIGHT_WARNINGS=0

record_preflight() {
  local check_name="$1"
  local required="$2"
  local status="$3"
  local detail="$4"

  PREFLIGHT_CHECKS+=("${check_name}")
  PREFLIGHT_REQUIRED+=("${required}")
  PREFLIGHT_STATUSES+=("${status}")
  PREFLIGHT_DETAILS+=("${detail}")

  if [[ "${required}" == "yes" && "${status}" == "FAIL" ]]; then
    REQUIRED_PREFLIGHT_FAILURES=$((REQUIRED_PREFLIGHT_FAILURES + 1))
  fi
  if [[ "${required}" == "no" && "${status}" == "WARN" ]]; then
    OPTIONAL_PREFLIGHT_WARNINGS=$((OPTIONAL_PREFLIGHT_WARNINGS + 1))
  fi
}

run_preflight() {
  if [[ "$(pwd)" == "${REPO_ROOT}" && -d .git && -d scripts ]]; then
    record_preflight "running_from_repository_root" "yes" "PASS" "Working directory appears to be repository root."
  else
    record_preflight "running_from_repository_root" "yes" "FAIL" "Must execute from repository root containing .git and scripts/."
  fi

  if [[ -d scripts ]]; then
    record_preflight "scripts_directory_exists" "yes" "PASS" "scripts/ directory exists."
  else
    record_preflight "scripts_directory_exists" "yes" "FAIL" "scripts/ directory is missing."
  fi

  if mkdir -p reports && [[ -w reports ]]; then
    record_preflight "reports_directory_writable" "yes" "PASS" "reports/ can be created and written."
  else
    record_preflight "reports_directory_writable" "yes" "FAIL" "reports/ cannot be created or written."
  fi

  if mkdir -p "${REPORT_DIR}" && [[ -w "${REPORT_DIR}" ]]; then
    record_preflight "reports_trl7_directory_writable" "yes" "PASS" "${REPORT_DIR}/ can be created and written."
  else
    record_preflight "reports_trl7_directory_writable" "yes" "FAIL" "${REPORT_DIR}/ cannot be created or written."
  fi

  if mkdir -p "${EVIDENCE_DIR}" && [[ -w "${EVIDENCE_DIR}" ]]; then
    record_preflight "reports_trl7_operational_evidence_directory_writable" "yes" "PASS" "${EVIDENCE_DIR}/ can be created and written."
  else
    record_preflight "reports_trl7_operational_evidence_directory_writable" "yes" "FAIL" "${EVIDENCE_DIR}/ cannot be created or written."
  fi

  local required_scripts=(
    "scripts/start_all.sh"
    "scripts/status_all.sh"
    "scripts/run_trl6_readiness_validation.sh"
    "scripts/run_evidence_pack_index.sh"
    "scripts/run_trl6_demo_bundle.sh"
    "scripts/run_trl6_demo_bundle_smoke.sh"
    "scripts/run_graph_api_readonly_smoke.sh"
  )

  for required_script in "${required_scripts[@]}"; do
    if [[ -f "${required_script}" ]]; then
      record_preflight "required_script_exists:${required_script}" "yes" "PASS" "Required script is present."
    else
      record_preflight "required_script_exists:${required_script}" "yes" "FAIL" "Required script is missing."
    fi
  done

  if command -v python3 >/dev/null 2>&1; then
    record_preflight "python3_available" "yes" "PASS" "python3 is available in PATH."
  else
    record_preflight "python3_available" "yes" "FAIL" "python3 is not available in PATH."
  fi

  if command -v bash >/dev/null 2>&1; then
    record_preflight "bash_available" "yes" "PASS" "bash is available in PATH."
  else
    record_preflight "bash_available" "yes" "FAIL" "bash is not available in PATH."
  fi

  if command -v git >/dev/null 2>&1; then
    record_preflight "git_available" "no" "PASS" "git is available in PATH."
  else
    record_preflight "git_available" "no" "WARN" "git is not available in PATH."
  fi

  if command -v pytest >/dev/null 2>&1; then
    record_preflight "pytest_available" "no" "PASS" "pytest is available in PATH."
  else
    record_preflight "pytest_available" "no" "WARN" "pytest is not available in PATH."
  fi
}

run_preflight

{
  echo "timestamp_utc=${TIMESTAMP_UTC}"
  for i in "${!PREFLIGHT_CHECKS[@]}"; do
    printf '%s	%s	%s	%s
' "${PREFLIGHT_CHECKS[$i]}" "${PREFLIGHT_REQUIRED[$i]}" "${PREFLIGHT_STATUSES[$i]}" "${PREFLIGHT_DETAILS[$i]}"
  done
} >"${PREFLIGHT_LOG_PATH}"

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
EXECUTION_SKIPPED="no"

if [[ "${REQUIRED_PREFLIGHT_FAILURES}" -gt 0 ]]; then
  OVERALL_STATUS="FAIL"
  EXECUTION_SKIPPED="yes"
fi

if [[ "${EXECUTION_SKIPPED}" == "no" ]]; then
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
      printf 'Required command script missing: %s
' "${cmd}" >"${log_path}"
      status="FAIL"
      OVERALL_STATUS="FAIL"
    fi

    STATUSES+=("${status}")
  done
fi

{
  echo "# TRL7 Operational Validation Dry-Run Report"
  echo
  echo "- UTC Timestamp: ${TIMESTAMP_UTC}"
  echo "- Purpose: Deterministic orchestration/reporting rehearsal for TRL7 operational pilot preparation."
  echo "- Mode: DRY_RUN / PILOT_REHEARSAL"
  echo
  echo "## Preflight Results"
  echo
  echo "| Check | Required | Status | Detail |"
  echo "| --- | --- | --- | --- |"
  for i in "${!PREFLIGHT_CHECKS[@]}"; do
    printf '| `%s` | %s | %s | %s |
' "${PREFLIGHT_CHECKS[$i]}" "${PREFLIGHT_REQUIRED[$i]}" "${PREFLIGHT_STATUSES[$i]}" "${PREFLIGHT_DETAILS[$i]}"
  done
  echo
  echo "- required_preflight_failures: ${REQUIRED_PREFLIGHT_FAILURES}"
  echo "- optional_preflight_warnings: ${OPTIONAL_PREFLIGHT_WARNINGS}"
  echo "- preflight_log: ${PREFLIGHT_LOG_PATH}"

  echo
  echo "## Command Results"
  echo
  echo "| Command | Status | Log |"
  echo "| --- | --- | --- |"

  if [[ "${EXECUTION_SKIPPED}" == "yes" ]]; then
    echo "| _Command execution skipped_ | FAIL | `core preflight checks failed; see preflight section` |"
  else
    for i in "${!COMMANDS[@]}"; do
      printf '| `%s` | %s | `%s` |
' "${COMMANDS[$i]}" "${STATUSES[$i]}" "${LOGS[$i]}"
    done
  fi

  echo
  echo "## Log Paths"
  echo "- ${PREFLIGHT_LOG_PATH}"
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
