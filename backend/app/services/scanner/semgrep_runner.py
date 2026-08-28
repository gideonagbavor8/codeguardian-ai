"""
app/services/scanner/semgrep_runner.py
STRETCH — Semgrep multi-language static analysis runner.
Not wired into the pipeline for MVP; import and call from scan_pipeline.py when ready.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import List

from app.services.scanner.base import RawSecurityFinding, normalise_severity


async def run_semgrep(code: str, language: str = "python") -> List[RawSecurityFinding]:
    """
    Run Semgrep with the auto ruleset against *code*.
    Requires `semgrep` to be installed (`pip install semgrep`).
    """
    ext_map = {
        "python": ".py",
        "javascript": ".js",
        "typescript": ".ts",
        "java": ".java",
        "go": ".go",
        "ruby": ".rb",
    }
    suffix = ext_map.get(language.lower(), ".txt")
    findings: List[RawSecurityFinding] = []

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "semgrep", "--config", "auto", "--json", "--quiet", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        raw = json.loads(stdout.decode())

        for result in raw.get("results", []):
            meta = result.get("extra", {}).get("metadata", {})
            findings.append(
                RawSecurityFinding(
                    tool="semgrep",
                    rule_id=result.get("check_id"),
                    severity=normalise_severity(
                        result.get("extra", {}).get("severity", "INFO")
                    ),
                    confidence=None,
                    file_path=os.path.basename(result.get("path", "")),
                    line_number=result.get("start", {}).get("line"),
                    code_snippet=result.get("extra", {}).get("lines"),
                    message=result.get("extra", {}).get("message", ""),
                    cwe_id=meta.get("cwe", [None])[0]
                    if isinstance(meta.get("cwe"), list)
                    else meta.get("cwe"),
                    owasp_category=meta.get("owasp", [None])[0]
                    if isinstance(meta.get("owasp"), list)
                    else meta.get("owasp"),
                )
            )
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return findings
