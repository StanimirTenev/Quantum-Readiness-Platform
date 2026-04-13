from pathlib import Path

from app.models import AssetCreate, AssetUpdate, CryptoEvidence, HostInventory, ScanIngestRequest, TLSEvidence, TLSEvidenceCertificate
from app.repository import AssetRepository


def test_repository_crud(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "inventory.db")

    created = repo.create_asset(
        AssetCreate(
            asset_type="server",
            name="vpn-gateway-01",
            owner="security",
            criticality=5,
            environment="prod",
            vendor="example-vendor",
            lifecycle_years=7,
        )
    )

    assert created.id
    assert created.name == "vpn-gateway-01"

    fetched = repo.get_asset(created.id)
    assert fetched is not None
    assert fetched.owner == "security"

    updated = repo.update_asset(created.id, AssetUpdate(owner="platform"))
    assert updated is not None
    assert updated.owner == "platform"

    listing = repo.list_assets()
    assert len(listing) == 1

    deleted = repo.delete_asset(created.id)
    assert deleted is True
    assert repo.get_asset(created.id) is None


def test_scan_and_risk_persistence(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "inventory.db")

    payload = ScanIngestRequest(
        source="network",
        assets=[
            AssetCreate(
                asset_type="endpoint",
                name="google.com:443",
                criticality=3,
                environment="unknown",
                lifecycle_years=3,
            )
        ],
        host_inventory=HostInventory(
            hostname="test-host",
            os="linux",
            kernel="6.x",
            architecture="amd64",
            ips=["127.0.0.1"],
        ),
        crypto_evidence=CryptoEvidence(
            openssl_available=True,
            openssl_version="OpenSSL 3",
            ssh_config_path="/etc/ssh/ssh_config",
            known_crypto_files=["/etc/ssl/openssl.cnf"],
        ),
        tls_evidence=TLSEvidence(
            target="google.com:443",
            tls_version="TLS1.3",
            cipher_suite="TLS_AES_128_GCM_SHA256",
            server_name="google.com",
            certificate=TLSEvidenceCertificate(
                subject="CN=*.google.com",
                issuer="CN=Example Issuer",
                not_before="2026-01-01T00:00:00Z",
                not_after="2026-06-01T00:00:00Z",
                signature_algorithm="ECDSA-SHA256",
                public_key_algorithm="ECDSA",
                dns_names=["google.com"],
            ),
        ),
    )

    scan_id = repo.create_scan(payload)
    created_assets = repo.create_many(payload.assets)

    assert scan_id
    assert len(created_assets) == 1

    repo.create_risk_result(
        scan_id=scan_id,
        asset_name="google.com:443",
        payload={
            "contract_version": "stage1-v1",
            "asset_name": "google.com:443",
            "scenario": "public_timeline",
            "scenario_multiplier": 1.0,
            "base_score": 3.4,
            "final_score": 3.4,
            "normalized_score_100": 68.0,
            "rating": "high",
            "dependency_count": 3,
            "vendor_blocked": False,
            "rationale": {"criticality": 3},
        },
    )

    scans = repo.list_scans()
    assert len(scans) == 1
    assert scans[0].source == "network"

    fetched = repo.get_scan(scan_id)
    assert fetched is not None
    assert fetched.host_inventory is not None
    assert fetched.host_inventory["hostname"] == "test-host"

    risks = repo.list_risk_results(scan_id=scan_id)
    assert len(risks) == 1
    assert risks[0].asset_name == "google.com:443"
    assert risks[0].rating == "high"
    assert risks[0].contract_version == "stage1-v1"


def test_cleanup_duplicate_assets(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "inventory.db")

    payload = AssetCreate(
        asset_type="endpoint",
        name="google.com:443",
        criticality=3,
        environment="unknown",
        lifecycle_years=3,
    )

    first = repo.create_asset(payload)
    second = repo.create_asset(payload)

    assert first.id == second.id

    result = repo.cleanup_duplicate_assets()
    assert "deleted_assets" in result
