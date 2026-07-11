"""Thin SQLite/PostgreSQL compatibility layer shared by inventory-service and
workflow-service's repositories. SQLite remains the default everywhere (bare-metal
dev, tests, CI); Postgres is used only when a caller passes a postgres:// /
postgresql:// connection string (currently: docker-compose's DATABASE_URL) -- see
infra/docker/README.md.

Both repositories already write `?`-style placeholders and expect dict-like rows
(sqlite3.Row); this module lets that code run unchanged against either backend by
translating placeholders and normalizing row/connection behavior, rather than
introducing an ORM or duplicating every query.
"""

from __future__ import annotations

import sqlite3
from typing import Any


def is_postgres_target(target: str) -> bool:
    return target.startswith("postgres://") or target.startswith("postgresql://")


class Connection:
    """Wraps a raw sqlite3 or psycopg connection behind one interface:
    `?`-placeholder `.execute()`, dict-like rows, and commit-on-clean-exit /
    rollback-on-exception context manager semantics (matching sqlite3's own
    behavior) -- deliberately does NOT close the underlying connection on
    __exit__, since existing repository code reuses `with self._connect() as
    connection:` per call and relies on the process/GC to close it, same as
    today's plain sqlite3 usage."""

    def __init__(self, raw: Any, is_postgres: bool) -> None:
        self._raw = raw
        self.is_postgres = is_postgres

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> Any:
        if self.is_postgres:
            query = query.replace("?", "%s")
        return self._raw.execute(query, params)

    def commit(self) -> None:
        self._raw.commit()

    def __enter__(self) -> "Connection":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        if exc_type is None:
            self._raw.commit()
        else:
            self._raw.rollback()
        return False


def connect(target: str) -> Connection:
    if is_postgres_target(target):
        import psycopg
        from psycopg.rows import dict_row

        raw = psycopg.connect(target, row_factory=dict_row)
        return Connection(raw, is_postgres=True)

    raw = sqlite3.connect(target)
    raw.row_factory = sqlite3.Row
    return Connection(raw, is_postgres=False)


def existing_columns(connection: Connection, table: str) -> set[str]:
    """Column names currently on `table`, for the ALTER-TABLE-ADD-COLUMN-if-missing
    pattern both repositories use to evolve their schema in place."""
    if connection.is_postgres:
        rows = connection.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = ?",
            (table,),
        ).fetchall()
        return {row["column_name"] for row in rows}

    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}
