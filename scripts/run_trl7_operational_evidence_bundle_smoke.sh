#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

JSON_PATH="reports/trl7/operational-evidence/trl7-operational-evidence-bundle-index.json"
MD_PATH="reports/trl7/operational-evidence/trl7-operational-evidence-bundle-index.md"
DRY_RUN_PATH="reports/trl7/trl7-operational-dry-run-report.md"
SMOKE_REPORT_PATH="reports/trl7/operational-evidence/trl7-operational-evidence-bundle-smoke-report.md"

TIMESTAMP_UTC="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
FAIL=0

declare -a CHECKED_FILES=()
declare -a JSON_STRUCTURE_CHECKS=()
declare -a SUMMARY_CHECKS=()
declare -a REQUIRED_ARTIFACT_CHECKS=()
declare -a BOUNDARY_CHECKS=()
declare -a MISSING_REQUIRED_ARTIFACTS=()

record_pass() {
  local section="$1"
  local message="$2"
  case "$section" in
    json) JSON_STRUCTURE_CHECKS+=("- PASS: ${message}") ;;
    summary) SUMMARY_CHECKS+=("- PASS: ${message}") ;;
    required) REQUIRED_ARTIFACT_CHECKS+=("- PASS: ${message}") ;;
    boundary) BOUNDARY_CHECKS+=("- PASS: ${message}") ;;
  esac
}

record_fail() {
  local section="$1"
  local message="$2"
  FAIL=1
  case "$section" in
    json) JSON_STRUCTURE_CHECKS+=("- FAIL: ${message}") ;;
    summary) SUMMARY_CHECKS+=("- FAIL: ${message}") ;;
    required) REQUIRED_ARTIFACT_CHECKS+=("- FAIL: ${message}") ;;
    boundary) BOUNDARY_CHECKS+=("- FAIL: ${message}") ;;
  esac
}

if [[ ! -f "$JSON_PATH" || ! -f "$MD_PATH" || ! -f "$DRY_RUN_PATH" ]]; then
  bash scripts/run_trl7_operational_evidence_bundle.sh
else
  # Refresh bundle index to validate current integrity/boundary expectations.
  bash scripts/run_trl7_operational_evidence_bundle.sh
fi

for file_path in "$JSON_PATH" "$MD_PATH" "$DRY_RUN_PATH"; do
  CHECKED_FILES+=("- ${file_path}")
  if [[ -f "$file_path" ]]; then
    record_pass required "File exists: ${file_path}"
  else
    record_fail required "Missing required file: ${file_path}"
  fi
done

for required_text in \
  "This bundle supports TRL7 operational pilot preparation only." \
  "TRL 7 achieved is not claimed by this bundle." \
  "Production readiness is not claimed by this bundle." \
  "This bundle does not run tests, start services, regenerate evidence, or perform remediation."; do
  if grep -Fq "$required_text" "$MD_PATH"; then
    record_pass boundary "Markdown contains boundary statement: ${required_text}"
  else
    record_fail boundary "Markdown missing boundary statement: ${required_text}"
  fi
done

if python3 - "$JSON_PATH" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data = json.load(f)
for key in ("generated_at_utc", "artifacts", "summary"):
    if key not in data:
        raise SystemExit(1)
PY
then
  record_pass json "JSON includes top-level keys: generated_at_utc, artifacts, summary"
else
  record_fail json "JSON missing one or more top-level keys: generated_at_utc, artifacts, summary"
fi

SUMMARY_FIELD_OUTPUT="$(python3 - "$JSON_PATH" <<'PY'
import json, sys
with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data = json.load(f)
summary = data.get("summary", {})
fields = [
    "total_artifacts", "present", "missing", "required_present", "required_missing",
    "pass_hint_count", "fail_hint_count", "unknown_hint_count", "review_required_count"
]
missing = [f for f in fields if f not in summary]
required_missing_value = summary.get("required_missing")
print("MISSING_FIELDS=" + ",".join(missing))
print("REQUIRED_MISSING=" + (str(required_missing_value) if required_missing_value is not None else ""))
artifacts = data.get("artifacts", [])
required_dry_run_present = None
for a in artifacts:
    if isinstance(a, dict) and a.get("path") == "reports/trl7/trl7-operational-dry-run-report.md":
        required_dry_run_present = a.get("present")
        break
