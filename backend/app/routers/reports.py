"""
app/routers/reports.py
GET /reports/{scan_id}          — full report
GET /reports/{scan_id}/findings — paginated findings
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import CurrentUser, DBDep
from app.models.report import Report
from app.models.scan import Scan
from app.models.finding import SecurityFinding, DependencyFinding
from app.schemas.finding import DependencyFindingOut, SecurityFindingOut
from app.schemas.report import (
    CountsSummary,
    FindingsSummary,
    ReportResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])


async def _get_scan_and_report(
    scan_id: uuid.UUID, user_id: uuid.UUID, db: Any
) -> tuple[Scan, Report]:
    """Shared helper — validates ownership and returns scan + report."""
    scan_result = await db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.user_id == user_id)
    )
    scan = scan_result.scalar_one_or_none()
    if scan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")

    report_result = await db.execute(
        select(Report).where(Report.scan_id == scan_id)
    )
    report = report_result.scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not ready yet. Poll /scans/{id}/status first.",
        )
    return scan, report


@router.get(
    "/{scan_id}",
    response_model=ReportResponse,
    summary="Get the full report for a completed scan",
)
async def get_report(
    scan_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
) -> ReportResponse:
    _scan, report = await _get_scan_and_report(scan_id, current_user.id, db)

    # Load findings
    sec_result = await db.execute(
        select(SecurityFinding).where(SecurityFinding.scan_id == scan_id)
    )
    sec_findings = sec_result.scalars().all()

    dep_result = await db.execute(
        select(DependencyFinding).where(DependencyFinding.scan_id == scan_id)
    )
    dep_findings = dep_result.scalars().all()

    # Enrich security findings with AI fix suggestions
    fix_map: dict[int, str] = {}
    if report.ai_fix_suggestions:
        for item in report.ai_fix_suggestions:
            fix_map[item.get("index", -1)] = item.get("suggestion", "")

    sec_out = []
    for i, f in enumerate(sec_findings):
        out = SecurityFindingOut.model_validate(f)
        out.ai_fix = fix_map.get(i)
        sec_out.append(out)

    dep_out = [DependencyFindingOut.model_validate(d) for d in dep_findings]

    return ReportResponse(
        id=report.id,
        scan_id=report.scan_id,
        release_readiness_score=report.release_readiness_score,
        risk_level=report.risk_level,
        ai_summary=report.ai_summary,
        ai_fix_suggestions=report.ai_fix_suggestions,
        ai_review_narrative=report.ai_review_narrative,
        model_used=report.model_used,
        findings=FindingsSummary(security=sec_out, dependencies=dep_out),
        counts=CountsSummary(
            critical=report.critical_count,
            high=report.high_count,
            medium=report.medium_count,
            low=report.low_count,
            total_security=report.total_security_issues,
            total_dependencies=report.total_dep_issues,
        ),
        generated_at=report.generated_at,
    )


@router.get(
    "/{scan_id}/findings",
    summary="Get paginated findings for a scan",
)
async def get_findings(
    scan_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBDep,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict:
    # Ownership check
    scan_result = await db.execute(
        select(Scan).where(Scan.id == scan_id, Scan.user_id == current_user.id)
    )
    if scan_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found.")

    offset = (page - 1) * limit

    sec_result = await db.execute(
        select(SecurityFinding)
        .where(SecurityFinding.scan_id == scan_id)
        .offset(offset)
        .limit(limit)
    )
    dep_result = await db.execute(
        select(DependencyFinding)
        .where(DependencyFinding.scan_id == scan_id)
        .offset(offset)
        .limit(limit)
    )

    return {
        "security": [SecurityFindingOut.model_validate(f) for f in sec_result.scalars()],
        "dependencies": [DependencyFindingOut.model_validate(d) for d in dep_result.scalars()],
        "page": page,
        "limit": limit,
    }
