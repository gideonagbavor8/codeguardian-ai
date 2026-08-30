from __future__ import annotations

from typing import Any, AsyncGenerator

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# libpq/psycopg2 connection parameters that asyncpg does not accept.  SQLAlchemy
# forwards a URL's query string straight to the driver's connect(), so leaving
# these in raises e.g.
#     connect() got an unexpected keyword argument 'sslmode'
# which surfaces as a 500 on every database-backed request.
_LIBPQ_ONLY_PARAMS = (
    "sslmode", "sslrootcert", "sslcert", "sslkey", "sslpassword",
    "channel_binding", "target_session_attrs", "gssencmode",
)


def normalise_db_url(raw: str) -> tuple[str, dict[str, Any]]:
    """
    Make a managed-Postgres URL usable with the asyncpg driver.

    Managed providers (Render, Heroku, Supabase, …) hand out libpq-style URLs
    such as postgres://user:pw@host/db?sslmode=require.  Two things need
    fixing for asyncpg:

    1. the postgres:// / postgresql:// scheme has no async driver, and
    2. libpq-only query parameters must be removed, with sslmode translated
       into asyncpg's own `ssl` connect argument (asyncpg accepts libpq's
       sslmode names there).

    Returns (url, connect_args) ready for create_async_engine().
    """
    url = make_url(raw)
    connect_args: dict[str, Any] = {}

    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+asyncpg")

    if url.drivername.startswith("postgresql+asyncpg"):
        query = dict(url.query)
        sslmode = query.pop("sslmode", None)
        for param in _LIBPQ_ONLY_PARAMS:
            query.pop(param, None)
        if sslmode:
            # asyncpg understands "require", "verify-full", "disable", etc.
            connect_args["ssl"] = sslmode[0] if isinstance(sslmode, tuple) else sslmode
        url = url.set(query=query)

    return url.render_as_string(hide_password=False), connect_args


DATABASE_URL, CONNECT_ARGS = normalise_db_url(settings.DATABASE_URL)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args=CONNECT_ARGS,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
