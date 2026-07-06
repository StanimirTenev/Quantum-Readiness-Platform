from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, status

from .clients.risk_engine import RiskEngineClient
from .models import (
    Asset,
    AssetCreate,
    AssetUpdate,
    RiskRecord,
    ScanIngestRequest,
    ScanIngestResponse,
    ScanRecord,
    ScanWithRisk,
)
from .repository import AssetRepository
from .risk_mapper import build_risk_payload
from .windows_evidence import build_ingest_request

app = FastAPI(title="Inventory Service", version="0.4.0")
repository = AssetRepository()
risk_client = RiskEngineClient()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "inventory-service"}


@app.get("/assets", response_model=list[Asset])
def list_assets() -> list[Asset]:
    return repository.list_assets()


@app.get("/assets/{asset_id}", response_model=Asset)
def get_asset(asset_id: str) -> Asset:
    asset = repository.get_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
    return asset


@app.post("/assets", response_model=Asset, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate) -> Asset:
    return repository.create_asset(payload)


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
) -> ScanIngestResponse:
    scan_id = repository.create_scan(payload)
    created = repository.create_many(payload.assets)

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
    )


@app.post("/scans/ingest", response_model=ScanIngestResponse, status_code=status.HTTP_201_CREATED)
def ingest_scan(
    payload: ScanIngestRequest,
    auto_score: bool = Query(default=True),
    scenario: str = Query(default="public_timeline"),
) -> ScanIngestResponse:
    return _persist_scan(payload, auto_score=auto_score, scenario=scenario)


@app.post(
    "/scans/ingest/windows",
    response_model=ScanIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_windows_evidence(
    document: dict[str, Any] = Body(...),
    auto_score: bool = Query(default=True),
    scenario: str = Query(default="public_timeline"),
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
    return _persist_scan(payload, auto_score=auto_score, scenario=scenario)


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
def list_risks(scan_id: str | None = None) -> list[RiskRecord]:
    return repository.list_risk_results(scan_id=scan_id)


@app.post("/admin/cleanup-assets")
def cleanup_assets() -> dict[str, int]:
    return repository.cleanup_duplicate_assets()
