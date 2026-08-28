"""
app/routers/dashboard.py
GET /dashboard/stats  — aggregate stats for current user
GET /dashboard/trend  — score trend data for chart
"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import func, select

from app.dependencies import CurrentUser, DBDep
from app.models.report import Report
from app.models.scan import Scan, ScanStatus
from app.schemas.report import DashboardStats, TrendPoint, TrendResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/stats",
    response_model=DashboardStats,
    summary="Aggregate statistics for the current user",
)
async def get_stats(current_user: CurrentUser, db: DBDep) -> DashboardStats:
    # Total scans
    total_result = await db.execute(
        select(func.count(Scan.id)).where(Scan.user_id == current_user.id)
    )
    total_scans: int = total_result.scalar_one() or 0

    # Completed scans
    completed_result = await db.execute(
        select(func.count(Scan.id)).where(
            Scan.user_id == current_user.id,
            Scan.status == ScanStatus.COMPLETE.value,
        )
    )
    completed_scans: int = completed_result.scalar_one() or 0

    # Average score + critical / high counts (join scans → reports)
    agg_result = await db.execute(
        select(
            func.avg(Report.release_readiness_score),
            func.sum(Report.critical_count),
            func.sum(Report.high_count),
        )
        .join(Scan, Scan.id == Report.scan_id)
        .where(Scan.user_id == current_user.id)
    )
    avg_score_raw, critical_total, high_total = agg_result.one()

    return DashboardStats(
        total_scans=total_scans,
        completed_scans=completed_scans,
        average_score=round(float(avg_score_raw), 1) if avg_score_raw is not None else None,
        critical_issues_total=int(critical_total or 0),
        high_issues_total=int(high_total or 0),
    )


@router.get(
    "/trend",
    response_model=TrendResponse,
    summary="Score trend data for the past 30 completed scans",
)
async def get_trend(current_user: CurrentUser, db: DBDep) -> TrendResponse:
    result = await db.execute(
        select(
            Report.release_readiness_score,
            Scan.completed_at,
            Scan.id,
            Scan.name,
        )
        .join(Scan, Scan.id == Report.scan_id)
        .where(
            Scan.user_id == current_user.id,
            Scan.status == ScanStatus.COMPLETE.value,
        )
        .order_by(Scan.completed_at.asc())
        .limit(30)
    )
    rows = result.all()

    points = [
        TrendPoint(
            date=row.completed_at.date().isoformat() if row.completed_at else "",
            score=row.release_readiness_score,
            scan_id=row.id,
            scan_name=row.name,
        )
        for row in rows
    ]
    return TrendResponse(points=points)
