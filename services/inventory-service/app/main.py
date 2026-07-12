import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, status

from .clients.risk_engine import RiskEngineClient
from .models import (
    Asset,
    AssetCreate,
    AssetRiskHistory,
    AssetRiskHistoryPoint,
    AssetUpdate,
    ReportCreate,
    ReportRecord,
    RiskRecord,
    ScanIngestRequest,
    ScanIngestResponse,
    ScanRecord,
    ScanWithRisk,
    Workspace,
    WorkspaceBundle,
    WorkspaceCreate,
)
from .repository import AssetRepository
from .risk_mapper import build_risk_payload
from .windows_evidence import build_ingest_request

# tools/report is a repo-level utility (also imported this way by
# api-gateway's demo_seed.py) -- reused here so a workspace's report is
# built from the same deterministic logic as the file-based demo reports.
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
from tools.report.build_operator_report import build_report  # noqa: E402

app = FastAPI(title="Inventory Service", version="0.4.0")
repository = AssetRepository()
risk_client = RiskEngineClient()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "inventory-service"}


@app.get("/assets", response_model=list[Asset])
def list_assets(workspace_id: str | None = Query(default=None)) -> list[Asset]:
    return repository.list_assets(workspace_id=workspace_id)


@app.get("/assets/{asset_id}", response_model=Asset)
def get_asset(asset_id: str) -> Asset:
    asset = repository.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@app.get("/assets/{asset_id}/history", response_model=AssetRiskHistory)
def get_asset_history(asset_id: str) -> AssetRiskHistory:
    asset = repository.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

    rows = repository.list_asset_risk_history(asset.name)
    points = [AssetRiskHistoryPoint(**row) for row in rows]

    first_score = points[0].normalized_score_100 if points else None
    latest_score = points[-1].normalized_score_100 if points else None
    trend = _risk_trend(first_score, latest_score, len(points))

    return AssetRiskHistory(
        asset_id=asset.id,
        asset_name=asset.name,
        points=points,
        first_score=first_score,
        latest_score=latest_score,
        trend=trend,
    )


def _risk_trend(first_score: float | None, latest_score: float | None, count: int) -> str:
    # Lower normalized score means lower risk (better posture).
    if count < 2 or first_score is None or latest_score is None:
        return "insufficient_data"
    if latest_score < first_score:
        return "improving"
    if latest_score > first_score:
        return "worsening"
    return "flat"


