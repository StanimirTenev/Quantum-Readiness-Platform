from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from .models import ApprovalRecord, Task, TaskCreate

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "workflow.db"


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
                    status TEXT NOT NULL
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
            connection.commit()

    def create_task(self, payload: TaskCreate) -> Task:
        task_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    id, title, asset_name, wave, priority, description, recommended_action, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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

    def update_task_status(self, task_id: str, status: str) -> Task | None:
        if self.get_task(task_id) is None:
            return None
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
