"""Repo/CI scanner CLI: detect classical crypto usage and CI signing commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from detectors import scan_repo


def build_ingest_payload(scan_result: dict[str, Any], repo_name: str) -> dict[str, Any]:
    known_files = sorted({
        finding["path"]
        for finding in scan_result["source_code_findings"] + scan_result["ci_pipeline_findings"]
    })
    # Map detected algorithms into the package_metadata.packages shape
    # risk-engine's stage2 evidence extraction already reads (crypto_packages_detected),
    # so a repo scan's findings actually feed into risk rationale on ingest.
    packages = [{"name": algorithm} for algorithm in scan_result["detected_algorithms"]]
    return {
        "source": "repo",
        "assets": [{"asset_type": "other", "name": repo_name}],
        "crypto_evidence": {
            "known_crypto_files": known_files,
            "package_metadata": {"packages": packages},
            "repo_scan": scan_result,
        },
    }


def post_ingest(inventory_url: str, payload: dict[str, Any], workspace_id: str | None = None) -> dict[str, Any]:
    """workspace_id is optional (the workspace model's hybrid creation mode
    -- see services/inventory-service/README.md): pass one to group this
    scan under an existing workspace, or omit it and inventory-service
    auto-creates a single-scan workspace for it."""
    import httpx

    endpoint = f"{inventory_url.rstrip('/')}/scans/ingest"
    params = {"workspace_id": workspace_id} if workspace_id else None
    response = httpx.post(endpoint, json=payload, params=params, timeout=10.0)
    response.raise_for_status()
    return response.json()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scan a repository for classical crypto usage and CI signing commands."
    )
    parser.add_argument("--repo-path", required=True, help="Path to the repository to scan.")
    parser.add_argument("--out", help="Write JSON payload to this file instead of stdout.")
    parser.add_argument("--ingest", help="inventory-service base URL, e.g. http://127.0.0.1:8001")
    parser.add_argument("--workspace-id", help="Group this scan under an existing workspace (POST /workspaces); omit to auto-create one")
    args = parser.parse_args(argv)

    repo_path = Path(args.repo_path).resolve()
    if not repo_path.is_dir():
        print(f"error: repo path not found: {repo_path}", file=sys.stderr)
        return 1

    scan_result = scan_repo(repo_path)
    payload = build_ingest_payload(scan_result, repo_path.name)
    output_text = json.dumps(payload, indent=2)

    if args.out:
        Path(args.out).write_text(output_text + "\n", encoding="utf-8")
    else:
        print(output_text)

    if args.ingest:
        response = post_ingest(args.ingest, payload, workspace_id=args.workspace_id)
        print(json.dumps(response, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
