from __future__ import annotations

import os
import sqlite3
import uuid
from pathlib import Path

from .models import ApprovalRecord, Task, TaskCreate

# WORKFLOW_DB_PATH lets a caller (e.g. an isolated test run, or a persistent volume
# mount) point the store at a specific database file -- mirrors inventory-service's
# INVENTORY_DB_PATH convention.
DEFAULT_DB_PATH = Path(os.getenv("WORKFLOW_DB_PATH") or (Path(__file__).resolve().parent.parent / "workflow.db"))


class WorkflowRepository:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = str(db_path)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    asset_name TEXT NOT NULL,
                    wave TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    description TEXT NOT NULL,
                    recommended_action TEXT,
                    status TEXT NOT NULL,
                    requested_by TEXT NOT NULL DEFAULT 'unknown'
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    approver TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    note TEXT
                )
                """
            )
            self._ensure_task_columns(connection)
            connection.commit()

    @staticmethod
    def _ensure_task_columns(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }
        if "requested_by" not in columns:
            connection.execute(
                "ALTER TABLE tasks ADD COLUMN requested_by TEXT NOT NULL DEFAULT 'unknown'"
            )

    def _find_existing_task(self, payload: TaskCreate) -> Task | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM tasks
                WHERE asset_name = ? AND wave = ? AND recommended_action IS ?
                ORDER BY rowid DESC
                LIMIT 1
                """,
                (payload.asset_name, payload.wave, payload.recommended_action),
            ).fetchone()
        return Task(**dict(row)) if row else None

    def create_task(self, payload: TaskCreate) -> Task:
        existing = self._find_existing_task(payload)
        if existing is not None:
            return existing

        task_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    id, title, asset_name, wave, priority, description, recommended_action, status, requested_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    payload.title,
                    payload.asset_name,
                    payload.wave,
                    payload.priority,
                    payload.description,
                    payload.recommended_action,
                    "draft",
                    payload.requested_by,
                ),
            )
            connection.commit()
        task = self.get_task(task_id)
        assert task is not None
        return task

    def list_tasks(self) -> list[Task]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM tasks ORDER BY rowid DESC").fetchall()
        return [Task(**dict(row)) for row in rows]

    def get_task(self, task_id: str) -> Task | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return Task(**dict(row)) if row else None

    def _is_valid_status_transition(self, from_status: str, to_status: str) -> bool:
        allowed_transitions: dict[str, set[str]] = {
            "draft": {"pending_approval"},
            "pending_approval": {"approved", "rejected"},
            "approved": {"in_progress"},
            "rejected": {"draft"},
            "in_progress": {"completed"},
            "completed": set(),
        }
        return to_status in allowed_transitions.get(from_status, set())

    def update_task_status(self, task_id: str, status: str) -> Task | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        if not self._is_valid_status_transition(task.status, status):
            raise ValueError(f"Invalid task status transition: {task.status} -> {status}")
        with self._connect() as connection:
            connection.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
            connection.commit()
        return self.get_task(task_id)

    def create_approval(self, task_id: str, approver: str, decision: str, note: str | None) -> ApprovalRecord | None:
        task = self.get_task(task_id)
        if task is None:
            return None
        if task.status != "pending_approval":
            raise ValueError("Task must be in pending_approval status before an approval decision")
        if approver == task.requested_by:
            raise ValueError("Approver must not be the same person who requested the task (segregation of duties)")

        approval_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO approvals (id, task_id, approver, decision, note)
                VALUES (?, ?, ?, ?, ?)
                """,
                (approval_id, task_id, approver, decision, note),
            )
            connection.commit()

        new_status = "approved" if decision == "approved" else "rejected"
        self.update_task_status(task_id, new_status)

        return ApprovalRecord(task_id=task_id, approver=approver, decision=decision, note=note)

    def list_approvals(self, task_id: str | None = None) -> list[ApprovalRecord]:
        query = "SELECT task_id, approver, decision, note FROM approvals"
        params: tuple = ()
        if task_id:
            query += " WHERE task_id = ?"
            params = (task_id,)
        query += " ORDER BY rowid DESC"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [ApprovalRecord(**dict(row)) for row in rows]

    def cleanup_duplicate_tasks(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, asset_name, wave, COALESCE(recommended_action, '') AS recommended_action, rowid
                FROM tasks
                ORDER BY rowid DESC
                """
            ).fetchall()

            seen: set[tuple[str, str, str]] = set()
            delete_ids: list[str] = []

            for row in rows:
                key = (row["asset_name"], row["wave"], row["recommended_action"])
                if key in seen:
                    delete_ids.append(row["id"])
                else:
                    seen.add(key)

            deleted_approvals = 0
            deleted_tasks = 0

            for task_id in delete_ids:
                cur1 = connection.execute("DELETE FROM approvals WHERE task_id = ?", (task_id,))
                cur2 = connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                deleted_approvals += cur1.rowcount
                deleted_tasks += cur2.rowcount

            connection.commit()

        return {
            "deleted_tasks": deleted_tasks,
            "deleted_approvals": deleted_approvals,
        }
