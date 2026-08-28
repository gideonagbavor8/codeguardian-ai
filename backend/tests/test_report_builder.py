"""
tests/test_report_builder.py
Unit tests for the release readiness score formula.
"""
from __future__ import annotations

import uuid
import pytest

from app.services.report_builder import build_report, _score_to_risk
from app.services.scanner.base import RawSecurityFinding, RawDependencyFinding
from app.services.ai.prompts import AIAnalysis


def make_finding(severity: str) -> RawSecurityFinding:
    return RawSecurityFinding(
        tool="bandit",
        rule_id="B001",
        severity=severity,
        confidence="HIGH",
        file_path="test.py",
        line_number=1,
        code_snippet="...",
        message="Test finding",
    )


def test_perfect_score_no_findings():
    report = build_report(
        scan_id=uuid.uuid4(),
        security_findings=[],
        dep_findings=[],
        ai_analysis=AIAnalysis(),
    )
    assert report.release_readiness_score == 100
    assert report.risk_level == "SAFE"


def test_critical_deduction():
    report = build_report(
        scan_id=uuid.uuid4(),
        security_findings=[make_finding("CRITICAL")],
        dep_findings=[],
        ai_analysis=AIAnalysis(),
    )
    assert report.release_readiness_score == 75  # 100 - 25
    assert report.risk_level == "LOW"


def test_high_deduction():
    # 10 HIGH findings → 100 - 100 = 0
    findings = [make_finding("HIGH") for _ in range(10)]
    report = build_report(
        scan_id=uuid.uuid4(),
        security_findings=findings,
        dep_findings=[],
        ai_analysis=AIAnalysis(),
    )
    assert report.release_readiness_score == 0
    assert report.risk_level == "CRITICAL"


def test_score_floor_at_zero():
    findings = [make_finding("CRITICAL") for _ in range(10)]
    report = build_report(
        scan_id=uuid.uuid4(),
        security_findings=findings,
        dep_findings=[],
        ai_analysis=AIAnalysis(),
    )
    assert report.release_readiness_score == 0


@pytest.mark.parametrize("score,expected", [
    (100, "SAFE"),
    (90,  "SAFE"),
    (89,  "LOW"),
    (70,  "LOW"),
    (69,  "MEDIUM"),
    (50,  "MEDIUM"),
    (49,  "HIGH"),
    (30,  "HIGH"),
    (29,  "CRITICAL"),
    (0,   "CRITICAL"),
])
def test_risk_thresholds(score: int, expected: str):
    assert _score_to_risk(score) == expected
