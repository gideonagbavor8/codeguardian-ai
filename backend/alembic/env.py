"""
alembic/env.py
Async Alembic environment — reads DATABASE_URL from .env via app.config.
"""
from __future__ import annotations

import asyncio
import sys
import os
from logging.config import fileConfig

# Ensure the backend/ directory (parent of this alembic/ folder) is on sys.path
# so that `import app.*` works when alembic is invoked from backend/.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

# Import all models so Alembic can detect them via Base.metadata
from app.models import Base  # noqa: F401 — registers all ORM classes
from app.config import settings
from app.database import normalise_db_url

# Alembic Config object
config = context.config

# Override sqlalchemy.url with the value from settings (reads .env).
# Managed-Postgres URLs carry libpq-only parameters such as ?sslmode=require
# that asyncpg rejects, so normalise them the same way the app engine does.
_DB_URL, _CONNECT_ARGS = normalise_db_url(settings.DATABASE_URL)
config.set_main_option("sqlalchemy.url", _DB_URL)

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations without a live DB connection (SQL script output)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
        connect_args=_CONNECT_ARGS,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
