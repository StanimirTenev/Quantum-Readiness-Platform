#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
python tools/evidence_pack/validate_trl7_evidence_bundle_consistency.py --repo-root "$REPO_ROOT"
