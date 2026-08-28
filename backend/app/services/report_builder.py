"""
app/services/report_builder.py
Aggregates scanner output into a Report ORM object.
Implements the Release Readiness Score formula from ARCHITECTURE.md §5.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.report import Report
from app.services.ai.prompts import AIAnalysis
from app.services.scanner.base import RawDependencyFinding, RawSecurityFinding

# ── Score deduction weights ────────────────────────────────────
_SEC_WEIGHTS = {
    "CRITICAL": 25,
    "HIGH": 10,
    "MEDIUM": 5,
    "LOW": 1,
    "INFO": 0,
}

_DEP_WEIGHTS = {
    "CRITICAL": 20,
    "HIGH": 8,
    "MEDIUM": 3,
    "LOW": 1,
    "INFO": 0,
}

# ── Risk level thresholds ─────────────────────────────────────
def _score_to_risk(score: int) -> str:
    if score >= 90:
        return "SAFE"
    if score >= 70:
        return "LOW"
    if score >= 50:
        return "MEDIUM"
    if score >= 30:
        return "HIGH"
    return "CRITICAL"


def build_report(
    scan_id: uuid.UUID,
    security_findings: list[RawSecurityFinding],
    dep_findings: list[RawDependencyFinding],
    ai_analysis: AIAnalysis,
    model_used: str | None = None,
) -> Report:
    """
    Compute the release readiness score and return an unsaved Report ORM instance.
    The caller is responsible for adding it to the DB session and committing.
    """
    # ── Count security findings by severity ───────────────────
    counts: dict[str, int] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
    for f in security_findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1

    # ── Compute score ─────────────────────────────────────────
    score = 100
    for sev, weight in _SEC_WEIGHTS.items():
        score -= counts.get(sev, 0) * weight

    for dep in dep_findings:
        score -= _DEP_WEIGHTS.get(dep.severity, 0)

    score = max(0, score)

    # ── Build ai_fix_suggestions keyed by finding index ───────
    fix_suggestions: list[dict[str, Any]] = ai_analysis.fix_suggestions

    return Report(
        scan_id=scan_id,
        release_readiness_score=score,
        risk_level=_score_to_risk(score),
        total_security_issues=len(security_findings),
        critical_count=counts.get("CRITICAL", 0),
        high_count=counts.get("HIGH", 0),
        medium_count=counts.get("MEDIUM", 0),
        low_count=counts.get("LOW", 0),
        total_dep_issues=len(dep_findings),
        ai_summary=ai_analysis.summary or None,
        ai_fix_suggestions=fix_suggestions or None,
        ai_review_narrative=ai_analysis.narrative or None,
        model_used=model_used,
    )
