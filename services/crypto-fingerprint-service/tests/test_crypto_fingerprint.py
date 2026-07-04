from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import app.main as main

client = TestClient(main.app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "crypto-fingerprint-service"}


def test_algorithms_lists_known_families() -> None:
    response = client.get("/algorithms")
    assert response.status_code == 200
    families = {entry["family"] for entry in response.json()["algorithms"]}
    assert {"RSA", "ECDSA", "ECDH", "ML-KEM", "ML-DSA"}.issubset(families)


def test_rsa_public_key_is_classical_vulnerable_and_hndl() -> None:
    response = client.post(
        "/fingerprint",
        json={"asset_name": "a", "algorithms": ["RSA"]},
    )
    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["algorithm_family"] == "RSA"
    assert finding["classification"] == "classical_vulnerable"
    assert finding["quantum_vulnerable"] is True
    assert finding["harvest_now_decrypt_later"] is True


def test_ecdsa_signature_is_vulnerable_but_not_hndl() -> None:
    response = client.post(
        "/fingerprint",
        json={
            "asset_name": "a",
            "tls_metadata": {
                "certificate": {"algorithms": {"signature": "ecdsa-with-SHA384", "public_key": "id-ecPublicKey"}}
            },
        },
    )
    assert response.status_code == 200
    findings = {f["location"]: f for f in response.json()["findings"]}
    signature = findings["tls_metadata.certificate.signature"]
    assert signature["algorithm_family"] == "ECDSA"
    assert signature["quantum_vulnerable"] is True
    # A signature cannot be harvested-now-decrypted-later.
    assert signature["harvest_now_decrypt_later"] is False


def test_pqc_algorithm_is_pqc_ready() -> None:
    response = client.post(
        "/fingerprint",
        json={"asset_name": "a", "algorithms": ["ML-KEM-768", "Kyber1024", "ML-DSA-65"]},
    )
    assert response.status_code == 200
    data = response.json()
    assert all(f["classification"] == "pqc_ready" for f in data["findings"])
    assert all(f["quantum_vulnerable"] is False for f in data["findings"])
    assert data["summary"]["pqc_readiness"] == "pqc_ready"


def test_weak_rsa_key_is_critical() -> None:
    response = client.post(
        "/fingerprint",
        json={
            "asset_name": "a",
            "tls_metadata": {
                "certificate": {"algorithms": {"public_key": "RSA"}, "key": {"size_bits": 1024}}
            },
        },
    )
    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["weak_key"] is True
    assert finding["severity"] == "critical"


def test_weak_signature_hash_is_critical() -> None:
    response = client.post(
        "/fingerprint",
        json={"asset_name": "a", "algorithms": ["sha1WithRSAEncryption"]},
    )
    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["algorithm_family"] == "RSA"
    assert finding["classification"] == "classical_vulnerable"
    assert finding["severity"] == "critical"


def test_symmetric_cipher_is_reduced_not_vulnerable() -> None:
    response = client.post(
        "/fingerprint",
        json={"asset_name": "a", "tls_metadata": {"cipher_suite": "TLS_AES_128_GCM_SHA256"}},
    )
    assert response.status_code == 200
    finding = response.json()["findings"][0]
    assert finding["classification"] == "symmetric_reduced"
    assert finding["quantum_vulnerable"] is False


def test_network_fixture_certificate_flags_rsa_hndl() -> None:
    response = client.post(
        "/fingerprint",
        json={
            "asset_name": "api.example.internal:443",
            "tls_metadata": {
                "cipher_suite": "TLS_AES_128_GCM_SHA256",
                "certificate": {
                    "algorithms": {"signature": "RSA-PSS-SHA256", "public_key": "RSA"}
                },
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["summary"]["pqc_readiness"] == "classical_only"
    assert data["summary"]["hndl_exposure"] is True
    assert data["summary"]["quantum_vulnerable_count"] == 2


def test_mixed_classical_and_pqc_is_hybrid() -> None:
    response = client.post(
        "/fingerprint",
        json={"asset_name": "a", "algorithms": ["RSA", "ML-KEM-768"]},
    )
    assert response.status_code == 200
    assert response.json()["summary"]["pqc_readiness"] == "hybrid_partial"


def test_empty_evidence_returns_unknown_readiness() -> None:
    response = client.post("/fingerprint", json={"asset_name": "a"})
    assert response.status_code == 200
    data = response.json()
    assert data["findings"] == []
    assert data["summary"]["pqc_readiness"] == "unknown"


def test_missing_asset_name_returns_422() -> None:
    response = client.post("/fingerprint", json={"algorithms": ["RSA"]})
    assert response.status_code == 422
