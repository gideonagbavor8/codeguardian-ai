"""
app/main.py
FastAPI application factory.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routers import auth, dashboard, reports, scans

# ── App instance ──────────────────────────────────────────────
app = FastAPI(
    title="CodeGuardian AI",
    description="AI-powered code review and security analysis platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
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
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "database": str(exc)}


# ── Root redirect hint ────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {"message": "CodeGuardian AI API — see /docs"}
