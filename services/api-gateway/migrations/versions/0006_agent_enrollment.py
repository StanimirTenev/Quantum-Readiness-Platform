"""Add agent_enrollment_tokens and agents tables

Mirrors agents.py's _ensure_schema() CREATE TABLE statements -- see
docs/adr/0001-product-v1-architecture.md and
docs/product-v1-roadmap.md Phase 5 item 12 (Agent Enrollment).

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-12

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE agent_enrollment_tokens (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            label TEXT,
            created_by TEXT,
            created_at TEXT NOT NULL,
            revoked_at TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL,
            enrollment_token_id TEXT NOT NULL,
            hostname_hash TEXT NOT NULL,
            os_type TEXT NOT NULL,
            agent_version TEXT NOT NULL,
            capabilities TEXT,
            status TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agents")
    op.execute("DROP TABLE IF EXISTS agent_enrollment_tokens")
