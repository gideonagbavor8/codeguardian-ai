"""
app/tasks/scan_pipeline.py
Full async scan orchestration task:
    extract → bandit scan → semgrep scan → dependency audit
           → AI analysis → report → persist
Status transitions: PENDING → RUNNING → COMPLETE | FAILED
"""
from __future__ import annotations

import logging
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
from app.services.scanner.semgrep_runner import run_semgrep
from app.services.scanner.base import RawDependencyFinding, RawSecurityFinding

logger = logging.getLogger(__name__)


async def run_scan_pipeline(scan_id: uuid.UUID, db: AsyncSession) -> None:
    """
    Entry point called via asyncio.create_task() from the scan router.
    All DB mutations happen inside this function.
    On any unhandled exception the scan is marked FAILED before returning.
    """
    # ── 1. Load scan from DB ──────────────────────────────────
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan: Scan | None = result.scalar_one_or_none()
    if scan is None:
        logger.error("Scan %s not found — aborting pipeline.", scan_id)
        return

    # ── 2. PENDING → RUNNING ──────────────────────────────────
    scan.status = ScanStatus.RUNNING.value
    await db.commit()
    logger.info("Scan %s: RUNNING", scan_id)

    try:
        meta: dict = scan.source_meta or {}
        code: str = meta.get("code", "")
        language: str = scan.language or "python"

        # ── 3. Bandit scan (Python only) ──────────────────────
        bandit_findings: list[RawSecurityFinding] = await run_bandit(code, language)
        logger.info(
            "Scan %s: bandit → %d finding(s)", scan_id, len(bandit_findings)
        )

        # ── 4. Semgrep scan (multi-language, optional) ────────
        semgrep_findings: list[RawSecurityFinding] = await run_semgrep(code, language)
        logger.info(
            "Scan %s: semgrep → %d finding(s)", scan_id, len(semgrep_findings)
        )

        # Merge; Bandit findings first so their indices align with AI suggestions
        raw_sec: list[RawSecurityFinding] = bandit_findings + semgrep_findings

        # ── 5. Dependency audit ───────────────────────────────
        dep_file: str = meta.get("dep_file_content", "")
        dep_ecosystem: str = meta.get("dep_ecosystem", "pip")
        raw_dep: list[RawDependencyFinding] = []
        if dep_file.strip():
            raw_dep = await audit_dependencies(dep_file, dep_ecosystem)
        logger.info(
            "Scan %s: dep-audit → %d finding(s)", scan_id, len(raw_dep)
        )

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

        await db.flush()  # assign IDs before AI call

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

        # ── 10. RUNNING → COMPLETE ────────────────────────────
        scan.status = ScanStatus.COMPLETE.value
        scan.completed_at = datetime.now(timezone.utc)
        await db.commit()
        logger.info(
            "Scan %s: COMPLETE — score=%d risk=%s",
            scan_id,
            report.release_readiness_score,
            report.risk_level,
        )

    except Exception as exc:
        logger.exception("Scan %s: pipeline FAILED — %s", scan_id, exc)
        # ── RUNNING → FAILED ──────────────────────────────────
        try:
            scan.status = ScanStatus.FAILED.value
            scan.error_message = str(exc)[:1000]
            scan.completed_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception:
            await db.rollback()
