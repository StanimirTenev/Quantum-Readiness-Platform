from app.models import AssetCreate, CryptoEvidence, ScanIngestRequest
from app.risk_mapper import build_risk_payload


def _host_with_windows_signals(signals: dict, asset_type: str = "endpoint") -> ScanIngestRequest:
    return ScanIngestRequest(
        source="host",
        assets=[AssetCreate(asset_type=asset_type, name="redacted-windows-host")],
        crypto_evidence=CryptoEvidence(openssl_available=False, windows_normalized_signals=signals),
    )


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


def test_windows_signals_do_not_change_a_plain_host_scan() -> None:
    payload = ScanIngestRequest(
        source="host",
        assets=[AssetCreate(asset_type="endpoint", name="plain-host")],
    )
    score = build_risk_payload(payload, asset_name="plain-host")

    # No windows_normalized_signals present -> original generic host scoring.
    assert score["blast_radius"] == 3.0
    assert score["migration_difficulty"] == 3.0
    assert score["dependency_count"] == 3


def test_domain_controller_maximizes_blast_radius_and_raises_dependencies() -> None:
    payload = _host_with_windows_signals(
        {"domain_controller_role_observed": True, "domain_joined": True},
        asset_type="server",
    )
    score = build_risk_payload(payload, asset_name="redacted-windows-host")

    assert score["blast_radius"] == 5.0
    assert score["dependency_count"] == 4  # server base 2 + domain controller 2


def test_domain_joined_widens_blast_radius_and_dependencies() -> None:
    payload = _host_with_windows_signals({"domain_joined": True})
    score = build_risk_payload(payload, asset_name="redacted-windows-host")

    assert score["blast_radius"] == 4.0  # host base 3 widened to 4
    assert score["dependency_count"] == 4  # endpoint base 3 + domain-joined 1


def test_certificate_volume_and_weakness_raise_migration_difficulty() -> None:
    payload = _host_with_windows_signals(
        {
            "certificates_observed_count": 61,
            "weak_signature_indicators_count": 23,
            "expired_certificates_count": 22,
        }
    )
    score = build_risk_payload(payload, asset_name="redacted-windows-host")

    # host base 3 + (>=50 certs) 2 + (weak/expired present) 1 = 6, capped at 5.
    assert score["migration_difficulty"] == 5.0


def test_moderate_certificate_volume_raises_migration_difficulty_by_one() -> None:
    payload = _host_with_windows_signals({"certificates_observed_count": 12})
    score = build_risk_payload(payload, asset_name="redacted-windows-host")

    assert score["migration_difficulty"] == 4.0  # host base 3 + (>=10 certs) 1


def test_windows_factors_stay_within_engine_bounds() -> None:
    payload = _host_with_windows_signals(
        {
            "domain_controller_role_observed": True,
            "domain_joined": True,
            "certificates_observed_count": 500,
            "weak_signature_indicators_count": 99,
            "expired_certificates_count": 99,
        }
    )
    score = build_risk_payload(payload, asset_name="redacted-windows-host")

    for factor in ("blast_radius", "migration_difficulty", "quantum_exposure", "criticality"):
        assert 0.0 <= score[factor] <= 5.0
