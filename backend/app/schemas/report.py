"""
app/schemas/report.py
Pydantic v2 schemas for reports and dashboard endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.finding import DependencyFindingOut, SecurityFindingOut


class FindingsSummary(BaseModel):
    security: list[SecurityFindingOut]
    dependencies: list[DependencyFindingOut]


class CountsSummary(BaseModel):
    critical: int
    high: int
    medium: int
    low: int
    total_security: int
    total_dependencies: int


class ReportResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    release_readiness_score: int
    risk_level: str
    ai_summary: str | None
    ai_fix_suggestions: list[dict[str, Any]] | None
    ai_review_narrative: str | None
    model_used: str | None
    findings: FindingsSummary
    counts: CountsSummary
    generated_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard schemas ─────────────────────────────────────────

class DashboardStats(BaseModel):
    total_scans: int
    completed_scans: int
    average_score: float | None
    critical_issues_total: int
    high_issues_total: int


class TrendPoint(BaseModel):
    date: str            # ISO date string YYYY-MM-DD
    score: int
    scan_id: uuid.UUID
    scan_name: str | None


class TrendResponse(BaseModel):
    points: list[TrendPoint]
