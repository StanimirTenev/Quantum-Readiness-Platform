from pathlib import Path

from app.models import AssetCreate, AssetUpdate
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
