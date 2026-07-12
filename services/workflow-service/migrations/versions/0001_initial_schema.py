"""Initial schema (tasks, approvals)

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
        CREATE TABLE tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            asset_name TEXT NOT NULL,
            wave TEXT NOT NULL,
            priority TEXT NOT NULL,
            description TEXT NOT NULL,
            recommended_action TEXT,
            status TEXT NOT NULL,
            requested_by TEXT NOT NULL DEFAULT 'unknown',
            created_at TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE approvals (
            id TEXT PRIMARY KEY,
            task_id TEXT NOT NULL,
            approver TEXT NOT NULL,
            decision TEXT NOT NULL,
            note TEXT,
            created_at TEXT
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS approvals")
    op.execute("DROP TABLE IF EXISTS tasks")
