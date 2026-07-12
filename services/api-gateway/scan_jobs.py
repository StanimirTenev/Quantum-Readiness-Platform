"""Scan job model + queue (Product v1 roadmap Phase 4 items 10-11).

Long-running scans should not execute directly inside the API request --
POST /api/scan-jobs (main.py) queues a job and returns immediately
(status=queued) without running anything itself. A separate worker.py
process (own docker-compose service, roadmap item 11's "Postgres-backed
queue + one worker container") polls scan_jobs for status='queued', claims
one (claim_next_queued_job, race-safe via mark_running's conditional
UPDATE), and runs it through the exact same evidence-ingestion pipeline
(_ingest_scan in main.py, including scan scope enforcement from
scan_scope.py and audit logging) that /api/scans/{host,network,repo}
already use synchronously: queued -> running -> succeeded/failed.

Retry: on failure, record_failure_and_maybe_retry re-queues the job (back
to status='queued', retry_count incremented) up to SCAN_JOB_MAX_RETRIES
(env-configurable, see worker.py) attempts before giving up and marking it
permanently 'failed'. No backoff delay between attempts -- the worker's own
poll interval provides natural spacing; no acceptance criterion for this
task needs exponential backoff.

Cancellation is reliable while a job is still "queued" (checked
cooperatively via mark_running before the worker starts it); a job's own
evidence-ingestion call is typically fast, so mid-flight cancellation of an
already-"running" job is best-effort rather than a hard preemptive
guarantee -- true preemption of a genuinely long-running operation isn't
needed by any current evidence source.

Same dual SQLite/Postgres model as auth.py (see tools/db_compat.py).
Shares api-gateway's single Alembic migration history (alembic_version_gateway).
"""
from __future__ import annotations

import json
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

from auth import DEFAULT_DB_PATH  # noqa: E402  (same physical DB as users/sessions/audit/scopes)

