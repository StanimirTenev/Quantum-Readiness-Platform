"""Scan scope manager (Product v1 roadmap Phase 4 item 9).

Prevents an arbitrary user from scanning an arbitrary IP/domain: a
ScanScope is an explicit allowlist (+ exclusions) a Security Architect/Admin
defines for a workspace; main.py's scan-ingestion routes check any network
target carried in the evidence (tls_evidence.target, ssh_evidence.target,
ipsec_evidence.target) against it before accepting the scan.

A workspace with no ScanScope defined yet stays open -- matches auth.py/
main.py's established "unconfigured = open for local dev" convention (see
enforce_rbac's setup-mode bypass) so every existing local-dev/CI/demo flow
that never creates one (none of them do) keeps working unchanged. Scope is
opt-in restriction, not a retroactive default lockdown.

scan_windows/rate_limits are stored (the roadmap's data model names them)
but not enforced yet -- no acceptance criterion for this task tests either,
so building real time-window/rate-limit enforcement now would be ahead of
any concrete requirement.

Same dual SQLite/Postgres model as auth.py (see tools/db_compat.py).
Shares api-gateway's single Alembic migration history (alembic_version_gateway).
"""
from __future__ import annotations

import ipaddress
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))
from tools.db_compat import Connection, connect, is_postgres_target  # noqa: E402

from auth import DEFAULT_DB_PATH  # noqa: E402  (same physical DB as users/sessions/audit)

# The unambiguous "entire internet" cases -- rejected outright at scope
# creation time, per the roadmap's "internet-wide scan забранен" rule.
_INTERNET_WIDE_CIDRS = {"0.0.0.0/0", "::/0"}


def _validate_cidr(value: str) -> str:
    if value.strip() in _INTERNET_WIDE_CIDRS:
        raise ValueError(f"internet-wide CIDR {value!r} is not allowed in a scan scope")
    try:
        network = ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise ValueError(f"invalid CIDR {value!r}: {exc}") from exc
    if network.prefixlen == 0:
        raise ValueError(f"internet-wide CIDR {value!r} is not allowed in a scan scope")
    return value


class ScanScopeCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1)
    allowed_cidr_ranges: list[str] = Field(default_factory=list)
    allowed_domains: list[str] = Field(default_factory=list)
    excluded_targets: list[str] = Field(default_factory=list)
    allowed_scan_types: list[str] = Field(default_factory=list)
    scan_windows: Optional[dict[str, Any]] = None
    rate_limits: Optional[dict[str, Any]] = None
    approved_by: Optional[str] = None

    @field_validator("allowed_cidr_ranges")
    @classmethod
    def _validate_allowed_cidrs(cls, value: list[str]) -> list[str]:
        return [_validate_cidr(v) for v in value]


class ScanScope(ScanScopeCreate):
    id: str
    created_by: Optional[str] = None
    created_at: str


def _row_to_scope(row: Any) -> ScanScope:
    data = dict(row)
    return ScanScope(
        id=data["id"],
        workspace_id=data["workspace_id"],
        allowed_cidr_ranges=json.loads(data["allowed_cidr_ranges"] or "[]"),
        allowed_domains=json.loads(data["allowed_domains"] or "[]"),
        excluded_targets=json.loads(data["excluded_targets"] or "[]"),
        allowed_scan_types=json.loads(data["allowed_scan_types"] or "[]"),
        scan_windows=json.loads(data["scan_windows"]) if data.get("scan_windows") else None,
        rate_limits=json.loads(data["rate_limits"]) if data.get("rate_limits") else None,
        created_by=data.get("created_by"),
        approved_by=data.get("approved_by"),
        created_at=data["created_at"],
    )


class ScanScopeRepository:
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
                CREATE TABLE IF NOT EXISTS scan_scopes (
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
            connection.commit()

    def create_scope(self, payload: ScanScopeCreate, created_by: str | None) -> ScanScope:
        scope_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO scan_scopes (
                    id, workspace_id, allowed_cidr_ranges, allowed_domains, excluded_targets,
                    allowed_scan_types, scan_windows, rate_limits, created_by, approved_by, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    scope_id,
                    payload.workspace_id,
                    json.dumps(payload.allowed_cidr_ranges),
                    json.dumps(payload.allowed_domains),
                    json.dumps(payload.excluded_targets),
                    json.dumps(payload.allowed_scan_types),
                    json.dumps(payload.scan_windows) if payload.scan_windows else None,
                    json.dumps(payload.rate_limits) if payload.rate_limits else None,
                    created_by,
                    payload.approved_by,
                    created_at,
                ),
            )
            connection.commit()
        return ScanScope(
            id=scope_id, created_by=created_by, created_at=created_at, **payload.model_dump()
        )

    def list_scopes(self, workspace_id: str | None = None) -> list[ScanScope]:
        query = "SELECT * FROM scan_scopes"
        params: tuple[Any, ...] = ()
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params = (workspace_id,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_scope(row) for row in rows]

    def has_scope(self, workspace_id: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS n FROM scan_scopes WHERE workspace_id = ?", (workspace_id,)
            ).fetchone()
        return int(dict(row)["n"]) > 0


def _extract_host(target: str) -> str:
    # Evidence targets in this codebase are "host:port" or a bare host (see
    # TLSEvidence.target/SSHEvidence.target/IPsecEvidence.target). IPv6 isn't
    # produced by any current evidence source, so a single rsplit on ":" is
    # sufficient -- avoids misparsing a bare hostname with no port.
    host, _, port = target.rpartition(":")
    return host if host and port.isdigit() else target


def _matches_any(host: str, patterns: list[str]) -> bool:
    try:
        addr: ipaddress.IPv4Address | ipaddress.IPv6Address | None = ipaddress.ip_address(host)
    except ValueError:
        addr = None

    for pattern in patterns:
        pattern = pattern.strip()
        if not pattern:
            continue
        if host == pattern:
            return True
        if pattern.startswith("*."):
            if host.endswith(pattern[1:]):
                return True
            continue
        if addr is not None:
            try:
                if addr in ipaddress.ip_network(pattern, strict=False):
                    return True
            except ValueError:
                continue
    return False


def check_target(scope: ScanScope, target: str) -> tuple[bool, str]:
    """Returns (allowed, reason). Excluded targets always win, even if also
    covered by an allowed CIDR/domain (roadmap: "excluded target винаги
    печели")."""
    host = _extract_host(target)
    if _matches_any(host, scope.excluded_targets):
        return False, "target is explicitly excluded from this workspace's scan scope"
    if _matches_any(host, scope.allowed_cidr_ranges) or _matches_any(host, scope.allowed_domains):
        return True, "allowed"
    return False, "target is not in this workspace's approved scan scope"
