#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Ensure safety scan artifacts are freshly generated before indexing so
# hash/size metadata in the bundle index reflects final on-disk content.
python3 tools/evidence_pack/scan_operational_evidence_safety.py --repo-root .

python3 tools/evidence_pack/build_trl7_operational_evidence_bundle.py --repo-root .

echo "Generated: reports/trl7/operational-evidence/trl7-operational-evidence-bundle-index.json"
echo "Generated: reports/trl7/operational-evidence/trl7-operational-evidence-bundle-index.md"
