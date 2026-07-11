from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import app.main as main

client = TestClient(main.app)


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "finding-attribution-service"}


def test_contract_describes_the_chain() -> None:
    response = client.get("/contract")
    assert response.status_code == 200
    assert response.json()["chain"] == [
        "vulnerability", "location", "service/application", "asset", "certificate/library/pipeline"
    ]


def test_tls_certificate_finding_attributes_endpoint_and_certificate() -> None:
    payload = {
        "asset_name": "payments-api",
        "application": "payments",
        "findings": [
            {
                "source": "tls_certificate",
                "location": "tls_metadata.certificate.public_key",
                "algorithm_family": "RSA",
                "classification": "classical_vulnerable",
                "severity": "high",
                "quantum_vulnerable": True,
                "harvest_now_decrypt_later": True,
                "reason": "RSA is broken by Shor.",
                "raw_value": "RSA",
            }
        ],
        "network_evidence": {
            "target": "api.example.internal",
            "port": 443,
            "certificate": {"subject": "CN=api.example.internal", "fingerprint_sha256": "abc123"},
        },
    }
    response = client.post("/attribute", json=payload)
    assert response.status_code == 200
    finding = response.json()["attributed_findings"][0]
    assert finding["location"]["kind"] == "network_endpoint"
    assert finding["location"]["value"] == "api.example.internal:443"
    assert finding["attribution"]["service"] == "api.example.internal:443"
    assert finding["attribution"]["application"] == "payments"
    assert finding["attribution"]["crypto_object"]["kind"] == "certificate"
    assert finding["attribution"]["crypto_object"]["id"] == "certificate:abc123"
    # explicit chain: vulnerability -> location -> service -> asset -> certificate
    assert finding["chain"] == [
        "RSA (classical_vulnerable)",
        "api.example.internal:443",
        "api.example.internal:443",
        "asset:payments-api",
        "certificate:CN=api.example.internal",
    ]


def test_host_package_finding_attributes_library() -> None:
    payload = {
        "asset_name": "host-01",
        "findings": [
            {"source": "host_package", "location": "crypto_evidence.package_metadata.packages[0]",
             "algorithm_family": "openssl", "classification": "unknown", "raw_value": "openssl"}
        ],
    }
    response = client.post("/attribute", json=payload)
    assert response.status_code == 200
    finding = response.json()["attributed_findings"][0]
    assert finding["location"]["kind"] == "package"
    assert finding["attribution"]["crypto_object"]["kind"] == "library"
    assert finding["attribution"]["crypto_object"]["id"] == "package:openssl"


def test_cipher_suite_finding_is_service_scoped() -> None:
    payload = {
        "asset_name": "svc",
        "findings": [{"source": "tls_cipher_suite", "location": "tls_metadata.cipher_suite",
                      "algorithm_family": "AES", "classification": "symmetric_reduced", "raw_value": "TLS_AES_128_GCM_SHA256"}],
        "tls_metadata": {"target": "h", "port": 8443},
    }
    response = client.post("/attribute", json=payload)
    assert response.status_code == 200
    finding = response.json()["attributed_findings"][0]
    assert finding["location"]["value"] == "h:8443"
    assert finding["attribution"]["crypto_object"]["kind"] == "cipher_suite"


def test_explicit_algorithm_is_manual_and_unattributed() -> None:
    payload = {"asset_name": "a", "findings": [
        {"source": "explicit_algorithm", "location": "algorithms[0]", "algorithm_family": "RSA",
         "classification": "classical_vulnerable", "raw_value": "RSA"}]}
    response = client.post("/attribute", json=payload)
    assert response.status_code == 200
    finding = response.json()["attributed_findings"][0]
    assert finding["location"]["kind"] == "manual"
    assert finding["attribution"]["service"] is None
    assert finding["attribution"]["crypto_object"] is None
    assert response.json()["summary"]["unattributed"] == 1


def test_summary_counts_by_location_kind() -> None:
    payload = {
        "asset_name": "a",
        "findings": [
            {"source": "tls_certificate", "algorithm_family": "RSA", "classification": "classical_vulnerable", "raw_value": "RSA"},
            {"source": "host_package", "algorithm_family": "openssl", "classification": "unknown", "raw_value": "openssl"},
            {"source": "explicit_algorithm", "algorithm_family": "ECDSA", "classification": "classical_vulnerable", "raw_value": "ECDSA"},
        ],
        "network_evidence": {"target": "h", "port": 443, "certificate": {"fingerprint_sha256": "ff"}},
    }
    response = client.post("/attribute", json=payload)
    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["total"] == 3
    assert summary["network_endpoint"] == 1
    assert summary["package"] == 1


def test_finding_id_is_deterministic() -> None:
    payload = {"asset_name": "a", "findings": [
        {"source": "explicit_algorithm", "algorithm_family": "RSA", "classification": "classical_vulnerable", "raw_value": "RSA"}]}
    a = client.post("/attribute", json=payload).json()["attributed_findings"][0]["finding_id"]
    b = client.post("/attribute", json=payload).json()["attributed_findings"][0]["finding_id"]
    assert a == b and a.startswith("finding:")


def test_missing_asset_name_returns_422() -> None:
    response = client.post("/attribute", json={"findings": []})
    assert response.status_code == 422


def test_repo_ci_pipeline_finding_attributes_pipeline() -> None:
    payload = {
        "asset_name": "repo-a",
        "findings": [
            {"source": "repo_ci_pipeline", "location": ".github/workflows/release.yml:12",
             "algorithm_family": "signing_command", "classification": "unknown", "raw_value": "gpg_sign"}
        ],
    }
    response = client.post("/attribute", json=payload)
    assert response.status_code == 200
    finding = response.json()["attributed_findings"][0]
    assert finding["location"]["kind"] == "config_file"
    assert finding["location"]["value"] == ".github/workflows/release.yml:12"
    assert finding["attribution"]["crypto_object"]["kind"] == "pipeline"
    assert finding["attribution"]["crypto_object"]["label"] == "gpg_sign"


def test_repo_embedded_key_finding_attributes_config() -> None:
    payload = {
        "asset_name": "repo-a",
        "findings": [
            {"source": "repo_embedded_key", "location": "k8s/tls-secret.yaml:6",
             "algorithm_family": "private_key", "classification": "unknown",
             "raw_value": "Embedded private key material"}
        ],
    }
    response = client.post("/attribute", json=payload)
    assert response.status_code == 200
    finding = response.json()["attributed_findings"][0]
    assert finding["location"]["kind"] == "config_file"
    assert finding["location"]["value"] == "k8s/tls-secret.yaml:6"
    assert finding["attribution"]["crypto_object"]["kind"] == "config"
