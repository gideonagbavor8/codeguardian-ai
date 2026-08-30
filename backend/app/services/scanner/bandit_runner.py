"""
app/services/scanner/bandit_runner.py
Runs Bandit against a temporary file and returns normalised findings.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import List

from app.services.scanner.base import (
    RawSecurityFinding,
    normalise_severity,
    run_subprocess_in_thread,
)

logger = logging.getLogger(__name__)

# Directories excluded from recursive scans (belt-and-braces: repo archives
# already drop these at extraction time).
_EXCLUDE_GLOBS = ",".join(
    f"*/{d}/*" for d in
    ("node_modules", ".venv", "venv", "dist", "build", ".next", "vendor")
)


def _display_path(filename: str, scan_root: str | None) -> str:
    """Repo-relative path for directory scans, bare filename otherwise."""
    if not filename:
        return ""
    if scan_root:
        try:
            return os.path.relpath(filename, scan_root).replace(os.sep, "/")
        except ValueError:  # different drive on Windows
            return os.path.basename(filename)
    return os.path.basename(filename)


async def run_bandit(
    code: str,
    language: str = "python",
    target_path: str | None = None,
) -> List[RawSecurityFinding]:
    """
    Execute Bandit and parse its JSON output.
    Returns a list of RawSecurityFinding.  Never raises — returns [] on failure.

    Two modes:
      - *target_path* given: scan that directory recursively.  Bandit selects
        .py files itself, so the *language* hint does not gate it and *code*
        is ignored.  Reported paths are relative to the directory.
      - otherwise: write *code* to a temp file and scan it (Python only).
    """
    scan_root: str | None = None
    tmp_path: str | None = None

    if target_path is not None:
        scan_root = target_path
        argv = [
            "bandit", "-r", target_path,
            "-f", "json", "-q", "--exit-zero",
            "-x", _EXCLUDE_GLOBS,
        ]
    else:
        if language.lower() != "python":
            return []
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(code)
            tmp_path = tmp.name
        argv = ["bandit", "-f", "json", "-q", "--exit-zero", tmp_path]

    findings: List[RawSecurityFinding] = []

    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        except NotImplementedError:
            # Event loop without asyncio subprocess support (Windows
            # SelectorEventLoop) — run bandit in a worker thread instead.
            stdout, stderr = await run_subprocess_in_thread(argv, timeout=60)

        raw_text = stdout.decode("utf-8", errors="replace").strip()
        if not raw_text:
            logger.warning("bandit produced no output. stderr: %s", stderr.decode()[:500])
            return findings

        raw = json.loads(raw_text)

        for result in raw.get("results", []):
            cwe_data = result.get("issue_cwe")
            cwe_id: str | None = None
            if isinstance(cwe_data, dict) and cwe_data.get("id"):
                cwe_id = f"CWE-{cwe_data['id']}"

            confidence_raw = result.get("issue_confidence", "")
            confidence = confidence_raw.upper() if confidence_raw else None

            findings.append(
                RawSecurityFinding(
                    tool="bandit",
                    rule_id=result.get("test_id"),
                    severity=normalise_severity(result.get("issue_severity", "LOW")),
                    confidence=confidence,
                    file_path=_display_path(result.get("filename", ""), scan_root),
                    line_number=result.get("line_number"),
                    code_snippet=result.get("code"),
                    message=result.get("issue_text", ""),
                    cwe_id=cwe_id,
                    owasp_category=result.get("issue_cwe", {}).get("link") if isinstance(result.get("issue_cwe"), dict) else None,
                )
            )

    except asyncio.TimeoutError:
        logger.error("bandit timed out after 60 s")
    except json.JSONDecodeError as exc:
        logger.error("bandit JSON parse error: %s", exc)
    except FileNotFoundError:
        logger.error("bandit is not installed or not on PATH")
    except Exception as exc:
        logger.error("bandit failed: %s", exc, exc_info=True)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return findings
