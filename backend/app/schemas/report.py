"""
app/schemas/report.py
Pydantic v2 schemas for reports and dashboard endpoints.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

class ReportResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    release_readiness_score: int
    risk_level: str
    ai_summary: str | None
    ai_fix_suggestions: list[dict[str, Any]] | None
    ai_review_narrative: str | None
    model_used: str | None
    # Flat counts — map directly to Report model columns
    total_security_issues: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    total_dep_issues: int
    generated_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard schemas ─────────────────────────────────────────

class DashboardStats(BaseModel):
    total_scans: int
    completed_scans: int
    average_score: float | None
    critical_findings: int
    recent_scans: list[dict]


class TrendPoint(BaseModel):
    date: str            # ISO date string YYYY-MM-DD
    score: int
    scan_id: uuid.UUID
    scan_name: str | None


class TrendResponse(BaseModel):
    points: list[TrendPoint]
