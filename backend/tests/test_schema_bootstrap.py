"""
tests/test_schema_bootstrap.py
The deployed app connects to Postgres but was started with a bare uvicorn
command, so no migration ever ran and every query hit a missing table.
These tests cover the startup schema bootstrap and the /health/db diagnostic
that makes that state visible.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app import main
from app.models import Base


def _sqlite_engine(tmp_path, name: str):
    # test_engine (session fixture) has already replaced JSONB/ARRAY columns
    # with SQLite-compatible types on Base.metadata.
    return create_async_engine(f"sqlite+aiosqlite:///{tmp_path / name}")


async def _table_names(engine) -> list[str]:
    async with engine.connect() as conn:
        return await conn.run_sync(
            lambda sync_conn: sorted(inspect(sync_conn).get_table_names())
        )


@pytest.mark.asyncio
async def test_lifespan_creates_missing_tables(test_engine, tmp_path):
    """An empty database gets the full schema on startup."""
    engine = _sqlite_engine(tmp_path, "boot.db")
    try:
        assert await _table_names(engine) == []      # nothing there yet

        with patch.object(main, "engine", engine):
            async with main.lifespan(main.app):
                pass

        created = await _table_names(engine)
        for expected in ("users", "scans", "security_findings",
                         "dependency_findings", "reports"):
            assert expected in created, created
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lifespan_is_idempotent(test_engine, tmp_path):
    """Running twice is a no-op — safe on every container restart."""
    engine = _sqlite_engine(tmp_path, "idem.db")
    try:
        with patch.object(main, "engine", engine):
            async with main.lifespan(main.app):
                pass
            first = await _table_names(engine)
            async with main.lifespan(main.app):
                pass
            second = await _table_names(engine)
        assert first == second and first
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lifespan_skipped_when_disabled(test_engine, tmp_path):
    """AUTO_CREATE_SCHEMA=False leaves the database untouched."""
    engine = _sqlite_engine(tmp_path, "disabled.db")
    try:
        with patch.object(main, "engine", engine), \
             patch.object(main, "AUTO_CREATE_SCHEMA", False):
            async with main.lifespan(main.app):
                pass
        assert await _table_names(engine) == []
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_lifespan_survives_bootstrap_failure(test_engine):
    """A failed bootstrap must not stop the app — /health must stay reachable."""
    broken = create_async_engine("postgresql+asyncpg://u:p@127.0.0.1:1/nope")
    try:
        with patch.object(main, "engine", broken):
            async with main.lifespan(main.app):
                pass          # must not raise
    finally:
        await broken.dispose()


@pytest.mark.asyncio
async def test_health_db_reports_missing_tables(test_engine, tmp_path):
    """A connected database with no schema reports status=error, not ok."""
    engine = _sqlite_engine(tmp_path, "empty.db")
    try:
        with patch.object(main, "engine", engine):
            result = await main.health_db()
        assert result["database"] == "connected"
        assert result["status"] == "error"
        assert "users" in result["missing_tables"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_health_db_reports_ok_once_schema_exists(test_engine, tmp_path):
    """After bootstrap, nothing is missing and status flips to ok."""
    engine = _sqlite_engine(tmp_path, "full.db")
    try:
        with patch.object(main, "engine", engine):
            async with main.lifespan(main.app):
                pass
            result = await main.health_db()
        assert result["status"] == "ok"
        assert result["missing_tables"] == []
        assert "users" in result["tables"]
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_health_db_reports_connection_error(test_engine):
    """An unreachable database still returns a JSON body, not a 500."""
    broken = create_async_engine("postgresql+asyncpg://u:p@127.0.0.1:1/nope")
    try:
        with patch.object(main, "engine", broken):
            result = await main.health_db()
        assert result["status"] == "error"
        assert "connected" not in result.get("database", "")
    finally:
        await broken.dispose()
