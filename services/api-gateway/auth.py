"""Local authentication for the API gateway (Product v1 roadmap Phase 3 item 6).

Real per-user accounts + sessions, replacing QRP_API_KEY as the *only*
protection available (see docs/adr/0001-product-v1-architecture.md). Kept
deliberately minimal, matching the roadmap's "Да НЕ се прави още" list for
this task: no SSO/OIDC, no multi-tenant accounts. RBAC route enforcement
(who is allowed to call what) and the audit log are separate, later tasks
(roadmap items 7-8) -- this module only proves identity and maintains a
session; it does not yet gate any route by role.

Same dual SQLite/Postgres model as inventory-service/workflow-service (see
tools/db_compat.py): SQLite for bare-metal dev/tests/CI (implicit schema
creation), Postgres for production (schema owned by migrations/, see
docs/adr/0001-product-v1-architecture.md).
"""
from __future__ import annotations

import hashlib
import os
import secrets
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import bcrypt
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
from tools.db_compat import Connection, connect, is_postgres_target  # noqa: E402

# Mirrors inventory-service's DEFAULT_DB_PATH convention: DATABASE_URL (Postgres,
# production) takes priority; GATEWAY_DB_PATH lets bare-metal dev/tests point the
# store at an isolated file; otherwise a service-local default.
DEFAULT_DB_PATH = os.getenv("DATABASE_URL") or os.getenv("GATEWAY_DB_PATH") or str(
    Path(__file__).resolve().parent / "gateway.db"
)

SESSION_TTL = timedelta(hours=24)
Role = str  # "admin" | "security_architect" | "operator" | "auditor"


class User(BaseModel):
    id: str
    username: str
    role: Role
    created_at: Optional[str] = None


class BootstrapRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=8, max_length=255)


class LoginRequest(BaseModel):
    username: str
    password: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=255)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def _hash_token(token: str) -> str:
    # Session tokens are stored hashed (like passwords) so a DB dump alone
    # doesn't yield usable session credentials -- the raw token only ever
    # lives in the response cookie.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class AuthRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        # Postgres (production) relies on Alembic migrations having already run
        # (see migrations/, docs/adr/0001-product-v1-architecture.md) -- never
        # silently creates schema. SQLite (dev/test) keeps the existing
        # implicit-create-on-first-use convenience.
        if not is_postgres_target(self.db_path):
            self._ensure_schema()

    def _connect(self) -> Connection:
        return connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    @staticmethod
    def _row_to_user(row: Any) -> User:
        data = dict(row)
        return User(id=data["id"], username=data["username"], role=data["role"], created_at=data.get("created_at"))

    def count_users(self) -> int:
        with self._connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS n FROM users").fetchone()
        return int(dict(row)["n"])

    def create_user(self, username: str, password: str, role: Role) -> User:
        user_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO users (id, username, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, hash_password(password), role, created_at),
            )
            connection.commit()
        return User(id=user_id, username=username, role=role, created_at=created_at)

    def get_user_by_id(self, user_id: str) -> User | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return self._row_to_user(row) if row else None

    def verify_credentials(self, username: str, password: str) -> User | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if row is None:
            return None
        data = dict(row)
        if not verify_password(password, data["password_hash"]):
            return None
        return self._row_to_user(row)

    def update_password(self, user_id: str, new_password: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(new_password), user_id),
            )
            connection.commit()

    def create_session(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(UTC)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO sessions (id, user_id, token_hash, created_at, expires_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, _hash_token(token), now.isoformat(), (now + SESSION_TTL).isoformat()),
            )
            connection.commit()
        return token

    def get_session_user(self, token: str) -> User | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE token_hash = ?", (_hash_token(token),)
            ).fetchone()
            if row is None:
                return None
            session = dict(row)
            if datetime.fromisoformat(session["expires_at"]) < datetime.now(UTC):
                return None
            user_row = connection.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
        return self._row_to_user(user_row) if user_row else None

    def delete_session(self, token: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
            connection.commit()
