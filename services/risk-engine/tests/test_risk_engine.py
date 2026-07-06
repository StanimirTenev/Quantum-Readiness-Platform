from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import (
    app,
    calculate_base_score,
    calculate_stage2_adjustment,
    extract_stage2_signals,
    extract_windows_signals,
)

client = TestClient(app)


def _windows_signals(**overrides) -> dict:
    signals = {
        "platform": "windows",
        "asset_type": "server",
        "certificates_observed_count": 0,
        "expired_certificates_count": 0,
        "weak_signature_indicators_count": 0,
        "crypto_relevant_services_count": 0,
        "domain_joined": False,
        "domain_controller_role_observed": False,
    }
    signals.update(overrides)
    return signals


def _base_payload() -> dict:
    return {
        "contract_version": "stage1-v1",
        "asset_name": "vpn-gateway-01",
        "criticality": 5,
        "confidentiality_lifetime": 5,
        "quantum_exposure": 5,
        "blast_radius": 5,
        "vendor_lock_in": 4,
        "migration_difficulty": 3,
        "scenario": "hidden_capability",
    }


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "risk-engine"}


def test_scenarios() -> None:
    response = client.get("/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert "public_timeline" in data


def test_calculate_base_score() -> None:
    class Obj:
        criticality = 5
        confidentiality_lifetime = 5
        quantum_exposure = 5
        blast_radius = 5
        vendor_lock_in = 5
        migration_difficulty = 5

    score = calculate_base_score(Obj())
    assert score == 5.0


def test_score_endpoint_backward_compatible_without_enriched_evidence() -> None:
    payload = {
        "contract_version": "stage1-v1",
        "asset_name": "legacy-edge",
        "criticality": 3,
        "confidentiality_lifetime": 3,
        "quantum_exposure": 3,
        "blast_radius": 3,
        "vendor_lock_in": 3,
        "migration_difficulty": 3,
        "scenario": "public_timeline",
    }
    response = client.post("/score", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["stage2_adjustment"] == 0.0
    assert "confidence_score" in data
    assert "risk_dimensions" in data


def test_evidence_signal_crypto_packages_detected() -> None:
    payload = _base_payload()
    payload["crypto_evidence"] = {"package_metadata": {"packages": ["openssl"]}}

    data = client.post("/score", json=payload).json()
    assert data["stage2_signals"]["evidence_signals"]["crypto_packages_detected"] is True


def test_evidence_signal_private_key_files_detected() -> None:
    payload = _base_payload()
    payload["crypto_evidence"] = {
        "cert_indicators": {
            "certificate_file_indicators": {"counts": {"key": 1}},
        }
    }

    data = client.post("/score", json=payload).json()
    assert data["stage2_signals"]["evidence_signals"]["private_key_files_detected"] is True


def test_evidence_signal_tls_config_detected() -> None:
    payload = _base_payload()
    payload["crypto_evidence"] = {
        "cert_indicators": {
            "config_file_indicators": {"counts": {"tls_server_config": 1}},
        }
    }

    data = client.post("/score", json=payload).json()
    assert data["stage2_signals"]["evidence_signals"]["tls_config_detected"] is True


def test_evidence_signal_tls_detected() -> None:
    payload = _base_payload()
    payload["tls_metadata"] = {"collected": True}

    data = client.post("/score", json=payload).json()
    assert data["stage2_signals"]["evidence_signals"]["tls_detected"] is True


def test_evidence_signal_weak_public_key_detected_for_rsa_1024() -> None:
    payload = _base_payload()
    payload["tls_metadata"] = {
        "certificate": {
            "public_key_algorithm": "RSA",
            "public_key_size": 1024,
        }
    }

    data = client.post("/score", json=payload).json()
    assert data["stage2_signals"]["evidence_signals"]["weak_public_key_detected"] is True


def test_evidence_signal_expiring_certificate_detected_within_90_days() -> None:
    payload = _base_payload()
    payload["tls_metadata"] = {
        "certificate": {
            "not_after": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        }
    }

    data = client.post("/score", json=payload).json()
    assert data["stage2_signals"]["evidence_signals"]["expiring_certificate_detected"] is True


def test_evidence_signal_certificate_chain_available() -> None:
    payload = _base_payload()
    payload["tls_metadata"] = {
        "certificate_chain": {
            "available": True,
            "length": 2,
        }
    }

    data = client.post("/score", json=payload).json()
    assert data["stage2_signals"]["evidence_signals"]["certificate_chain_available"] is True


def test_invalid_certificate_date_does_not_fail() -> None:
    payload = _base_payload()
    payload["tls_metadata"] = {
        "certificate": {
            "not_after": "invalid-date",
        }
    }

    response = client.post("/score", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["stage2_signals"]["evidence_signals"]["expiring_certificate_detected"] is False


def test_score_capped_at_100_with_stage2_evidence_adjustments() -> None:
    payload = _base_payload()
    payload["scenario"] = "hndl_active_now"
    payload["crypto_evidence"] = {
        "package_metadata": {"packages": ["openssl"]},
        "cert_indicators": {
            "certificate_file_indicators": {"counts": {"certificate": 1, "key": 1}},
            "config_file_indicators": {"counts": {"tls_server_config": 1, "ssh_server_config": 1}},
        },
    }
    payload["tls_metadata"] = {
        "collected": True,
        "certificate": {
            "public_key_algorithm": "RSA",
            "public_key_size": 1024,
            "not_after": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        },
        "certificate_chain": {"available": True, "length": 2},
    }

    data = client.post("/score", json=payload).json()
    assert data["normalized_score_100"] == 100.0


def test_extract_windows_signals_applies_thresholds() -> None:
    from app.main import RiskInput

    signals = extract_windows_signals(
        RiskInput(
            asset_name="win",
            criticality=3,
            confidentiality_lifetime=3,
            quantum_exposure=3,
            blast_radius=3,
            vendor_lock_in=1,
            migration_difficulty=3,
            windows_signals=_windows_signals(
                certificates_observed_count=50,
                expired_certificates_count=1,
                weak_signature_indicators_count=0,
                crypto_relevant_services_count=2,
                domain_controller_role_observed=True,
            ),
        )
    )
    assert signals["windows_large_certificate_estate"] is True  # 50 hits threshold
    assert signals["windows_expired_certificates"] is True
    assert signals["windows_weak_signature_certificates"] is False
    assert signals["windows_domain_controller"] is True
    assert signals["windows_crypto_services_present"] is True


def test_windows_signals_add_dedicated_stage2_adjustment() -> None:
    payload = _base_payload()
    payload["windows_signals"] = _windows_signals(
        certificates_observed_count=80,       # >= 50 -> +3
        expired_certificates_count=5,         # -> +8
        weak_signature_indicators_count=3,    # -> +6
        crypto_relevant_services_count=10,    # -> +2
        domain_controller_role_observed=True, # -> +5
    )
    data = client.post("/score", json=payload).json()
    # No other stage2 evidence in the base payload, so the whole adjustment is
    # the Windows contribution: 8 + 6 + 5 + 3 + 2 = 24.
    assert data["stage2_adjustment"] == 24.0
    assert data["rationale"]["windows_domain_controller"] is True
    assert data["rationale"]["windows_expired_certificates"] is True


def test_windows_signals_absent_means_no_windows_adjustment() -> None:
    data = client.post("/score", json=_base_payload()).json()
    assert data["stage2_adjustment"] == 0.0
    assert data["rationale"]["windows_evidence_present"] is False
    assert data["rationale"]["windows_domain_controller"] is False


def test_windows_domain_controller_raises_dimensions() -> None:
    payload = _base_payload()
    payload["quantum_exposure"] = 2
    payload["criticality"] = 2
    payload["windows_signals"] = _windows_signals(
        certificates_observed_count=80,
        expired_certificates_count=2,
        weak_signature_indicators_count=1,
        domain_controller_role_observed=True,
    )
    dims = client.post("/score", json=payload).json()["risk_dimensions"]
    assert dims["exposure"] == 50.0            # (2/5*100) + 10 domain controller
    assert dims["impact"] == 50.0              # (2/5*100) + 10 domain controller
    assert dims["urgency"] == 65.0             # 40 expired + 25 weak signature
    assert dims["migration_complexity"] == 25.0  # 15 large estate + 10 domain controller


def test_windows_evidence_presence_raises_confidence() -> None:
    without = client.post("/score", json=_base_payload()).json()["confidence_score"]
    payload = _base_payload()
    payload["windows_signals"] = _windows_signals()  # present but all-clean
    with_windows = client.post("/score", json=payload).json()["confidence_score"]
    assert with_windows == without + 10.0


def test_calculate_stage2_adjustment_never_returns_negative_value() -> None:
    signals = {
        "stage2_notes_signals": {"has_hndl_signal": False, "has_pqc_plan_signal": True},
        "evidence_signals": {},
        "high_dependency_pressure": False,
        "vendor_blocked": False,
        "dependency_count": 0,
    }

    assert calculate_stage2_adjustment(signals) == 0.0


def test_extract_stage2_signals_returns_notes_and_evidence_blocks() -> None:
    payload = _base_payload()
    payload["stage2_notes"] = "HNDL concern; migration plan in progress"
    payload["crypto_evidence"] = {"package_metadata": {"packages": ["openssl"]}}

    response = client.post("/score", json=payload)
    assert response.status_code == 200
    signals = response.json()["stage2_signals"]
    assert signals["stage2_notes_signals"]["has_hndl_signal"] is True
    assert signals["stage2_notes_signals"]["has_pqc_plan_signal"] is True
    assert signals["evidence_signals"]["crypto_packages_detected"] is True


def test_confidence_score_increases_with_enriched_evidence() -> None:
    minimal = _base_payload()
    enriched = _base_payload()
    enriched["environment"] = "production"
    enriched["stage2_notes"] = "hndl noted"
    enriched["crypto_evidence"] = {"package_metadata": {"packages": ["openssl"]}}
    enriched["tls_metadata"] = {"collected": True, "certificate_chain": {"available": True, "length": 2}}

    minimal_data = client.post("/score", json=minimal).json()
    enriched_data = client.post("/score", json=enriched).json()

    assert enriched_data["confidence_score"] > minimal_data["confidence_score"]


def test_risk_dimensions_exposure_increases_with_tls_signals() -> None:
    base_payload = _base_payload()
    base_payload["quantum_exposure"] = 2
    tls_payload = _base_payload()
    tls_payload["quantum_exposure"] = 2
    tls_payload["tls_metadata"] = {"collected": True}
    tls_payload["crypto_evidence"] = {
        "cert_indicators": {"config_file_indicators": {"counts": {"tls_server_config": 1}}}
    }

    base_data = client.post("/score", json=base_payload).json()
    tls_data = client.post("/score", json=tls_payload).json()
    assert tls_data["risk_dimensions"]["exposure"] > base_data["risk_dimensions"]["exposure"]


def test_risk_dimensions_impact_reflects_criticality_and_production() -> None:
    payload = _base_payload()
    payload["criticality"] = 5
    payload["environment"] = "production"
    data = client.post("/score", json=payload).json()
    assert data["risk_dimensions"]["impact"] == 100.0


def test_risk_dimensions_urgency_increases_for_expiring_or_weak_key() -> None:
    payload = _base_payload()
    payload["tls_metadata"] = {
        "certificate": {
            "public_key_algorithm": "RSA",
            "public_key_size": 1024,
            "not_after": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
        }
    }
    data = client.post("/score", json=payload).json()
    assert data["risk_dimensions"]["urgency"] >= 75.0


def test_risk_dimensions_migration_complexity_increases_for_dependencies_and_blockers() -> None:
    payload = _base_payload()
    payload["dependency_count"] = 30
    payload["vendor_blocked"] = True
    payload["crypto_evidence"] = {
        "cert_indicators": {"certificate_file_indicators": {"counts": {"certificate": 2, "key": 2}}}
    }
    data = client.post("/score", json=payload).json()
    assert data["risk_dimensions"]["migration_complexity"] == 100.0


def test_risk_dimensions_are_capped_at_100() -> None:
    payload = _base_payload()
    payload["criticality"] = 5
    payload["dependency_count"] = 999
    payload["vendor_blocked"] = True
    payload["environment"] = "production"
    payload["crypto_evidence"] = {
        "cert_indicators": {
            "certificate_file_indicators": {"counts": {"certificate": 1, "key": 1}},
            "config_file_indicators": {"counts": {"tls_server_config": 1, "ssh_server_config": 1}},
        }
    }
    payload["tls_metadata"] = {"collected": True}
    data = client.post("/score", json=payload).json()

    assert data["confidence_score"] <= 100
    for value in data["risk_dimensions"].values():
        assert value <= 100
