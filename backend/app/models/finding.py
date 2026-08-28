"""
app/models/finding.py
SecurityFinding and DependencyFinding ORM models.
"""
from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, new_uuid


class SecurityFinding(Base, TimestampMixin):
    """One row per vulnerability detected by Bandit / Semgrep."""

    __tablename__ = "security_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool: Mapped[str] = mapped_column(String(50), nullable=False)          # bandit | semgrep
    rule_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)      # CRITICAL|HIGH|MEDIUM|LOW|INFO
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)  # HIGH|MEDIUM|LOW
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    line_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    cwe_id: Mapped[str | None] = mapped_column(String(20), nullable=True)  # e.g. CWE-89
    owasp_category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Relationships ──────────────────────────────────────────
    scan: Mapped["Scan"] = relationship("Scan", back_populates="security_findings")  # noqa: F821

    def __repr__(self) -> str:
        return f"<SecurityFinding id={self.id} severity={self.severity!r} rule={self.rule_id!r}>"


class DependencyFinding(Base, TimestampMixin):
    """One row per vulnerable package found by pip-audit / npm audit."""

    __tablename__ = "dependency_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=new_uuid,
    )
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    package_name: Mapped[str] = mapped_column(String(255), nullable=False)
    installed_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fixed_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    cve_ids: Mapped[List[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    ecosystem: Mapped[str] = mapped_column(String(20), nullable=False)     # pip | npm | cargo | gem

    # ── Relationships ──────────────────────────────────────────
    scan: Mapped["Scan"] = relationship("Scan", back_populates="dependency_findings")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<DependencyFinding id={self.id} "
            f"package={self.package_name!r} severity={self.severity!r}>"
        )
