import importlib
from pathlib import Path

from app.models import AssetCreate, AssetUpdate, CryptoEvidence, HostInventory, ScanIngestRequest, TLSEvidence, TLSEvidenceCertificate
from app.repository import AssetRepository


def test_default_db_path_honors_inventory_db_path_env(tmp_path: Path, monkeypatch) -> None:
    custom = tmp_path / "env-inventory.db"
    monkeypatch.setenv("INVENTORY_DB_PATH", str(custom))

    import app.repository as repository_module

    reloaded = importlib.reload(repository_module)
    try:
        assert reloaded.DEFAULT_DB_PATH == str(custom)
        repo = reloaded.AssetRepository()
        repo.create_asset(AssetCreate(asset_type="server", name="env-db-host"))
        assert custom.exists()
    finally:
        # Restore the module to its unpatched default for the rest of the suite.
        monkeypatch.delenv("INVENTORY_DB_PATH", raising=False)
        importlib.reload(repository_module)


def test_default_db_path_prefers_database_url_over_inventory_db_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("INVENTORY_DB_PATH", str(tmp_path / "sqlite-should-be-ignored.db"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/inventory")

    import app.repository as repository_module

    reloaded = importlib.reload(repository_module)
    try:
        assert reloaded.DEFAULT_DB_PATH == "postgresql://user:pass@localhost:5432/inventory"
    finally:
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("INVENTORY_DB_PATH", raising=False)
        importlib.reload(repository_module)


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


def test_create_asset_defaults_environment_and_auto_creates_workspace(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "inventory.db")

    created = repo.create_asset(AssetCreate(asset_type="server", name="no-env-host"))

    assert created.environment == "unknown"
    assert created.workspace_id is not None
    assert repo.get_workspace(created.workspace_id) is not None


def test_update_asset_cannot_null_out_environment(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "inventory.db")
    created = repo.create_asset(AssetCreate(asset_type="server", name="env-host", environment="production"))

    updated = repo.update_asset(created.id, AssetUpdate(environment=None))

    assert updated is not None
    assert updated.environment == "production"


def test_create_many_shares_one_auto_created_workspace(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "inventory.db")

    created = repo.create_many([
        AssetCreate(asset_type="server", name="batch-host-1"),
        AssetCreate(asset_type="server", name="batch-host-2"),
    ])

    assert len(created) == 2
    assert created[0].workspace_id is not None
    assert created[0].workspace_id == created[1].workspace_id


def test_list_assets_filters_by_workspace(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "inventory.db")
    ws_a = repo.create_workspace(source="a").id
    ws_b = repo.create_workspace(source="b").id
    repo.create_asset(AssetCreate(asset_type="server", name="host-a"), workspace_id=ws_a)
    repo.create_asset(AssetCreate(asset_type="server", name="host-b"), workspace_id=ws_b)

    scoped = repo.list_assets(workspace_id=ws_a)

    assert [asset.name for asset in scoped] == ["host-a"]
    assert len(repo.list_assets()) == 2


def test_list_risk_results_filters_by_workspace(tmp_path: Path) -> None:
    repo = AssetRepository(tmp_path / "inventory.db")
    ws_a = repo.create_workspace(source="a").id
    ws_b = repo.create_workspace(source="b").id
    scan_a_id, _ = repo.create_scan(
        ScanIngestRequest(source="manual", assets=[AssetCreate(asset_type="server", name="risk-host-a")]),
        workspace_id=ws_a,
    )
    scan_b_id, _ = repo.create_scan(
        ScanIngestRequest(source="manual", assets=[AssetCreate(asset_type="server", name="risk-host-b")]),
        workspace_id=ws_b,
    )
    risk_payload = {
        "scenario": "public_timeline",
        "scenario_multiplier": 1.0,
        "base_score": 3.0,
        "final_score": 3.0,
        "normalized_score_100": 60.0,
        "rating": "medium",
        "rationale": {},
    }
    repo.create_risk_result(scan_id=scan_a_id, asset_name="risk-host-a", payload=risk_payload)
    repo.create_risk_result(scan_id=scan_b_id, asset_name="risk-host-b", payload=risk_payload)

    scoped = repo.list_risk_results(workspace_id=ws_a)

    assert [risk.asset_name for risk in scoped] == ["risk-host-a"]
    assert len(repo.list_risk_results()) == 2


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

    scan_id, _workspace_id = repo.create_scan(payload)
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
