"""Enforce assets.environment NOT NULL

Product v1 roadmap Phase 2 item 4 acceptance: "всяко asset има environment"
(every asset has an environment). app/repository.py already defaults a
missing/blank environment to "unknown" on every create/update path; this
migration backfills any pre-existing NULL rows the same way and then adds
the DB-level constraint so Postgres (production) enforces the invariant
directly, not just the application layer. SQLite (dev-only, see
docs/adr/0001-product-v1-architecture.md) keeps its existing nullable
column -- the application-layer default is what SQLite relies on.

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
    op.execute("UPDATE assets SET environment = 'unknown' WHERE environment IS NULL")
    op.execute("ALTER TABLE assets ALTER COLUMN environment SET DEFAULT 'unknown'")
    op.execute("ALTER TABLE assets ALTER COLUMN environment SET NOT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE assets ALTER COLUMN environment DROP NOT NULL")
    op.execute("ALTER TABLE assets ALTER COLUMN environment DROP DEFAULT")
