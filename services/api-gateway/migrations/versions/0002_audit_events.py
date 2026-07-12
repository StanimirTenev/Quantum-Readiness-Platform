"""Add audit_events table

Mirrors audit.py's _ensure_schema() CREATE TABLE statement -- see
docs/adr/0001-product-v1-architecture.md and
docs/product-v1-roadmap.md Phase 3 item 8 (Audit Log Foundation).

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-12

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE audit_events (
            id TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            actor_user_id TEXT,
            actor_role TEXT,
            workspace_id TEXT,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            source_ip TEXT,
            request_id TEXT NOT NULL,
            summary TEXT,
            result TEXT NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS audit_events")
