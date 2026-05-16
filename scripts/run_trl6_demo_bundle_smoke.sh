#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

bundle_json="reports/trl6/demo-bundle/trl6-demo-bundle-index.json"
bundle_md="reports/trl6/demo-bundle/trl6-demo-bundle-index.md"
smoke_report="reports/trl6/demo-bundle/trl6-demo-bundle-smoke-report.md"

required_artifacts=(
  "reports/trl6/trl6-readiness-report.md"
  "reports/trl6/operator-review-summary.md"
  "reports/trl6/operator-demo-checklist.md"
  "reports/trl6/known-limitations.md"
  "docs/trl6-readiness-plan.md"
  "docs/trl6-operator-review-boundary.md"
)

boundary_statements=(
  "This bundle supports TRL6 demo/operator review only."
  "TRL 6 achieved is not claimed by this bundle."
  "Production readiness is not claimed by this bundle."
  "This bundle does not run tests, start services, or regenerate evidence."
)

json_required_keys=("generated_at_utc" "artifacts" "summary")

if [[ ! -f "$bundle_json" || ! -f "$bundle_md" ]]; then
  bash scripts/run_trl6_demo_bundle.sh
fi

status="PASS"
checks=()
artifact_rows=()

if [[ -f "$bundle_json" ]]; then
  checks+=("PASS: exists $bundle_json")
else
  checks+=("FAIL: missing $bundle_json")
  status="FAIL"
fi

if [[ -f "$bundle_md" ]]; then
  checks+=("PASS: exists $bundle_md")
else
  checks+=("FAIL: missing $bundle_md")
  status="FAIL"
fi

for statement in "${boundary_statements[@]}"; do
  if grep -Fq "$statement" "$bundle_md"; then
    checks+=("PASS: boundary statement present: $statement")
  else
    checks+=("FAIL: boundary statement missing: $statement")
    status="FAIL"
  fi
done

for key in "${json_required_keys[@]}"; do
  if python - "$bundle_json" "$key" <<'PY'
import json
import sys
path, key = sys.argv[1], sys.argv[2]
with open(path, encoding='utf-8') as f:
    data = json.load(f)
sys.exit(0 if key in data else 1)
PY
  then
    checks+=("PASS: json root key present: $key")
  else
    checks+=("FAIL: json root key missing: $key")
    status="FAIL"
  fi
done

for artifact in "${required_artifacts[@]}"; do
  file_exists="false"
  json_marked_present="unknown"

  if [[ -f "$artifact" ]]; then
    file_exists="true"
  else
    status="FAIL"
  fi

  if python - "$bundle_json" "$artifact" <<'PY'
import json
import sys
path, artifact = sys.argv[1], sys.argv[2]
with open(path, encoding='utf-8') as f:
    data = json.load(f)
for item in data.get('artifacts', []):
    if item.get('path') == artifact:
        if item.get('exists') is True:
            sys.exit(0)
        sys.exit(2)
sys.exit(3)
PY
  then
    json_marked_present="true"
  else
    rc=$?
    if [[ $rc -eq 2 ]]; then
      json_marked_present="false"
      status="FAIL"
    else
      json_marked_present="not_listed"
      status="FAIL"
    fi
  fi

  artifact_rows+=("| $artifact | $file_exists | $json_marked_present |")
done

mkdir -p "$(dirname "$smoke_report")"
{
  echo "# TRL6 Demo Bundle Integrity Smoke Report"
  echo
  echo "UTC timestamp: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo
  echo "## Checked Files"
  echo "- $bundle_json"
  echo "- $bundle_md"
  echo
  echo "## Required Artifact Presence Summary"
  echo "| artifact | file_exists | json_marked_present |"
  echo "|---|---|---|"
  for row in "${artifact_rows[@]}"; do
    echo "$row"
  done
  echo
  echo "## Boundary Statement Checks"
  for statement in "${boundary_statements[@]}"; do
    if grep -Fq "$statement" "$bundle_md"; then
      echo "- PASS: $statement"
    else
      echo "- FAIL: $statement"
    fi
  done
  echo
  echo "## JSON Structure Checks"
  for key in "${json_required_keys[@]}"; do
    if python - "$bundle_json" "$key" <<'PY'
import json
import sys
path, key = sys.argv[1], sys.argv[2]
with open(path, encoding='utf-8') as f:
    data = json.load(f)
sys.exit(0 if key in data else 1)
PY
    then
      echo "- PASS: key present: $key"
    else
      echo "- FAIL: key missing: $key"
    fi
  done
  echo
  echo "## Overall Check Log"
  for item in "${checks[@]}"; do
    echo "- $item"
  done
  echo
  echo "## Result"
  echo "$status"
  echo
  echo "This smoke validates demo bundle integrity only."
  echo
  echo "This smoke does not claim TRL 6 achieved or production readiness."
} > "$smoke_report"

echo "Wrote $smoke_report"

if [[ "$status" != "PASS" ]]; then
  exit 1
fi
