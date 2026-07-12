import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .models import (
    Asset,
    AssetCreate,
    AssetUpdate,
    ReportRecord,
    RiskRecord,
    ScanIngestRequest,
    ScanRecord,
    Workspace,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
from tools.db_compat import Connection, connect, existing_columns, is_postgres_target  # noqa: E402

# DATABASE_URL (postgres://... or postgresql://...) takes priority when set --
# used by infra/docker/docker-compose.yml so the deployed product runs on
# Postgres. Otherwise falls back to SQLite: INVENTORY_DB_PATH lets a caller
# (e.g. the local flow runner) point the store at an isolated database so a
# demonstration run does not accumulate into the dev DB. See
# tools/db_compat.py and infra/docker/README.md.
DEFAULT_DB_PATH = os.getenv("DATABASE_URL") or os.getenv("INVENTORY_DB_PATH") or str(
    Path(__file__).resolve().parent.parent / "inventory.db"
)


class AssetRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        # Postgres (production mode) relies on Alembic migrations having already
        # run (see migrations/, docs/adr/0001-product-v1-architecture.md) --
        # never silently creates schema. SQLite (dev/test) keeps the existing
        # implicit-create-on-first-use convenience.
        if not is_postgres_target(self.db_path):
            self._ensure_schema()

    def _connect(self) -> Connection:
        return connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    source TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
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
                    tls_evidence TEXT,
                    ssh_evidence TEXT,
                    ipsec_evidence TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS risk_results (
                    id TEXT PRIMARY KEY,
                    scan_id TEXT NOT NULL,
                    contract_version TEXT NOT NULL DEFAULT 'stage1-v1',
                    asset_name TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    scenario_multiplier REAL NOT NULL,
                    base_score REAL NOT NULL,
                    final_score REAL NOT NULL,
                    normalized_score_100 REAL NOT NULL,
                    rating TEXT NOT NULL,
                    dependency_count INTEGER NOT NULL DEFAULT 0,
                    vendor_blocked INTEGER NOT NULL DEFAULT 0,
                    rationale TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reports (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT NOT NULL,
                    report_type TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    content TEXT NOT NULL
                )
                """
            )
            self._ensure_risk_result_columns(connection)
            self._ensure_scan_columns(connection)
            self._ensure_asset_columns(connection)
            connection.commit()

    @staticmethod
    def _ensure_risk_result_columns(connection: Connection) -> None:
        columns = existing_columns(connection, "risk_results")
        if "contract_version" not in columns:
            connection.execute(
                "ALTER TABLE risk_results ADD COLUMN contract_version TEXT NOT NULL DEFAULT 'stage1-v1'"
            )
        if "dependency_count" not in columns:
            connection.execute(
                "ALTER TABLE risk_results ADD COLUMN dependency_count INTEGER NOT NULL DEFAULT 0"
            )
        if "vendor_blocked" not in columns:
            connection.execute(
                "ALTER TABLE risk_results ADD COLUMN vendor_blocked INTEGER NOT NULL DEFAULT 0"
            )
        if "created_at" not in columns:
            # Portable substitute for SQLite's implicit rowid (not available on
            # Postgres) as the "most recent first" ordering key -- see
            # list_risk_results().
            connection.execute("ALTER TABLE risk_results ADD COLUMN created_at TEXT")

    @staticmethod
    def _ensure_scan_columns(connection: Connection) -> None:
        columns = existing_columns(connection, "scans")
        if "workspace_id" not in columns:
            connection.execute("ALTER TABLE scans ADD COLUMN workspace_id TEXT")
        if "ssh_evidence" not in columns:
            connection.execute("ALTER TABLE scans ADD COLUMN ssh_evidence TEXT")
        if "ipsec_evidence" not in columns:
            connection.execute("ALTER TABLE scans ADD COLUMN ipsec_evidence TEXT")

    @staticmethod
    def _ensure_asset_columns(connection: Connection) -> None:
        columns = existing_columns(connection, "assets")
        if "created_at" not in columns:
            connection.execute("ALTER TABLE assets ADD COLUMN created_at TEXT")
        if "workspace_id" not in columns:
            connection.execute("ALTER TABLE assets ADD COLUMN workspace_id TEXT")

    def create_workspace(self, source: str | None) -> Workspace:
        workspace_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO workspaces (id, source, created_at) VALUES (?, ?, ?)",
                (workspace_id, source, created_at),
            )
            connection.commit()
        return Workspace(id=workspace_id, source=source, created_at=created_at)

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        return Workspace(**dict(row)) if row else None

    def list_workspaces(self) -> list[Workspace]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM workspaces ORDER BY created_at DESC").fetchall()
        return [Workspace(**dict(row)) for row in rows]

    def create_report(self, workspace_id: str, report_type: str, content: str) -> ReportRecord:
        report_id = str(uuid.uuid4())
        generated_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reports (id, workspace_id, report_type, generated_at, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (report_id, workspace_id, report_type, generated_at, content),
            )
            connection.commit()
        return ReportRecord(
            id=report_id, workspace_id=workspace_id, report_type=report_type,
            generated_at=generated_at, content=content,
        )

    def get_report(self, report_id: str) -> ReportRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return ReportRecord(**dict(row)) if row else None

    def list_reports(self, workspace_id: str | None = None) -> list[ReportRecord]:
        query = "SELECT * FROM reports"
        params: tuple[Any, ...] = ()
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params = (workspace_id,)
        query += " ORDER BY generated_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [ReportRecord(**dict(row)) for row in rows]

    def list_scans_by_workspace(self, workspace_id: str) -> list[ScanRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM scans WHERE workspace_id = ? ORDER BY scanned_at ASC", (workspace_id,)
            ).fetchall()
        return [self._row_to_scan(row) for row in rows]

    def _find_existing_asset(self, payload: AssetCreate) -> Asset | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM assets
                WHERE name = ? AND asset_type = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (payload.name, payload.asset_type),
            ).fetchone()
        return Asset(**dict(row)) if row else None

    def list_assets(self, workspace_id: str | None = None) -> list[Asset]:
        query = "SELECT * FROM assets"
        params: tuple[Any, ...] = ()
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params = (workspace_id,)
        query += " ORDER BY name ASC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [Asset(**dict(row)) for row in rows]

    def get_asset(self, asset_id: str) -> Asset | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
        return Asset(**dict(row)) if row else None

    def create_asset(self, payload: AssetCreate, workspace_id: str | None = None) -> Asset:
        """workspace_id is only recorded when the asset is actually created --
        it marks "first discovered in this workspace"; reusing an existing
        asset (matched by name+type) in a later workspace's scan does not
        change its workspace_id, matching created_at's immutable-on-creation
        semantics. Mirrors create_scan's hybrid workspace model: if the
        caller doesn't pass workspace_id, a new single-asset workspace is
        auto-created (once we know we're actually inserting, not reusing an
        existing asset) so every asset always ends up in some workspace."""
        existing = self._find_existing_asset(payload)
        if existing is not None:
            return existing

        if workspace_id is None:
            workspace_id = self.create_workspace(source="manual").id

        asset_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO assets (id, asset_type, name, owner, criticality, environment, vendor, lifecycle_years, created_at, workspace_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    payload.asset_type,
                    payload.name,
                    payload.owner,
                    payload.criticality,
                    payload.environment or "unknown",
                    payload.vendor,
                    payload.lifecycle_years,
                    created_at,
                    workspace_id,
                ),
            )
            connection.commit()
        created = self.get_asset(asset_id)
        assert created is not None
        return created

    def create_many(self, payloads: Iterable[AssetCreate], workspace_id: str | None = None) -> list[Asset]:
        # Resolve once so a batch of assets shares one auto-created workspace
        # instead of each asset scattering into its own (create_asset would
        # otherwise auto-create independently per call when workspace_id is None).
        if workspace_id is None:
            workspace_id = self.create_workspace(source="manual").id
        return [self.create_asset(payload, workspace_id=workspace_id) for payload in payloads]

    def update_asset(self, asset_id: str, payload: AssetUpdate) -> Asset | None:
        existing = self.get_asset(asset_id)
        if existing is None:
            return None
        merged = existing.model_copy(update=payload.model_dump(exclude_unset=True))
        if not merged.environment:
            # Guard against an update explicitly nulling out environment --
            # every persisted asset always has a non-null environment.
            merged.environment = existing.environment or "unknown"
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

    def create_scan(self, payload: ScanIngestRequest, workspace_id: str | None = None) -> tuple[str, str]:
        """Returns (scan_id, workspace_id). Hybrid workspace model: if the
        caller doesn't pass workspace_id, a new single-scan workspace is
        auto-created (source = this scan's source) so every scan always
        belongs to some workspace, no caller changes required."""
        if workspace_id is None:
            workspace_id = self.create_workspace(source=payload.source).id

        scan_id = str(uuid.uuid4())
        scanned_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO scans (id, source, scanned_at, workspace_id, host_inventory, crypto_evidence, tls_evidence, ssh_evidence, ipsec_evidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scan_id,
                    payload.source,
                    scanned_at,
                    workspace_id,
                    self._json_or_none(payload.host_inventory.model_dump() if payload.host_inventory else None),
                    self._json_or_none(payload.crypto_evidence.model_dump() if payload.crypto_evidence else None),
                    self._json_or_none(payload.tls_evidence.model_dump() if payload.tls_evidence else None),
                    self._json_or_none(payload.ssh_evidence.model_dump() if payload.ssh_evidence else None),
                    self._json_or_none(payload.ipsec_evidence.model_dump() if payload.ipsec_evidence else None),
                ),
            )
            connection.commit()
        return scan_id, workspace_id

    def list_scans(self) -> list[ScanRecord]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM scans ORDER BY scanned_at DESC").fetchall()
        return [self._row_to_scan(row) for row in rows]

    def get_scan(self, scan_id: str) -> ScanRecord | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM scans WHERE id = ?", (scan_id,)).fetchone()
        return self._row_to_scan(row) if row else None

    def create_risk_result(self, scan_id: str, asset_name: str, payload: dict[str, Any]) -> str:
        result_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO risk_results (
                    id, scan_id, contract_version, asset_name, scenario, scenario_multiplier, base_score,
                    final_score, normalized_score_100, rating, dependency_count, vendor_blocked, rationale,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    scan_id,
                    payload.get("contract_version", "stage1-v1"),
                    asset_name,
                    payload["scenario"],
                    payload["scenario_multiplier"],
                    payload["base_score"],
                    payload["final_score"],
                    payload["normalized_score_100"],
                    payload["rating"],
                    int(payload.get("dependency_count", 0)),
                    int(bool(payload.get("vendor_blocked", False))),
                    json.dumps(payload["rationale"]),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.commit()
        return result_id

    def list_risk_results(self, scan_id: str | None = None, workspace_id: str | None = None) -> list[RiskRecord]:
        # risk_results has no workspace_id column of its own -- it's scoped to a
        # workspace transitively through its scan, so filtering by workspace_id
        # joins against scans (unlike the scan_id filter, which needs no join).
        if workspace_id is not None:
            query = "SELECT r.* FROM risk_results r JOIN scans s ON r.scan_id = s.id WHERE s.workspace_id = ?"
            params: tuple[Any, ...] = (workspace_id,)
            if scan_id is not None:
                query += " AND r.scan_id = ?"
                params += (scan_id,)
            query += " ORDER BY r.created_at DESC"
        else:
            query = "SELECT * FROM risk_results"
            params = ()
            if scan_id is not None:
                query += " WHERE scan_id = ?"
                params = (scan_id,)
            query += " ORDER BY created_at DESC"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [self._row_to_risk(row) for row in rows]

    def list_asset_risk_history(self, asset_name: str) -> list[dict[str, Any]]:
        """Chronological risk trend for an asset across all persisted scans.

        Joins each risk result to its scan so the caller sees how an asset's
        posture changed over time (one row per risk result, oldest first)."""
        query = """
            SELECT r.scan_id AS scan_id,
                   s.scanned_at AS scanned_at,
                   r.scenario AS scenario,
                   r.rating AS rating,
                   r.normalized_score_100 AS normalized_score_100,
                   r.final_score AS final_score
            FROM risk_results r
            JOIN scans s ON r.scan_id = s.id
            WHERE r.asset_name = ?
            ORDER BY s.scanned_at ASC, r.created_at ASC
        """
        with self._connect() as connection:
            rows = connection.execute(query, (asset_name,)).fetchall()
        return [dict(row) for row in rows]

    def cleanup_duplicate_assets(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, asset_type, created_at
                FROM assets
                ORDER BY created_at DESC
                """
            ).fetchall()

            seen: set[tuple[str, str]] = set()
            delete_ids: list[str] = []

            for row in rows:
                key = (row["name"], row["asset_type"])
                if key in seen:
                    delete_ids.append(row["id"])
                else:
                    seen.add(key)

            deleted_assets = 0
            for asset_id in delete_ids:
                cur = connection.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
                deleted_assets += cur.rowcount

            connection.commit()

        return {"deleted_assets": deleted_assets}

    def _row_to_scan(self, row: Any) -> ScanRecord:
        return ScanRecord(
            id=row["id"],
            source=row["source"],
            scanned_at=row["scanned_at"],
            workspace_id=row["workspace_id"],
            host_inventory=self._parse_json(row["host_inventory"]),
            crypto_evidence=self._parse_json(row["crypto_evidence"]),
            tls_evidence=self._parse_json(row["tls_evidence"]),
            ssh_evidence=self._parse_json(row["ssh_evidence"]),
            ipsec_evidence=self._parse_json(row["ipsec_evidence"]),
        )

    def _row_to_risk(self, row: Any) -> RiskRecord:
        return RiskRecord(
            id=row["id"],
            scan_id=row["scan_id"],
            contract_version=row["contract_version"],
            asset_name=row["asset_name"],
            scenario=row["scenario"],
            scenario_multiplier=row["scenario_multiplier"],
            base_score=row["base_score"],
            final_score=row["final_score"],
            normalized_score_100=row["normalized_score_100"],
            rating=row["rating"],
            dependency_count=row["dependency_count"],
            vendor_blocked=bool(row["vendor_blocked"]),
            rationale=json.loads(row["rationale"]),
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
