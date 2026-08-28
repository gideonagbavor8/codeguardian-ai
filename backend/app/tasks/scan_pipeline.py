"""
app/tasks/scan_pipeline.py
Full async scan orchestration task:
    extract → security scan → dependency audit → AI analysis → report → persist
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.finding import DependencyFinding, SecurityFinding
from app.models.scan import Scan, ScanStatus, SourceType
from app.services.ai.watsonx_client import generate_analysis
from app.services.report_builder import build_report
from app.services.scanner.bandit_runner import run_bandit
from app.services.scanner.dep_auditor import audit_dependencies
from app.services.scanner.base import RawSecurityFinding, RawDependencyFinding

logger = logging.getLogger(__name__)


async def run_scan_pipeline(scan_id: uuid.UUID, db: AsyncSession) -> None:
    """
    Entry point called via asyncio.create_task() from the scan router.
    All DB mutations happen inside this function.
    """
    # ── 1. Load scan from DB ──────────────────────────────────
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan: Scan | None = result.scalar_one_or_none()
    if scan is None:
        logger.error("Scan %s not found — aborting pipeline.", scan_id)
        return

    # ── 2. Mark RUNNING ───────────────────────────────────────
    scan.status = ScanStatus.RUNNING.value
    await db.commit()

    try:
        meta: dict = scan.source_meta or {}

        # ── 3. Read source code ───────────────────────────────
        code = meta.get("code", "")
        language = scan.language or "python"

        # ── 4. Security scan ─────────────────────────────────
        raw_sec: list[RawSecurityFinding] = await run_bandit(code, language)

        # ── 5. Dependency audit ───────────────────────────────
        dep_file = meta.get("dep_file_content", "")
        dep_ecosystem = meta.get("dep_ecosystem", "pip")
        raw_dep: list[RawDependencyFinding] = []
        if dep_file:
            raw_dep = await audit_dependencies(dep_file, dep_ecosystem)

        # ── 6. Persist SecurityFinding rows ───────────────────
        for raw in raw_sec:
            db.add(
                SecurityFinding(
                    scan_id=scan_id,
                    tool=raw.tool,
                    rule_id=raw.rule_id,
                    severity=raw.severity,
                    confidence=raw.confidence,
                    file_path=raw.file_path,
                    line_number=raw.line_number,
                    code_snippet=raw.code_snippet,
                    message=raw.message,
                    cwe_id=raw.cwe_id,
                    owasp_category=raw.owasp_category,
                )
            )

        # ── 7. Persist DependencyFinding rows ─────────────────
        for raw in raw_dep:
            db.add(
                DependencyFinding(
                    scan_id=scan_id,
                    package_name=raw.package_name,
                    installed_version=raw.installed_version,
                    fixed_version=raw.fixed_version,
                    severity=raw.severity,
                    cve_ids=raw.cve_ids or [],
                    description=raw.description,
                    ecosystem=raw.ecosystem,
                )
            )

        await db.flush()  # assign IDs before passing to AI

        # ── 8. AI analysis ────────────────────────────────────
        ai_analysis = await generate_analysis(raw_sec, raw_dep)

        # ── 9. Build and persist Report ───────────────────────
        report = build_report(
            scan_id=scan_id,
            security_findings=raw_sec,
            dep_findings=raw_dep,
            ai_analysis=ai_analysis,
            model_used=settings.WATSONX_MODEL_ID,
        )
        db.add(report)

        # ── 10. Mark COMPLETE ─────────────────────────────────
        scan.status = ScanStatus.COMPLETE.value
        scan.completed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info("Scan %s completed. Score=%d", scan_id, report.release_readiness_score)

    except Exception as exc:
        logger.exception("Scan pipeline failed for scan_id=%s: %s", scan_id, exc)
        try:
            scan.status = ScanStatus.FAILED.value
            scan.error_message = str(exc)[:1000]
            scan.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception:
            await db.rollback()
