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

from app.services.scanner.base import RawSecurityFinding, normalise_severity

logger = logging.getLogger(__name__)


async def run_bandit(code: str, language: str = "python") -> List[RawSecurityFinding]:
    """
    Write *code* to a temp file, execute Bandit, parse JSON output.
    Returns a list of RawSecurityFinding.  Never raises — returns [] on failure.
    Only runs for Python; returns [] for all other languages.
    """
    if language.lower() != "python":
        return []

    findings: List[RawSecurityFinding] = []

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "bandit", "-f", "json", "-q", "--exit-zero", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)

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
                    file_path=os.path.basename(result.get("filename", "")),
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
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return findings
