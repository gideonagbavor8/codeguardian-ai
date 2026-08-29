"""
tests/test_pipeline.py
Unit and integration tests for the scanning pipeline.

All scanner subprocess calls are mocked — no real bandit, semgrep, or
pip-audit binaries are required for these tests.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.models.scan import Scan, ScanStatus, SourceType
from app.models.finding import SecurityFinding, DependencyFinding
from app.models.report import Report
from app.services.scanner.base import (
    RawDependencyFinding,
    RawSecurityFinding,
    normalise_severity,
)
from app.services.scanner.semgrep_runner import _semgrep_severity, semgrep_available
from app.services.scanner.dep_auditor import _severity_from_aliases
from app.services.ai.prompts import AIAnalysis
from app.tasks.scan_pipeline import run_scan_pipeline


# ── Helpers ───────────────────────────────────────────────────

def _make_sec(severity: str = "HIGH", tool: str = "bandit") -> RawSecurityFinding:
    return RawSecurityFinding(
        tool=tool,
        rule_id="B001",
        severity=severity,
        confidence="HIGH",
        file_path="test.py",
        line_number=1,
        code_snippet="bad_code()",
        message="Test finding",
        cwe_id="CWE-89",
    )


def _make_dep(severity: str = "HIGH") -> RawDependencyFinding:
    return RawDependencyFinding(
        package_name="requests",
        installed_version="2.25.0",
        fixed_version="2.31.0",
        severity=severity,
        cve_ids=["CVE-2023-32681"],
        description="Proxy credential leak",
        ecosystem="pip",
    )


BANDIT_HIGH_JSON = json.dumps({
    "results": [
        {
            "test_id": "B301",
            "issue_severity": "HIGH",
            "issue_confidence": "HIGH",
            "filename": "/tmp/snippet.py",
            "line_number": 2,
            "code": "pickle.loads(data)",
            "issue_text": "Pickle deserialisation is unsafe",
            "issue_cwe": {"id": 502, "link": "https://cwe.mitre.org/data/definitions/502.html"},
        }
    ],
    "errors": [],
})

SEMGREP_WARNING_JSON = json.dumps({
    "results": [
        {
            "check_id": "python.lang.security.audit.eval-detected",
            "path": "/tmp/snippet.py",
            "start": {"line": 5},
            "extra": {
                "severity": "WARNING",
                "message": "Use of eval() is dangerous",
                "lines": "eval(user_input)",
                "metadata": {
                    "cwe": ["CWE-78"],
                    "owasp": ["A1:2017-Injection"],
                },
            },
        }
    ],
    "errors": [],
})

PIPAUDIT_JSON = json.dumps({
    "dependencies": [
        {
            "name": "requests",
            "version": "2.25.0",
            "vulns": [
                {
                    "id": "PYSEC-2023-74",
                    "aliases": ["CVE-2023-32681", "GHSA-j8r2-6x86-q33q"],
                    "fix_versions": ["2.31.0"],
                    "description": "Proxy credential leak",
                }
            ],
        }
    ]
})


# ─────────────────────────────────────────────────────────────
# 1. Severity normalisation
# ─────────────────────────────────────────────────────────────

class TestNormaliseSeverity:
    def test_canonical_values(self):
        for v in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            assert normalise_severity(v.lower()) == v

    def test_moderate_maps_to_medium(self):
        assert normalise_severity("moderate") == "MEDIUM"

    def test_unknown_maps_to_info(self):
        assert normalise_severity("unknown_level") == "INFO"

    def test_case_insensitive(self):
        assert normalise_severity("HIGH") == "HIGH"
        assert normalise_severity("high") == "HIGH"


class TestSemgrepSeverity:
    def test_error_maps_to_high(self):
        assert _semgrep_severity("ERROR") == "HIGH"

    def test_warning_maps_to_medium(self):
        assert _semgrep_severity("WARNING") == "MEDIUM"

    def test_info_stays_info(self):
        assert _semgrep_severity("INFO") == "INFO"

    def test_unknown_falls_back_to_info(self):
        assert _semgrep_severity("UNKNOWN") == "INFO"


class TestDepAuditorSeverity:
    def test_empty_aliases_gives_low(self):
        assert _severity_from_aliases([]) == "LOW"

    def test_aliases_present_gives_medium(self):
        assert _severity_from_aliases(["CVE-2023-0001"]) == "MEDIUM"


# ─────────────────────────────────────────────────────────────
# 2. Bandit runner (subprocess mocked)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_bandit_returns_findings_for_python():
    from app.services.scanner.bandit_runner import run_bandit

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(BANDIT_HIGH_JSON.encode(), b""))

    with patch("app.services.scanner.bandit_runner.asyncio.create_subprocess_exec",
               return_value=mock_proc):
        findings = await run_bandit("import pickle\npickle.loads(data)", "python")

    assert len(findings) == 1
    f = findings[0]
    assert f.tool == "bandit"
    assert f.severity == "HIGH"
    assert f.rule_id == "B301"
    assert f.cwe_id == "CWE-502"
    assert f.line_number == 2


@pytest.mark.asyncio
async def test_bandit_skips_non_python():
    from app.services.scanner.bandit_runner import run_bandit

    findings = await run_bandit("const x = 1;", "javascript")
    assert findings == []


@pytest.mark.asyncio
async def test_bandit_returns_empty_on_no_output():
    from app.services.scanner.bandit_runner import run_bandit

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))

    with patch("app.services.scanner.bandit_runner.asyncio.create_subprocess_exec",
               return_value=mock_proc):
        findings = await run_bandit("print('hello')", "python")

    assert findings == []


@pytest.mark.asyncio
async def test_bandit_returns_empty_on_json_error():
    from app.services.scanner.bandit_runner import run_bandit

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"NOT JSON", b""))

    with patch("app.services.scanner.bandit_runner.asyncio.create_subprocess_exec",
               return_value=mock_proc):
        findings = await run_bandit("x = 1", "python")

    assert findings == []


# ─────────────────────────────────────────────────────────────
# 3. Semgrep runner (subprocess mocked)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_semgrep_returns_findings_when_available():
    from app.services.scanner.semgrep_runner import run_semgrep

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(SEMGREP_WARNING_JSON.encode(), b""))

    with patch("app.services.scanner.semgrep_runner.semgrep_available", return_value=True), \
         patch("app.services.scanner.semgrep_runner.asyncio.create_subprocess_exec",
               return_value=mock_proc):
        findings = await run_semgrep("eval(user_input)", "python")

    assert len(findings) == 1
    f = findings[0]
    assert f.tool == "semgrep"
    assert f.severity == "MEDIUM"   # WARNING → MEDIUM
    assert f.cwe_id == "CWE-78"
    assert f.owasp_category == "A1:2017-Injection"


@pytest.mark.asyncio
async def test_semgrep_skips_when_not_installed():
    from app.services.scanner.semgrep_runner import run_semgrep

    with patch("app.services.scanner.semgrep_runner.semgrep_available", return_value=False):
        findings = await run_semgrep("eval(x)", "python")

    assert findings == []


@pytest.mark.asyncio
async def test_semgrep_returns_empty_on_json_error():
    from app.services.scanner.semgrep_runner import run_semgrep

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"BAD JSON", b""))

    with patch("app.services.scanner.semgrep_runner.semgrep_available", return_value=True), \
         patch("app.services.scanner.semgrep_runner.asyncio.create_subprocess_exec",
               return_value=mock_proc):
        findings = await run_semgrep("x = 1", "python")

    assert findings == []


# ─────────────────────────────────────────────────────────────
# 4. Dependency auditor (subprocess mocked)
# ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dep_auditor_pip_returns_findings():
    from app.services.scanner.dep_auditor import audit_dependencies

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(PIPAUDIT_JSON.encode(), b""))

    with patch("app.services.scanner.dep_auditor.asyncio.create_subprocess_exec",
               return_value=mock_proc):
        findings = await audit_dependencies("requests==2.25.0\n", "pip")

    assert len(findings) == 1
    d = findings[0]
    assert d.package_name == "requests"
    assert d.installed_version == "2.25.0"
    assert d.fixed_version == "2.31.0"
    assert "CVE-2023-32681" in d.cve_ids
    assert d.ecosystem == "pip"
    assert d.severity == "MEDIUM"   # derived from aliases (no direct severity field)


@pytest.mark.asyncio
async def test_dep_auditor_unknown_ecosystem_returns_empty():
    from app.services.scanner.dep_auditor import audit_dependencies

    findings = await audit_dependencies("some content", "cargo")
    assert findings == []


@pytest.mark.asyncio
async def test_dep_auditor_empty_dep_file_returns_empty():
    from app.services.scanner.dep_auditor import audit_dependencies

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(b"", b""))

    with patch("app.services.scanner.dep_auditor.asyncio.create_subprocess_exec",
               return_value=mock_proc):
        findings = await audit_dependencies("requests==2.25.0", "pip")

    assert findings == []


# ─────────────────────────────────────────────────────────────
# 5. Full pipeline status transitions
# ─────────────────────────────────────────────────────────────

async def _make_pending_scan(db, code: str = "import os") -> Scan:
    """Insert a PENDING scan directly and return it."""
    scan = Scan(
        user_id=uuid.uuid4(),
        name="test-scan",
        status=ScanStatus.PENDING.value,
        source_type=SourceType.SNIPPET.value,
        language="python",
        source_meta={"code": code, "language": "python"},
    )
    db.add(scan)
    await db.flush()
    await db.commit()
    return scan


@pytest.mark.asyncio
async def test_pipeline_reaches_complete(db_session):
    """Pipeline sets status=COMPLETE and creates a Report row."""
    scan = await _make_pending_scan(db_session)

    with patch("app.tasks.scan_pipeline.run_bandit",
               new_callable=AsyncMock, return_value=[_make_sec("HIGH")]) as _b, \
         patch("app.tasks.scan_pipeline.run_semgrep",
               new_callable=AsyncMock, return_value=[]) as _s, \
         patch("app.tasks.scan_pipeline.audit_dependencies",
               new_callable=AsyncMock, return_value=[]) as _d, \
         patch("app.tasks.scan_pipeline.generate_analysis",
               new_callable=AsyncMock,
               return_value=AIAnalysis(summary="ok", fix_suggestions=[], narrative="ok")):

        await run_scan_pipeline(scan.id, db_session)

    await db_session.refresh(scan)
    assert scan.status == ScanStatus.COMPLETE.value
    assert scan.completed_at is not None

    report_result = await db_session.execute(
        select(Report).where(Report.scan_id == scan.id)
    )
    report = report_result.scalar_one_or_none()
    assert report is not None
    assert report.release_readiness_score == 90   # 100 - 10 (1 HIGH)
    assert report.high_count == 1


@pytest.mark.asyncio
async def test_pipeline_merges_bandit_and_semgrep(db_session):
    """Security findings from both Bandit and Semgrep appear in the DB."""
    scan = await _make_pending_scan(db_session)

    with patch("app.tasks.scan_pipeline.run_bandit",
               new_callable=AsyncMock, return_value=[_make_sec("HIGH", "bandit")]), \
         patch("app.tasks.scan_pipeline.run_semgrep",
               new_callable=AsyncMock, return_value=[_make_sec("MEDIUM", "semgrep")]), \
         patch("app.tasks.scan_pipeline.audit_dependencies",
               new_callable=AsyncMock, return_value=[]), \
         patch("app.tasks.scan_pipeline.generate_analysis",
               new_callable=AsyncMock,
               return_value=AIAnalysis(summary="", fix_suggestions=[], narrative="")):

        await run_scan_pipeline(scan.id, db_session)

    result = await db_session.execute(
        select(SecurityFinding).where(SecurityFinding.scan_id == scan.id)
    )
    findings = result.scalars().all()
    tools = {f.tool for f in findings}
    assert "bandit" in tools
    assert "semgrep" in tools
    assert len(findings) == 2


@pytest.mark.asyncio
async def test_pipeline_persists_dep_findings(db_session):
    """Dependency findings are written to the DB."""
    scan = await _make_pending_scan(db_session)

    with patch("app.tasks.scan_pipeline.run_bandit",
               new_callable=AsyncMock, return_value=[]), \
         patch("app.tasks.scan_pipeline.run_semgrep",
               new_callable=AsyncMock, return_value=[]), \
         patch("app.tasks.scan_pipeline.audit_dependencies",
               new_callable=AsyncMock, return_value=[_make_dep("HIGH")]), \
         patch("app.tasks.scan_pipeline.generate_analysis",
               new_callable=AsyncMock,
               return_value=AIAnalysis(summary="", fix_suggestions=[], narrative="")):

        scan.source_meta = {"code": "x=1", "dep_file_content": "requests==2.25.0", "dep_ecosystem": "pip"}
        await db_session.commit()
        await run_scan_pipeline(scan.id, db_session)

    result = await db_session.execute(
        select(DependencyFinding).where(DependencyFinding.scan_id == scan.id)
    )
    dep_findings = result.scalars().all()
    assert len(dep_findings) == 1
    assert dep_findings[0].package_name == "requests"


@pytest.mark.asyncio
async def test_pipeline_marks_failed_on_exception(db_session):
    """When a scanner raises, the scan is marked FAILED and the API survives."""
    scan = await _make_pending_scan(db_session)

    with patch("app.tasks.scan_pipeline.run_bandit",
               new_callable=AsyncMock, side_effect=RuntimeError("bandit exploded")), \
         patch("app.tasks.scan_pipeline.run_semgrep",
               new_callable=AsyncMock, return_value=[]):

        # Should not raise — pipeline handles exceptions internally
        await run_scan_pipeline(scan.id, db_session)

    await db_session.refresh(scan)
    assert scan.status == ScanStatus.FAILED.value
    assert "bandit exploded" in (scan.error_message or "")


@pytest.mark.asyncio
async def test_pipeline_noop_for_missing_scan(db_session):
    """Pipeline silently returns when given an unknown scan_id."""
    fake_id = uuid.uuid4()
    # Should not raise
    await run_scan_pipeline(fake_id, db_session)


@pytest.mark.asyncio
async def test_pipeline_skips_dep_audit_when_no_dep_file(db_session):
    """audit_dependencies is NOT called when dep_file_content is empty."""
    scan = await _make_pending_scan(db_session)

    with patch("app.tasks.scan_pipeline.run_bandit",
               new_callable=AsyncMock, return_value=[]), \
         patch("app.tasks.scan_pipeline.run_semgrep",
               new_callable=AsyncMock, return_value=[]), \
         patch("app.tasks.scan_pipeline.audit_dependencies",
               new_callable=AsyncMock, return_value=[]) as mock_audit, \
         patch("app.tasks.scan_pipeline.generate_analysis",
               new_callable=AsyncMock,
               return_value=AIAnalysis(summary="", fix_suggestions=[], narrative="")):

        await run_scan_pipeline(scan.id, db_session)

    mock_audit.assert_not_called()
