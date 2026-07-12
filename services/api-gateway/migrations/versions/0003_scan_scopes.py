"""Add scan_scopes table

Mirrors scan_scope.py's _ensure_schema() CREATE TABLE statement -- see
docs/adr/0001-product-v1-architecture.md and
docs/product-v1-roadmap.md Phase 4 item 9 (Scan Scope Manager).

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-12

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE scan_scopes (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            allowed_cidr_ranges TEXT,
            allowed_domains TEXT,
            excluded_targets TEXT,
            allowed_scan_types TEXT,
            scan_windows TEXT,
            rate_limits TEXT,
            created_by TEXT,
            approved_by TEXT,
            created_at TEXT NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS scan_scopes")
