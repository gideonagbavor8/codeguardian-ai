"""
tests/conftest.py
Pytest fixtures for async FastAPI testing.

Uses SQLite in-memory (no postgres required).  PostgreSQL-specific column types
(JSONB, ARRAY) are replaced with SQLite-compatible equivalents at DDL time.
A custom TypeDecorator handles Python list ↔ JSON-string conversion for the
cve_ids ARRAY column so that INSERT/SELECT work correctly in SQLite.
"""
from __future__ import annotations

import asyncio
import json as _json
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import JSON, String, Text, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

from app.main import app
from app.database import get_db
from app.models.base import Base

# ── In-memory SQLite ──────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class _JsonListType(TypeDecorator):
    """
    Stores a Python list as a JSON string in SQLite.
    Transparently converts on read/write so ORM code sees a real list.
    """
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return _json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        try:
            return _json.loads(value)
        except (TypeError, ValueError):
            return value


def _patch_pg_types(metadata):
    """
    Walk every column in metadata and replace PostgreSQL-only types with
    SQLite-compatible equivalents so that create_all() and DML succeed in tests.
    """
    for table in metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = JSON()
            elif isinstance(col.type, ARRAY):
                # Use our list↔JSON decorator so Python lists round-trip correctly
                col.type = _JsonListType()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    # Patch PG-specific column types before creating tables
    _patch_pg_types(Base.metadata)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    SessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
