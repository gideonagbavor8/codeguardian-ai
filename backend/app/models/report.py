"""
app/models/report.py
Report ORM model — aggregated scan output including AI narrative.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, new_uuid


class Report(Base):
    """Aggregated report: one per scan (1:1)."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # ── Readiness score ───────────────────────────────────────
    release_readiness_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)

    # ── Finding counts ────────────────────────────────────────
    total_security_issues: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    critical_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    medium_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_dep_issues: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── AI output ─────────────────────────────────────────────
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_fix_suggestions: Mapped[list | None] = mapped_column(
        JSONB, nullable=True
    )  # [{finding_id, suggestion}, ...]
    ai_review_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────
    scan: Mapped["Scan"] = relationship("Scan", back_populates="report")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<Report id={self.id} scan_id={self.scan_id} "
            f"score={self.release_readiness_score} risk={self.risk_level!r}>"
        )