@app.post("/assets", response_model=Asset, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, workspace_id: str | None = Query(default=None)) -> Asset:
    """Mirrors /scans/host's hybrid workspace model: pass an existing
    workspace_id to group this asset under it, or omit it and a new
    single-asset workspace is auto-created -- every asset always ends up in
    some workspace."""
    if workspace_id is not None and repository.get_workspace(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return repository.create_asset(payload, workspace_id=workspace_id)


@app.put("/assets/{asset_id}", response_model=Asset)
def update_asset(asset_id: str, payload: AssetUpdate) -> Asset:
    asset = repository.update_asset(asset_id, payload)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@app.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(asset_id: str) -> None:
    deleted = repository.delete_asset(asset_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")


def _persist_scan(
    payload: ScanIngestRequest,
    auto_score: bool,
    scenario: str,
    workspace_id: str | None = None,
) -> ScanIngestResponse:
    """workspace_id is the hybrid workspace model's entry point (see
    Workspace/POST /workspaces): pass an existing workspace_id to group this
    scan under it, or omit it and a new single-scan workspace is
    auto-created -- every scan always ends up in some workspace."""
    if workspace_id is not None and repository.get_workspace(workspace_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    scan_id, resolved_workspace_id = repository.create_scan(payload, workspace_id=workspace_id)
    created = repository.create_many(payload.assets, workspace_id=resolved_workspace_id)

    if auto_score:
        for asset in created:
            risk_payload = build_risk_payload(payload, asset.name, scenario=scenario)
            risk_result = risk_client.score(risk_payload)
            repository.create_risk_result(scan_id=scan_id, asset_name=asset.name, payload=risk_result)

    return ScanIngestResponse(
        source=payload.source,
        created=len(created),
        asset_ids=[asset.id for asset in created],
        scan_id=scan_id,
        workspace_id=resolved_workspace_id,
    )


@app.post("/scans/ingest", response_model=ScanIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_scan(
    payload: ScanIngestRequest,
    auto_score: bool = Query(default=True),
    scenario: str = Query(default="public_timeline"),
    workspace_id: str | None = Query(default=None),
) -> ScanIngestResponse:
    return _persist_scan(payload, auto_score=auto_score, scenario=scenario, workspace_id=workspace_id)


@app.post(
    "/scans/ingest/windows",
    response_model=ScanIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_windows_evidence(
    document: dict[str, Any] = Body(...),
    auto_score: bool = Query(default=True),
    scenario: str = Query(default="public_timeline"),
    workspace_id: str | None = Query(default=None),
) -> ScanIngestResponse:
    """Persist a Windows host evidence document (from the windows-host-agent).

    The raw aggregate/redacted evidence document is mapped to the standard
    ingest contract, then persisted and risk-scored through the same path as
    `/scans/ingest`, so a host collection becomes durable inventory.
    """
    try:
        payload = build_ingest_request(document)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"invalid windows evidence document: {exc}",
        ) from exc
    return _persist_scan(payload, auto_score=auto_score, scenario=scenario, workspace_id=workspace_id)


@app.get("/scans", response_model=list[ScanRecord])
def list_scans() -> list[ScanRecord]:
    return repository.list_scans()


@app.get("/scans/{scan_id}", response_model=ScanWithRisk)
def get_scan(scan_id: str) -> ScanWithRisk:
    scan = repository.get_scan(scan_id)
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")
    risks = repository.list_risk_results(scan_id=scan_id)
    return ScanWithRisk(scan=scan, risks=risks)


@app.get("/risks", response_model=list[RiskRecord])
def list_risks(scan_id: str | None = None, workspace_id: str | None = None) -> list[RiskRecord]:
    return repository.list_risk_results(scan_id=scan_id, workspace_id=workspace_id)


@app.post("/admin/cleanup-assets")
def cleanup_assets() -> dict[str, int]:
    return repository.cleanup_duplicate_assets()


# --- Workspace model (PR: Project/Workspace Model) ---
# Lightweight grouping, not multi-tenancy: a workspace ties together "this is
# scan run X" (its scans), "these are findings from it" (their risk
# records), and "this is a report tied to it" (persisted reports). Hybrid
# creation: POST /workspaces first for explicit grouping across multiple
# scans, or omit workspace_id on /scans/ingest and one is auto-created.

@app.post("/workspaces", response_model=Workspace, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate) -> Workspace:
    return repository.create_workspace(source=payload.source)


@app.get("/workspaces", response_model=list[Workspace])
def list_workspaces() -> list[Workspace]:
    return repository.list_workspaces()


@app.get("/workspaces/{workspace_id}", response_model=WorkspaceBundle)
def get_workspace(workspace_id: str) -> WorkspaceBundle:
    workspace = repository.get_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    scans = repository.list_scans_by_workspace(workspace_id)
    risks = [risk for scan in scans for risk in repository.list_risk_results(scan_id=scan.id)]
    reports = repository.list_reports(workspace_id=workspace_id)
    return WorkspaceBundle(workspace=workspace, scans=scans, risks=risks, reports=reports)


@app.post("/workspaces/{workspace_id}/reports", response_model=ReportRecord, status_code=status.HTTP_201_CREATED)
def create_workspace_report(workspace_id: str, payload: ReportCreate = ReportCreate()) -> ReportRecord:
    """Builds an operator report (tools/report/build_operator_report) from
    this workspace's own scans/risks -- one highest-scoring risk record per
    asset_name, matching the persisted_risk bundle shape -- and persists it
    so it's fetchable later via GET /reports/{report_id}."""
    workspace = repository.get_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")

    scans = repository.list_scans_by_workspace(workspace_id)
    best_risk_by_asset: dict[str, tuple[RiskRecord, str]] = {}
    for scan in scans:
        for risk in repository.list_risk_results(scan_id=scan.id):
            current = best_risk_by_asset.get(risk.asset_name)
            if current is None or risk.normalized_score_100 > current[0].normalized_score_100:
                best_risk_by_asset[risk.asset_name] = (risk, scan.source)

    bundle = {
        "generated_at": datetime.now(UTC).isoformat(),
        "environment": f"workspace {workspace_id}",
        "assets": [
            {
                "asset_name": asset_name,
                "application": source,
                "persisted_risk": {
                    "rating": risk.rating,
                    "normalized_score_100": risk.normalized_score_100,
                    "rationale": risk.rationale,
                },
            }
            for asset_name, (risk, source) in best_risk_by_asset.items()
        ],
    }
    content = build_report(bundle)
    return repository.create_report(workspace_id, report_type=payload.report_type, content=content)


@app.get("/reports/{report_id}", response_model=ReportRecord)
def get_report(report_id: str) -> ReportRecord:
    report = repository.get_report(report_id)
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@app.get("/reports", response_model=list[ReportRecord])
def list_reports(workspace_id: str | None = None) -> list[ReportRecord]:
    return repository.list_reports(workspace_id=workspace_id)
