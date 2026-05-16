#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

python tools/evidence_pack/build_trl6_demo_bundle.py --repo-root "$repo_root"
