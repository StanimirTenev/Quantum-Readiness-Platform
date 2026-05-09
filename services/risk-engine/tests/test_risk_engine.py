from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import (
    app,
    calculate_base_score,
    calculate_stage2_adjustment,
    extract_stage2_signals,
)

client = TestClient(app)


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