ScanType = Literal["host", "network", "repo"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class ScanJobCreate(BaseModel):
    scan_type: ScanType
    payload: dict[str, Any] = Field(..., description="Same evidence shape /api/scans/{scan_type} accepts.")
    workspace_id: Optional[str] = None
    scenario: str = "public_timeline"
    targets: list[str] = Field(default_factory=list, description="Optional explicit target list for display; auto-extracted from evidence if omitted.")


class ScanJob(BaseModel):
    id: str
    workspace_id: Optional[str] = None
    scan_type: str
    targets: list[str]
    status: JobStatus
    retry_count: int = 0
    created_by: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    logs: str = ""
    result_summary: Optional[str] = None


def _row_to_job(row: Any) -> ScanJob:
    data = dict(row)
    return ScanJob(
        id=data["id"],
        workspace_id=data.get("workspace_id"),
        scan_type=data["scan_type"],
        targets=json.loads(data["targets"] or "[]"),
        status=data["status"],
        retry_count=data.get("retry_count") or 0,
        created_by=data.get("created_by"),
        created_at=data["created_at"],
        started_at=data.get("started_at"),
        finished_at=data.get("finished_at"),
        logs=data.get("logs") or "",
        result_summary=data.get("result_summary"),
    )


class ScanJobRepository:
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
                CREATE TABLE IF NOT EXISTS scan_jobs (
                    id TEXT PRIMARY KEY,
                    workspace_id TEXT,
                    scan_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    targets TEXT,
                    status TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    logs TEXT,
                    result_summary TEXT
                )
                """
            )
            connection.commit()

    def create_job(self, payload: ScanJobCreate, created_by: str | None) -> ScanJob:
        job_id = str(uuid.uuid4())
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO scan_jobs (
                    id, workspace_id, scan_type, payload, scenario, targets, status,
                    created_by, created_at, logs
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    payload.workspace_id,
                    payload.scan_type,
                    json.dumps(payload.payload),
                    payload.scenario,
                    json.dumps(payload.targets),
                    "queued",
                    created_by,
                    created_at,
                    "queued\n",
                ),
            )
            connection.commit()
        return ScanJob(
            id=job_id, workspace_id=payload.workspace_id, scan_type=payload.scan_type,
            targets=payload.targets, status="queued", created_by=created_by,
            created_at=created_at, logs="queued\n",
        )

    def get_job(self, job_id: str) -> ScanJob | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM scan_jobs WHERE id = ?", (job_id,)).fetchone()
        return _row_to_job(row) if row else None

    def get_job_input(self, job_id: str) -> tuple[dict[str, Any], str] | None:
        """Returns (payload, scenario) for the worker to run -- not part of
        the public ScanJob model (the raw evidence payload isn't useful to
        expose via the status API, and could be large)."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload, scenario FROM scan_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            return None
        data = dict(row)
        return json.loads(data["payload"]), data["scenario"]

    def list_jobs(self, workspace_id: str | None = None) -> list[ScanJob]:
        query = "SELECT * FROM scan_jobs"
        params: tuple[Any, ...] = ()
        if workspace_id is not None:
            query += " WHERE workspace_id = ?"
            params = (workspace_id,)
        query += " ORDER BY created_at DESC"
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [_row_to_job(row) for row in rows]

    def _append_log(self, connection: Connection, job_id: str, line: str) -> None:
        row = connection.execute("SELECT logs FROM scan_jobs WHERE id = ?", (job_id,)).fetchone()
        existing = dict(row)["logs"] or "" if row else ""
        connection.execute(
            "UPDATE scan_jobs SET logs = ? WHERE id = ?", (existing + line + "\n", job_id)
        )

    def mark_running(self, job_id: str) -> bool:
        """Returns False (no-op) if the job isn't "queued" anymore -- e.g. it
        was cancelled before the worker got to it -- so the caller knows not
        to actually run the scan."""
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE scan_jobs SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
                (datetime.now(UTC).isoformat(), job_id),
            )
            started = cursor.rowcount == 1
            if started:
                self._append_log(connection, job_id, "running")
            connection.commit()
        return started

    def mark_finished(self, job_id: str, status: Literal["succeeded", "failed"], result_summary: str, log_line: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE scan_jobs SET status = ?, finished_at = ?, result_summary = ? WHERE id = ? AND status = 'running'",
                (status, datetime.now(UTC).isoformat(), result_summary, job_id),
            )
            self._append_log(connection, job_id, log_line)
            connection.commit()

    def claim_next_queued_job(self) -> ScanJob | None:
        """Atomically claims the oldest queued job for a worker to run --
        race-safe via mark_running's conditional UPDATE (WHERE status =
        'queued'), so multiple worker processes never double-process the
        same job. Returns None if nothing is queued."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM scan_jobs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 10"
            ).fetchall()
        for row in rows:
            job_id = dict(row)["id"]
            if self.mark_running(job_id):
                return self.get_job(job_id)
        return None

    def record_failure_and_maybe_retry(self, job_id: str, error_detail: str, max_retries: int) -> bool:
        """Returns True if the job was re-queued for another attempt, False
        if it was marked permanently 'failed' (retry_count exceeded
        max_retries)."""
        job = self.get_job(job_id)
        if job is None:
            return False
        new_retry_count = job.retry_count + 1
        with self._connect() as connection:
            if new_retry_count <= max_retries:
                connection.execute(
                    "UPDATE scan_jobs SET status = 'queued', retry_count = ?, started_at = NULL WHERE id = ? AND status = 'running'",
                    (new_retry_count, job_id),
                )
                self._append_log(connection, job_id, f"attempt {new_retry_count} failed: {error_detail} -- retrying")
                connection.commit()
                return True
            connection.execute(
                "UPDATE scan_jobs SET status = 'failed', retry_count = ?, finished_at = ?, result_summary = ? WHERE id = ? AND status = 'running'",
                (new_retry_count, datetime.now(UTC).isoformat(), error_detail, job_id),
            )
            self._append_log(connection, job_id, f"attempt {new_retry_count} failed: {error_detail} -- giving up after {max_retries} retries")
            connection.commit()
        return False

    def cancel_job(self, job_id: str) -> ScanJob | None:
        """Only succeeds while the job is still queued or running -- a
        terminal job (succeeded/failed/cancelled) can't be cancelled."""
        job = self.get_job(job_id)
        if job is None or job.status not in ("queued", "running"):
            return None
        with self._connect() as connection:
            connection.execute(
                "UPDATE scan_jobs SET status = 'cancelled', finished_at = ? WHERE id = ?",
                (datetime.now(UTC).isoformat(), job_id),
            )
            self._append_log(connection, job_id, "cancelled")
            connection.commit()
        return self.get_job(job_id)