print("DRY_RUN_PRESENT=" + ("true" if required_dry_run_present is True else "false" if required_dry_run_present is False else "unknown"))
if required_missing_value not in (None, 0):
    missing_required = [a.get("path") for a in artifacts if isinstance(a, dict) and a.get("required") is True and a.get("present") is not True]
    print("MISSING_REQUIRED_ARTIFACTS=" + "|".join([m for m in missing_required if m]))
else:
    print("MISSING_REQUIRED_ARTIFACTS=")
PY
)"

MISSING_FIELDS="$(echo "$SUMMARY_FIELD_OUTPUT" | awk -F= '/^MISSING_FIELDS=/{print $2}')"
REQUIRED_MISSING_VALUE="$(echo "$SUMMARY_FIELD_OUTPUT" | awk -F= '/^REQUIRED_MISSING=/{print $2}')"
DRY_RUN_PRESENT="$(echo "$SUMMARY_FIELD_OUTPUT" | awk -F= '/^DRY_RUN_PRESENT=/{print $2}')"
MISSING_REQUIRED_LIST_RAW="$(echo "$SUMMARY_FIELD_OUTPUT" | awk -F= '/^MISSING_REQUIRED_ARTIFACTS=/{print $2}')"

if [[ -z "$MISSING_FIELDS" ]]; then
  record_pass summary "Summary includes required fields"
else
  record_fail summary "Summary missing required fields: ${MISSING_FIELDS}"
fi

if [[ "$REQUIRED_MISSING_VALUE" == "0" ]]; then
  record_pass summary "summary.required_missing is 0"
else
  record_fail summary "summary.required_missing is not 0 (value: ${REQUIRED_MISSING_VALUE:-unset})"
fi

if [[ "$DRY_RUN_PRESENT" == "true" ]]; then
  record_pass required "Required dry-run report is marked present in JSON artifacts"
elif [[ "$DRY_RUN_PRESENT" == "false" ]]; then
  record_fail required "Required dry-run report is marked missing in JSON artifacts"
else
  record_fail required "Could not determine required dry-run report presence from JSON artifacts"
fi

if [[ -n "$MISSING_REQUIRED_LIST_RAW" ]]; then
  IFS='|' read -r -a MISSING_REQUIRED_ARTIFACTS <<< "$MISSING_REQUIRED_LIST_RAW"
  for item in "${MISSING_REQUIRED_ARTIFACTS[@]}"; do
    REQUIRED_ARTIFACT_CHECKS+=("- INFO: Missing required artifact from JSON: ${item}")
  done
fi

RESULT="PASS"
if [[ "$FAIL" -ne 0 ]]; then
  RESULT="FAIL"
fi

{
  echo "# TRL7 Operational Evidence Bundle Smoke Report"
  echo
  echo "- UTC timestamp: ${TIMESTAMP_UTC}"
  echo "- Result: ${RESULT}"
  echo
  echo "## Checked files"
  printf '%s\n' "${CHECKED_FILES[@]}"
  echo
  echo "## JSON structure checks"
  printf '%s\n' "${JSON_STRUCTURE_CHECKS[@]}"
  echo
  echo "## Summary checks"
  printf '%s\n' "${SUMMARY_CHECKS[@]}"
  echo
  echo "## Required artifact presence checks"
  printf '%s\n' "${REQUIRED_ARTIFACT_CHECKS[@]}"
  echo
  echo "## Boundary statement checks"
  printf '%s\n' "${BOUNDARY_CHECKS[@]}"
  echo
  echo "This smoke validates TRL7 operational evidence bundle integrity only."
  echo "This smoke does not claim TRL 7 achieved or production readiness."
} > "$SMOKE_REPORT_PATH"

echo "Wrote: ${SMOKE_REPORT_PATH}"
echo "Result: ${RESULT}"

if [[ "$FAIL" -ne 0 ]]; then
  exit 1
fi
