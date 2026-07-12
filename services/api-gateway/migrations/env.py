"""Alembic environment for api-gateway's PostgreSQL schema only.

SQLite (bare-metal dev/tests/CI) keeps its existing implicit-create-on-first-use
pattern in auth.py -- this migration history exists purely for the
DATABASE_URL/Postgres path (see docs/adr/0001-product-v1-architecture.md).
Reads DATABASE_URL from the environment, the same variable the app itself
reads, so there's exactly one place a deployment configures its connection
string.

version_table is set to a service-specific name (not Alembic's default
"alembic_version") because api-gateway, inventory-service, and
workflow-service share one physical Postgres database (see
infra/docker/README.md) -- independent migration histories in the same
database would collide on the default table name otherwise.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Alembic migrations only apply to the PostgreSQL "
            "path -- set DATABASE_URL to a postgresql:// connection string before running "
            "'alembic upgrade head'. SQLite deployments do not use these migrations."
        )
    # SQLAlchemy's bare "postgresql://" scheme defaults to the psycopg2 driver;
    # this project uses psycopg (v3) everywhere else -- normalize explicitly so
    # the same DATABASE_URL value the app reads works here unchanged.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="alembic_version_gateway",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version_gateway",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
