"""Add scan_jobs table

Mirrors scan_jobs.py's _ensure_schema() CREATE TABLE statement -- see
docs/adr/0001-product-v1-architecture.md and
docs/product-v1-roadmap.md Phase 4 item 10 (Scan Job Model).

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-12

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE scan_jobs (
            id TEXT PRIMARY KEY,
            workspace_id TEXT,
            scan_type TEXT NOT NULL,
            payload TEXT NOT NULL,
            scenario TEXT NOT NULL,
            targets TEXT,
            status TEXT NOT NULL,
            created_by TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            logs TEXT,
            result_summary TEXT
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scan_jobs")
