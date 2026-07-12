"""Agent enrollment (Product v1 roadmap Phase 5 item 12).

Linux/Windows agents become managed agents, not just scripts: an
Admin/Security Architect creates an enrollment token for a workspace; the
agent is installed with that token and calls POST /api/agents/register,
which validates the token and issues an agent_id. The agent then calls
POST /api/agents/{agent_id}/heartbeat (using the same enrollment token as
its bearer credential -- see module note below) to keep last_seen current.

Register/heartbeat are agent-facing, not human-facing: they bypass
main.py's session/RBAC enforcement entirely (see RBAC_PUBLIC_PATHS and
_is_agent_heartbeat_path in main.py) and authenticate via the enrollment token instead (passed as
`Authorization: Bearer <token>`), matching how QRP_API_KEY is a separate,
orthogonal machine-trust mechanism from human RBAC (see
docs/adr/0001-product-v1-architecture.md). One enrollment token can
register many agents (a fleet install code, not a per-agent secret) --
revoking it cuts off both new registrations and heartbeats from every
agent that shares it, which is the intended "revoke this fleet's access"
semantic, not tracked as a separate cascading update.

Wiring evidence ingestion (POST /api/scans/*) to require agent identity is
explicitly out of scope here -- none of this task's acceptance criteria
need it, and changing already-working ingestion routes is a much larger,
separate concern (roadmap item 13, Agent Security, deals with the
token/evidence-handling side of that). hostname is hashed before storage
(never kept raw), matching the roadmap's own "hostname_hash or redacted
host id" model field and this project's established evidence-redaction
conventions elsewhere (e.g. windows_evidence.py).

Same dual SQLite/Postgres model as auth.py (see tools/db_compat.py).
Shares api-gateway's single Alembic migration history (alembic_version_gateway).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
from tools.db_compat import Connection, connect, is_postgres_target  # noqa: E402

from auth import DEFAULT_DB_PATH  # noqa: E402  (same physical DB as users/sessions/audit/...)

AgentStatus = Literal["active", "unsupported_version"]

# No agent version has shipped below this -- see _is_supported_version.
MIN_SUPPORTED_AGENT_VERSION = "1.0.0"


def _hash_token(token: str) -> str:
    # Same pattern as auth.py's session tokens: store hashed, never raw, so
    # a DB dump alone doesn't yield a usable enrollment credential.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_hostname(hostname: str) -> str:
    return hashlib.sha256(hostname.encode("utf-8")).hexdigest()


def _parse_version(version: str) -> tuple[int, ...]:
    parts: list[int] = []
    for segment in version.strip().split("."):
        digits = "".join(ch for ch in segment if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def _is_supported_version(version: str, minimum: str = MIN_SUPPORTED_AGENT_VERSION) -> bool:
    return _parse_version(version) >= _parse_version(minimum)


class EnrollmentTokenCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1)
    label: Optional[str] = None


class EnrollmentToken(BaseModel):
    id: str
    workspace_id: str
    label: Optional[str] = None
    created_by: Optional[str] = None
    created_at: str
    revoked_at: Optional[str] = None


class EnrollmentTokenCreated(EnrollmentToken):
    token: str = Field(..., description="Raw enrollment token -- shown only once, at creation.")


class AgentRegisterRequest(BaseModel):
    hostname: str = Field(..., min_length=1, description="Hashed before storage, never kept raw.")
    os_type: str = Field(..., min_length=1)
    agent_version: str = Field(..., min_length=1)
    capabilities: list[str] = Field(default_factory=list)


class AgentRegisterResponse(BaseModel):
    agent_id: str
    status: AgentStatus
    config: dict[str, Any] = Field(default_factory=dict)


class Agent(BaseModel):
    id: str
    workspace_id: str
    enrollment_token_id: str
    hostname_hash: str
    os_type: str
    agent_version: str
    capabilities: list[str]
    status: AgentStatus
    last_seen: str
    created_at: str


def _row_to_token(row: Any) -> EnrollmentToken:
    data = dict(row)
    return EnrollmentToken(
        id=data["id"], workspace_id=data["workspace_id"], label=data.get("label"),
        created_by=data.get("created_by"), created_at=data["created_at"], revoked_at=data.get("revoked_at"),
    )


def _row_to_agent(row: Any) -> Agent:
    data = dict(row)
    return Agent(
        id=data["id"], workspace_id=data["workspace_id"], enrollment_token_id=data["enrollment_token_id"],
        hostname_hash=data["hostname_hash"], os_type=data["os_type"], agent_version=data["agent_version"],
        capabilities=json.loads(data["capabilities"] or "[]"), status=data["status"],
        last_seen=data["last_seen"], created_at=data["created_at"],
    )


class AgentRepository:
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
                CREATE TABLE IF NOT EXISTS agent_enrollment_tokens (
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS agents (
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
            connection.commit()

    # --- Enrollment tokens ---

    def create_token(self, payload: EnrollmentTokenCreate, created_by: str | None) -> EnrollmentTokenCreated:
        token_id = str(uuid.uuid4())
        raw_token = secrets.token_urlsafe(32)
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO agent_enrollment_tokens (id, workspace_id, token_hash, label, created_by, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (token_id, payload.workspace_id, _hash_token(raw_token), payload.label, created_by, created_at),
            )
            connection.commit()
        return EnrollmentTokenCreated(
            id=token_id, workspace_id=payload.workspace_id, label=payload.label,
            created_by=created_by, created_at=created_at, token=raw_token,
        )

    def list_tokens(self, workspace_id: str | None = None) -> list[EnrollmentToken]:
        query = "SELECT * FROM agent_enrollment_tokens"
        params: tuple[Any, ...] = ()
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params = (workspace_id,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_token(row) for row in rows]

    def get_token(self, token_id: str) -> EnrollmentToken | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM agent_enrollment_tokens WHERE id = ?", (token_id,)).fetchone()
        return _row_to_token(row) if row else None

    def revoke_token(self, token_id: str) -> EnrollmentToken | None:
        if self.get_token(token_id) is None:
            return None
        with self._connect() as connection:
            connection.execute(
                "UPDATE agent_enrollment_tokens SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                (datetime.now(UTC).isoformat(), token_id),
            )
            connection.commit()
        return self.get_token(token_id)

    def verify_token(self, raw_token: str) -> EnrollmentToken | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM agent_enrollment_tokens WHERE token_hash = ?", (_hash_token(raw_token),)
            ).fetchone()
        if row is None:
            return None
        token = _row_to_token(row)
        return token if token.revoked_at is None else None

    # --- Agents ---

    def register_agent(self, token: EnrollmentToken, payload: AgentRegisterRequest) -> Agent:
        agent_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()
        status: AgentStatus = "active" if _is_supported_version(payload.agent_version) else "unsupported_version"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO agents (
                    id, workspace_id, enrollment_token_id, hostname_hash, os_type,
                    agent_version, capabilities, status, last_seen, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agent_id, token.workspace_id, token.id, _hash_hostname(payload.hostname),
                    payload.os_type, payload.agent_version, json.dumps(payload.capabilities),
                    status, now, now,
                ),
            )
            connection.commit()
        return Agent(
            id=agent_id, workspace_id=token.workspace_id, enrollment_token_id=token.id,
            hostname_hash=_hash_hostname(payload.hostname), os_type=payload.os_type,
            agent_version=payload.agent_version, capabilities=payload.capabilities,
            status=status, last_seen=now, created_at=now,
        )

    def get_agent(self, agent_id: str) -> Agent | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
        return _row_to_agent(row) if row else None

    def list_agents(self, workspace_id: str | None = None) -> list[Agent]:
        query = "SELECT * FROM agents"
        params: tuple[Any, ...] = ()
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params = (workspace_id,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_agent(row) for row in rows]

    def touch_last_seen(self, agent_id: str) -> Agent | None:
        if self.get_agent(agent_id) is None:
            return None
        with self._connect() as connection:
            connection.execute(
                "UPDATE agents SET last_seen = ? WHERE id = ?", (datetime.now(UTC).isoformat(), agent_id)
            )
            connection.commit()
        return self.get_agent(agent_id)
