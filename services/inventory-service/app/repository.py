import json
import sqlite3
import uuid
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Iterable

from .models import Asset, AssetCreate, AssetUpdate, ScanIngestRequest, ScanRecord

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "inventory.db"


class AssetRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY,
                    asset_type TEXT NOT NULL,
                    name TEXT NOT NULL,
                    owner TEXT,
                    criticality INTEGER,
                    environment TEXT,
                    vendor TEXT,
                    lifecycle_years INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS scans (
                    id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    scanned_at TEXT NOT NULL,
                    host_inventory TEXT,
                    crypto_evidence TEXT,
                    tls_evidence TEXT
                )
                """
            )
            connection.commit()

    def list_assets(self) -> list[Asset]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM assets ORDER BY name ASC").fetchall()
        return [Asset(**dict(row)) for row in rows]

    def get_asset(self, asset_id: str) -> Asset | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return Asset(**dict(row)) if row else None

    def create_asset(self, payload: AssetCreate) -> Asset:
        asset_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO assets (id, asset_type, name, owner, criticality, environment, vendor, lifecycle_years)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    payload.asset_type,
                    payload.name,
                    payload.owner,
                    payload.criticality,
                    payload.environment,
                    payload.vendor,
                    payload.lifecycle_years,
                ),
            )
            connection.commit()
        created = self.get_asset(asset_id)
        assert created is not None
        return created

    def create_many(self, payloads: Iterable[AssetCreate]) -> list[Asset]:
        return [self.create_asset(payload) for payload in payloads]

    def update_asset(self, asset_id: str, payload: AssetUpdate) -> Asset | None:
        existing = self.get_asset(asset_id)
        if existing is None:
            return None
        merged = existing.model_copy(update=payload.model_dump(exclude_unset=True))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE assets
                SET asset_type = ?, name = ?, owner = ?, criticality = ?, environment = ?, vendor = ?, lifecycle_years = ?
                WHERE id = ?
                """,
                (
                    merged.asset_type,
                    merged.name,
                    merged.owner,
                    merged.criticality,
                    merged.environment,
                    merged.vendor,
                    merged.lifecycle_years,
                    asset_id,
                ),
            )
            connection.commit()
        return self.get_asset(asset_id)

    def delete_asset(self, asset_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
            connection.commit()
        return cursor.rowcount > 0

    def create_scan(self, payload: ScanIngestRequest) -> str:
        scan_id = str(uuid.uuid4())
        scanned_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO scans (id, source, scanned_at, host_inventory, crypto_evidence, tls_evidence)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_id,
                    payload.source,
                    scanned_at,
                    self._json_or_none(payload.host_inventory.model_dump() if payload.host_inventory else None),
                    self._json_or_none(payload.crypto_evidence.model_dump() if payload.crypto_evidence else None),
                    self._json_or_none(payload.tls_evidence.model_dump() if payload.tls_evidence else None),
                ),
            )
            connection.commit()
        return scan_id

    def list_scans(self) -> list[ScanRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM scans ORDER BY scanned_at DESC").fetchall()
        return [self._row_to_scan(row) for row in rows]

    def get_scan(self, scan_id: str) -> ScanRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        return self._row_to_scan(row) if row else None

    def _row_to_scan(self, row: sqlite3.Row) -> ScanRecord:
        return ScanRecord(
            id=row["id"],
            source=row["source"],
            scanned_at=row["scanned_at"],
            host_inventory=self._parse_json(row["host_inventory"]),
            crypto_evidence=self._parse_json(row["crypto_evidence"]),
            tls_evidence=self._parse_json(row["tls_evidence"]),
        )

    @staticmethod
    def _json_or_none(value: dict[str, Any] | None) -> str | None:
        if value is None:
            return None
        return json.dumps(value)

    @staticmethod
    def _parse_json(value: str | None) -> dict[str, Any] | None:
        if value is None:
            return None
        return json.loads(value)
