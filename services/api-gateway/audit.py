"""Audit log foundation for the API gateway (Product v1 roadmap Phase 3 item 8).

Records who did what, when, from where, and whether it succeeded, for the
mutating actions docs/product-v1-roadmap.md names explicitly (login/logout,
user creation, workspace creation, scan job creation/evidence ingest, report
generation) plus every access denied by auth.py/main.py's RBAC layer (failed
authentication and failed authorization). "before/after summary" is a
best-effort, short structured description of the request/result -- not a
full field-level diff -- deliberately, since a real diff would need hooks
into every downstream service's own mutation logic, not just the gateway;
that's beyond a "foundation".

Same dual SQLite/Postgres model as auth.py (see tools/db_compat.py): SQLite
for bare-metal dev/tests/CI (implicit schema creation), Postgres for
production (schema owned by migrations/, see
docs/adr/0001-product-v1-architecture.md). Shares api-gateway's single
Alembic migration history (alembic_version_gateway) -- audit_events is
migration 0002 there, not a separate history.
"""
from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
from tools.db_compat import Connection, connect, is_postgres_target  # noqa: E402

from auth import DEFAULT_DB_PATH  # noqa: E402  (same physical DB as users/sessions)


class AuditEvent(BaseModel):
    id: str
    timestamp: str
    actor_user_id: Optional[str] = None
    actor_role: Optional[str] = None
    workspace_id: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    source_ip: Optional[str] = None
    request_id: str
    summary: Optional[str] = None
    result: str  # "success" | "failure"


class AuditRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        if not is_postgres_target(self.db_path):
            self._ensure_schema()

    def _connect(self) -> Connection:
        return connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
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
            connection.commit()

    def record(
        self,
        *,
        action: str,
        result: str,
        actor_user_id: str | None = None,
        actor_role: str | None = None,
        workspace_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        source_ip: str | None = None,
        request_id: str | None = None,
        summary: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            workspace_id=workspace_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            source_ip=source_ip,
            request_id=request_id or str(uuid.uuid4()),
            summary=summary,
            result=result,
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO audit_events (
                    id, timestamp, actor_user_id, actor_role, workspace_id, action,
                    resource_type, resource_id, source_ip, request_id, summary, result
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    event.timestamp,
                    event.actor_user_id,
                    event.actor_role,
                    event.workspace_id,
                    event.action,
                    event.resource_type,
                    event.resource_id,
                    event.source_ip,
                    event.request_id,
                    event.summary,
                    event.result,
                ),
            )
            connection.commit()
        return event

    def list_events(self, limit: int = 200) -> list[AuditEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [AuditEvent(**dict(row)) for row in rows]
