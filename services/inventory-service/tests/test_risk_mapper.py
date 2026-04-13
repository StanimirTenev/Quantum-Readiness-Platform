from app.models import AssetCreate, ScanIngestRequest
from app.risk_mapper import build_risk_payload


def test_build_risk_payload_uses_asset_specific_fields_and_contract_metadata() -> None:
    payload = ScanIngestRequest(
        source="manual",
        assets=[
            AssetCreate(asset_type="server", name="core-db", criticality=2),
            AssetCreate(asset_type="endpoint", name="api-gateway", criticality=5, vendor="blocked-vendor"),
        ],
    )

    score_payload = build_risk_payload(payload, asset_name="api-gateway", scenario="vendor_lag")

    assert score_payload["contract_version"] == "stage1-v1"
    assert score_payload["asset_name"] == "api-gateway"
    assert score_payload["criticality"] == 5.0
    assert score_payload["dependency_count"] == 3
    assert score_payload["vendor_blocked"] is True
    assert score_payload["scenario"] == "vendor_lag"
