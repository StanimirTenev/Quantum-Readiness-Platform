"""Demo dataset seeding for the web-ui's "Load Demo" button (PR: Product
Demo v2 / UI Demo Scenario). Seeds a small, realistic set of host/network/
repo evidence plus a vendor document directly into the currently-running
stack, via the same /scans/ingest contract real agents use, then builds a
graph snapshot and doc index at the default paths graph-service/
retrieval-service already read from.

Reuses the same host/network Stage2 fixtures as scripts/run_product_demo.sh
and scripts/run_evidence_to_risk_smoke.sh -- one source of truth for what
"the demo dataset" looks like, so the CI-facing demo report and the live
UI demo show consistent data.

This module is the one deliberate exception to the gateway otherwise being
read-only/proxy-only: seeding demo data is explicitly what it's for. It
never touches the deterministic risk/pqc-readiness pipelines directly --
it only POSTs evidence through the normal ingest contract, same as any
other collector.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "services" / "inventory-service" / "tests" / "fixtures" / "stage2_evidence"
HOST_FIXTURE = FIXTURES_DIR / "host_enriched_ingest.json"
NETWORK_FIXTURE = FIXTURES_DIR / "network_enriched_ingest.json"

DEMO_REPO_NAME = "qrp-demo-payments-service"
REPO_SCAN_PAYLOAD: dict[str, Any] = {
    "assets": [{"asset_type": "other", "name": DEMO_REPO_NAME}],
    "crypto_evidence": {
        "known_crypto_files": ["app/legacy_auth.py", ".github/workflows/release.yml"],
        "package_metadata": {"packages": [{"name": "RSA"}, {"name": "SHA1"}]},
        "repo_scan": {
            "source_code_findings": [
                {"path": "app/legacy_auth.py", "line": 4, "algorithm": "RSA"},
                {"path": "app/legacy_auth.py", "line": 9, "algorithm": "SHA1"},
            ],
            "ci_pipeline_findings": [
                {"path": ".github/workflows/release.yml", "line": 12, "command_type": "gpg_sign"},
            ],
            "detected_algorithms": ["RSA", "SHA1"],
        },
    },
}

DEMO_DOC_ID = "vendor-pqc-roadmap.md"
DEMO_DOC_TEXT = (
    "Our appliances will support hybrid post-quantum key exchange (ML-KEM-768) "
    "starting Q3 2026. Certificate rotation procedures are documented in the "
    "operations runbook. Rotate the signing certificate every 90 days."
)
DOC_INDEX_DEFAULT_PATH = REPO_ROOT / "reports" / "doc-index" / "latest" / "doc-index.json"
GRAPH_SNAPSHOT_DEFAULT_PATH = REPO_ROOT / "reports" / "graph" / "latest" / "graph-snapshot.json"

DEMO_ASSET_NAMES = ["qrp-linux-demo-01", "api.example.internal:443", DEMO_REPO_NAME]


def _read_fixture(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_demo_scan_payloads() -> list[tuple[str, str, dict[str, Any]]]:
    """Returns [(source, asset_name, payload), ...] ready to POST to
    /scans/ingest via the gateway's own _ingest_scan helper."""
    host_payload = _read_fixture(HOST_FIXTURE)
    network_payload = _read_fixture(NETWORK_FIXTURE)
    return [
        ("host", "qrp-linux-demo-01", host_payload),
        ("network", "api.example.internal:443", network_payload),
        ("repo", DEMO_REPO_NAME, REPO_SCAN_PAYLOAD),
    ]


def write_demo_doc_index(target_path: Path | None = None) -> Path:
    path = target_path or DOC_INDEX_DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    index = {
        "documents": [{
            "doc_id": DEMO_DOC_ID,
            "source_path": str(path.parent / DEMO_DOC_ID),
            "chunks": [{"chunk_index": 0, "page": None, "text": DEMO_DOC_TEXT}],
        }],
        "document_count": 1,
        "total_chunk_count": 1,
    }
    path.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return path


def build_demo_graph_snapshot(target_path: Path | None = None) -> tuple[bool, str]:
    """Runs the same fixture-based graph projection tool
    scripts/run_product_demo.sh uses. Relative paths + cwd=REPO_ROOT so the
    snapshot doesn't bake in a machine-specific absolute path."""
    path = target_path or GRAPH_SNAPSHOT_DEFAULT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    report_path = path.with_name("demo-load-graph-report.md")
    result = subprocess.run(
        [
            sys.executable, "tools/graph_projection/project_stage2_fixtures.py",
            "--host", str(HOST_FIXTURE.relative_to(REPO_ROOT)),
            "--network", str(NETWORK_FIXTURE.relative_to(REPO_ROOT)),
            "--snapshot-out", str(path.relative_to(REPO_ROOT)),
            "--report-out", str(report_path.relative_to(REPO_ROOT)),
        ],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return False, (result.stderr or result.stdout or "graph projection failed").strip()[-500:]
    return True, "graph snapshot built"
