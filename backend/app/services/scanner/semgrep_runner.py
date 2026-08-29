"""
app/services/scanner/semgrep_runner.py
Semgrep multi-language static analysis runner.
Wired into scan_pipeline alongside Bandit.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
from typing import List

from app.services.scanner.base import RawSecurityFinding, normalise_severity

logger = logging.getLogger(__name__)

_EXT_MAP = {
    "python":     ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "java":       ".java",
    "go":         ".go",
    "ruby":       ".rb",
    "c":          ".c",
    "cpp":        ".cpp",
    "php":        ".php",
}


def semgrep_available() -> bool:
    """Return True if the semgrep binary is on PATH."""
    return shutil.which("semgrep") is not None


async def run_semgrep(code: str, language: str = "python") -> List[RawSecurityFinding]:
    """
    Run Semgrep with the auto ruleset against *code*.
    Returns [] gracefully when semgrep is not installed or any error occurs.
    """
    if not semgrep_available():
        logger.debug("semgrep not found on PATH — skipping")
        return []

    suffix = _EXT_MAP.get(language.lower(), ".txt")
    findings: List[RawSecurityFinding] = []

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "semgrep",
            "--config", "auto",
            "--json",
            "--quiet",
            "--no-git-ignore",
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

        raw_text = stdout.decode("utf-8", errors="replace").strip()
        if not raw_text:
            logger.debug("semgrep produced no output. stderr: %s", stderr.decode()[:500])
            return findings

        raw = json.loads(raw_text)

        for result in raw.get("results", []):
            extra = result.get("extra", {})
            meta = extra.get("metadata", {})

            # Semgrep severity field names: ERROR, WARNING, INFO
            sev_raw = extra.get("severity", "INFO")
            severity = _semgrep_severity(sev_raw)

            # CWE may be a list or a single string
            cwe_raw = meta.get("cwe")
            if isinstance(cwe_raw, list):
                cwe_id = cwe_raw[0] if cwe_raw else None
            else:
                cwe_id = cwe_raw

            # OWASP may also be a list
            owasp_raw = meta.get("owasp")
            if isinstance(owasp_raw, list):
                owasp = owasp_raw[0] if owasp_raw else None
            else:
                owasp = owasp_raw

            findings.append(
                RawSecurityFinding(
                    tool="semgrep",
                    rule_id=result.get("check_id"),
                    severity=severity,
                    confidence=None,
                    file_path=os.path.basename(result.get("path", "")),
                    line_number=result.get("start", {}).get("line"),
                    code_snippet=extra.get("lines"),
                    message=extra.get("message", ""),
                    cwe_id=cwe_id,
                    owasp_category=owasp,
                )
            )

    except asyncio.TimeoutError:
        logger.error("semgrep timed out after 120 s")
    except json.JSONDecodeError as exc:
        logger.error("semgrep JSON parse error: %s", exc)
    except FileNotFoundError:
        logger.error("semgrep binary not found")
    except Exception as exc:
        logger.error("semgrep failed: %s", exc, exc_info=True)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return findings


def _semgrep_severity(raw: str) -> str:
    """Map Semgrep's severity labels to our canonical set."""
    mapping = {
        "error":   "HIGH",
        "warning": "MEDIUM",
        "info":    "INFO",
        # Semgrep also uses these:
        "critical": "CRITICAL",
        "high":     "HIGH",
        "medium":   "MEDIUM",
        "low":      "LOW",
    }
    return mapping.get(raw.lower(), "INFO")
