"""
app/main.py
FastAPI application factory.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.config import settings
from app.database import engine
from app.models import Base
from app.routers import auth, dashboard, reports, scans

logger = logging.getLogger(__name__)

# Set AUTO_CREATE_SCHEMA=false to disable the startup schema bootstrap.
AUTO_CREATE_SCHEMA = os.getenv("AUTO_CREATE_SCHEMA", "true").strip().lower() not in (
    "0", "false", "no", "off",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    Ensure the schema exists before serving traffic.

    Managed deploys (Render) start the app with a bare uvicorn command and
    never run `alembic upgrade head`, so the database connects but every table
    is missing and each query 500s.  create_all is idempotent — it creates only
    what is absent and is a no-op once the schema is present.  Alembic remains
    the source of truth for schema *changes*; this is bootstrap only.
    """
    if AUTO_CREATE_SCHEMA:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Schema check complete — all tables present.")
        except Exception as exc:
            # Keep serving so /health and /health/db stay reachable for triage.
            logger.error("Schema bootstrap failed: %s", exc, exc_info=True)
    yield


# ── App instance ──────────────────────────────────────────────
app = FastAPI(
    title="CodeGuardian AI",
    description="AI-powered code review and security analysis platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(auth.router,      prefix=API_PREFIX)
app.include_router(scans.router,     prefix=API_PREFIX)
app.include_router(reports.router,   prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)


# ── Health endpoints ──────────────────────────────────────────

@app.get("/health", tags=["health"], summary="Liveness check")
async def health() -> dict:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/health/db", tags=["health"], summary="Database connectivity check")
async def health_db() -> dict:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            # Report which tables exist: a connected database with no schema
            # is the difference between "works" and "500 on every request".
            tables = await conn.run_sync(
                lambda sync_conn: sorted(inspect(sync_conn).get_table_names())
            )
        expected = sorted(Base.metadata.tables.keys())
        missing = [t for t in expected if t not in tables]
        return {
            "status": "ok" if not missing else "error",
            "database": "connected",
            "tables": tables,
            "missing_tables": missing,
        }
    except Exception as exc:
        return {"status": "error", "database": str(exc)}


# ── Root redirect hint ────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"message": "CodeGuardian AI API — see /docs"}
