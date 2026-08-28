"""
app/models/scan.py
Scan job ORM model + ScanStatus / SourceType enums.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class ScanStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class SourceType(str, enum.Enum):
    SNIPPET = "SNIPPET"
    UPLOAD = "UPLOAD"
    GITHUB = "GITHUB"


class Scan(Base, TimestampMixin):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ScanStatus.PENDING.value,
        server_default=text("'PENDING'"),
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Flexible JSON payload: filename, repo_url, tmp_path, language hint, etc.
    source_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Relationships ──────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="scans")  # noqa: F821
    security_findings: Mapped[list["SecurityFinding"]] = relationship(  # noqa: F821
        "SecurityFinding",
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    dependency_findings: Mapped[list["DependencyFinding"]] = relationship(  # noqa: F821
        "DependencyFinding",
        back_populates="scan",
        cascade="all, delete-orphan",
    )
    report: Mapped["Report | None"] = relationship(  # noqa: F821
        "Report",
        back_populates="scan",
        cascade="all, delete-orphan",
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<Scan id={self.id} status={self.status!r}>"
