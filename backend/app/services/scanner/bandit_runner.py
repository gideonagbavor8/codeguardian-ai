"""
app/services/scanner/bandit_runner.py
Runs Bandit against a temporary file and returns normalised findings.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import List

from app.services.scanner.base import RawSecurityFinding, normalise_severity


async def run_bandit(code: str, language: str = "python") -> List[RawSecurityFinding]:
    """
    Write *code* to a temp file, execute Bandit, parse JSON output.
    Returns a list of RawSecurityFinding.  Never raises — returns [] on failure.
    """
    if language.lower() != "python":
        # Bandit only handles Python; return empty for other languages
        return []

    suffix = ".py"
    findings: List[RawSecurityFinding] = []

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "bandit", "-f", "json", "-q", "--exit-zero", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=60)
        raw = json.loads(stdout.decode())

        for result in raw.get("results", []):
            findings.append(
                RawSecurityFinding(
                    tool="bandit",
                    rule_id=result.get("test_id"),
                    severity=normalise_severity(result.get("issue_severity", "LOW")),
                    confidence=result.get("issue_confidence", "").upper() or None,
                    file_path=os.path.basename(result.get("filename", "")),
                    line_number=result.get("line_number"),
                    code_snippet=result.get("code"),
                    message=result.get("issue_text", ""),
                    cwe_id=(
                        f"CWE-{result['issue_cwe']['id']}"
                        if result.get("issue_cwe")
                        else None
                    ),
                )
            )
    except Exception:
        # Bandit not installed or parse error — return empty gracefully
        pass
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return findings
