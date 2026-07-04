import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))
import app.main as main

client = TestClient(main.app)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "services" / "inventory-service" / "tests" / "fixtures" / "stage2_evidence"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "evidence-normalizer"}


def test_normalize_network_fixture_canonicalizes_certificate() -> None:
    response = client.post("/normalize", json=_load("network_enriched_ingest.json"))
    assert response.status_code == 200
    data = response.json()
    net = data["network_evidence"]
    assert net["tls_version"] == "TLS 1.3"  # taken from protocol_version
    cert = net["certificate"]
    assert cert["subject"] == "CN=api.example.internal,O=Example Internal"  # from display_dn
    assert cert["signature_algorithm"] == "RSA-PSS-SHA256"  # from algorithms.signature
    assert cert["public_key_algorithm"] == "RSA"  # from algorithms.public_key
    assert cert["dns_names"] == ["api.example.internal", "app.example.internal"]
    assert net["certificate_chain"]["available"] is True
    assert net["certificate_chain"]["fingerprints"] == [
        "11aa22bb33cc44dd55ee66ff77889900aabbccddeeff00112233445566778899"
    ]


def test_normalize_host_fixture_extracts_packages_and_files() -> None:
    response = client.post("/normalize", json=_load("host_enriched_ingest.json"))
    assert response.status_code == 200
    host = response.json()["host_evidence"]
    assert host["package_manager"] == "dnf"
    assert host["packages"][0] == {"name": "openssl", "version": "3.0.13-1.el9", "package_manager": "dnf"}
    assert host["certificate_files"] == ["/etc/pki/tls/certs/app.example.internal.crt"]
    assert host["config_files"] == ["/etc/nginx/conf.d/app.example.internal-tls.conf"]


def test_flat_certificate_form_produces_same_canonical_shape() -> None:
    payload = {
        "source": "network",
        "assets": [{"asset_type": "endpoint", "name": "h:443"}],
        "tls_metadata": {
            "collected": True,
            "protocol_version": "TLS 1.2",
            "certificate": {
                "subject": "CN=flat.example",
                "signature_algorithm": "sha256WithRSAEncryption",
                "public_key_algorithm": "RSA",
                "public_key_size": 2048,
                "not_after": "2027-01-01T00:00:00Z",
            },
        },
    }
    response = client.post("/normalize", json=payload)
    assert response.status_code == 200
    cert = response.json()["network_evidence"]["certificate"]
    assert cert["subject"] == "CN=flat.example"
    assert cert["signature_algorithm"] == "sha256WithRSAEncryption"
    assert cert["public_key_size"] == 2048
    assert response.json()["network_evidence"]["tls_version"] == "TLS 1.2"


def test_tls_metadata_and_tls_evidence_aliases_both_accepted() -> None:
    base = {"assets": [{"asset_type": "endpoint", "name": "h"}]}
    tls = {"collected": True, "target": "h", "certificate": {"subject": "CN=x"}}
    a = client.post("/normalize", json={**base, "tls_metadata": tls})
    b = client.post("/normalize", json={**base, "tls_evidence": tls})
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["network_evidence"]["target"] == "h"
    assert b.json()["network_evidence"]["target"] == "h"


def test_missing_asset_name_emits_warning() -> None:
    response = client.post(
        "/normalize", json={"source": "manual", "assets": [{"asset_type": "server"}]}
    )
    assert response.status_code == 200
    assert any("missing name" in w for w in response.json()["warnings"])


def test_empty_request_returns_warnings_not_error() -> None:
    response = client.post("/normalize", json={})
    assert response.status_code == 200
    data = response.json()
    assert data["host_evidence"] is None
    assert data["network_evidence"] is None
    assert "no assets provided" in data["warnings"]
    assert "no host or network evidence provided" in data["warnings"]


def test_private_key_indicator_flagged_from_counts() -> None:
    payload = {
        "assets": [{"asset_type": "server", "name": "h"}],
        "crypto_evidence": {
            "cert_indicators": {
                "certificate_file_indicators": {
                    "files": [{"path": "/etc/ssl/private/server.key"}],
                    "counts": {"key": 1},
                }
            }
        },
    }
    response = client.post("/normalize", json=payload)
    assert response.status_code == 200
    host = response.json()["host_evidence"]
    assert host["private_key_indicator"] is True
    assert any("private key indicator" in w for w in response.json()["warnings"])
