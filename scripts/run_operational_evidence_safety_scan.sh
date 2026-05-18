#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python3 tools/evidence_pack/scan_operational_evidence_safety.py --repo-root .

echo "Generated: reports/trl7/operational-evidence-safety-scan-report.json"
echo "Generated: reports/trl7/operational-evidence-safety-scan-report.md"
