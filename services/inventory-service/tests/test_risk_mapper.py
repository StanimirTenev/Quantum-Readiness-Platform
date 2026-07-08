from app.models import AssetCreate, CryptoEvidence, ScanIngestRequest, TLSEvidence
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


def test_build_risk_payload_forwards_tls_evidence_for_weak_key_detection() -> None:
    payload = ScanIngestRequest(
        source="network",
        assets=[AssetCreate(asset_type="endpoint", name="legacy-vpn.internal:443")],
        tls_evidence=TLSEvidence(
            collected=True,
            certificate={"public_key_algorithm": "RSA", "public_key_size": 1024, "not_after": "2027-01-01T00:00:00Z"},
        ),
    )

    score = build_risk_payload(payload, asset_name="legacy-vpn.internal:443")

    assert score["tls_metadata"]["collected"] is True
    assert score["tls_metadata"]["certificate"]["public_key_algorithm"] == "RSA"
    assert score["tls_metadata"]["certificate"]["public_key_size"] == 1024


def test_build_risk_payload_forwards_crypto_evidence_for_host_evidence_signals() -> None:
    payload = ScanIngestRequest(
        source="host",
        assets=[AssetCreate(asset_type="server", name="linux-host-01")],
        crypto_evidence=CryptoEvidence(
            openssl_available=True,
            package_metadata={"packages": [{"name": "openssl"}]},
            cert_indicators={
                "certificate_file_indicators": {"counts": {"certificate": 2, "key": 1}},
                "config_file_indicators": {"counts": {"tls_server_config": 1, "ssh_server_config": 1}},
            },
        ),
    )

    score = build_risk_payload(payload, asset_name="linux-host-01")

    assert score["crypto_evidence"]["package_metadata"]["packages"] == [{"name": "openssl"}]
    assert score["crypto_evidence"]["cert_indicators"]["certificate_file_indicators"]["counts"]["key"] == 1
    assert score["crypto_evidence"]["cert_indicators"]["config_file_indicators"]["counts"]["ssh_server_config"] == 1


def test_build_risk_payload_forwards_stage2_notes_when_present() -> None:
    payload = ScanIngestRequest(
        source="host",
        assets=[AssetCreate(asset_type="server", name="archive-host")],
        stage2_notes="Long-term archive, HNDL exposure noted by operator.",
    )

    score = build_risk_payload(payload, asset_name="archive-host")

    assert score["stage2_notes"] == "Long-term archive, HNDL exposure noted by operator."


def test_build_risk_payload_omits_evidence_keys_when_not_present() -> None:
    payload = ScanIngestRequest(
        source="manual",
        assets=[AssetCreate(asset_type="server", name="bare-asset")],
    )

    score = build_risk_payload(payload, asset_name="bare-asset")

    assert "tls_metadata" not in score
    assert "crypto_evidence" not in score
    assert "stage2_notes" not in score


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
