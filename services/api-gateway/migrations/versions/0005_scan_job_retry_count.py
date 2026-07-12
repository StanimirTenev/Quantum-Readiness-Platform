"""Add scan_jobs.retry_count

Mirrors scan_jobs.py's _ensure_schema() CREATE TABLE statement -- see
docs/adr/0001-product-v1-architecture.md and
docs/product-v1-roadmap.md Phase 4 item 11 (Worker Queue v1 -- retry/failed
state).

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-12

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE scan_jobs ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0")


def downgrade() -> None:
    op.execute("ALTER TABLE scan_jobs DROP COLUMN retry_count")
