"""Initial schema (workspaces, assets, scans, risk_results, reports)

Mirrors app/repository.py's _ensure_schema() CREATE TABLE statements plus
every column its _ensure_*_columns() helpers have since added via
ALTER TABLE on SQLite -- baked directly into the CREATE TABLE here since a
fresh Postgres database created through this migration never needs the
ALTER-TABLE-if-missing dance SQLite still uses for backward compatibility
with pre-existing dev databases.

Revision ID: 0001
Revises:
Create Date: 2026-07-12

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE workspaces (
            id TEXT PRIMARY KEY,
            source TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE assets (
            id TEXT PRIMARY KEY,
            asset_type TEXT NOT NULL,
            name TEXT NOT NULL,
            owner TEXT,
            criticality INTEGER,
            environment TEXT,
            vendor TEXT,
            lifecycle_years INTEGER,
            created_at TEXT,
            workspace_id TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE scans (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            scanned_at TEXT NOT NULL,
            host_inventory TEXT,
            crypto_evidence TEXT,
            tls_evidence TEXT,
            ssh_evidence TEXT,
            ipsec_evidence TEXT,
            workspace_id TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE risk_results (
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
            rationale TEXT NOT NULL,
            created_at TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE reports (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            report_type TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            content TEXT NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS reports")
    op.execute("DROP TABLE IF EXISTS risk_results")
    op.execute("DROP TABLE IF EXISTS scans")
    op.execute("DROP TABLE IF EXISTS assets")
    op.execute("DROP TABLE IF EXISTS workspaces")
