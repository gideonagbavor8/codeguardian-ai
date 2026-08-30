"""
app/services/scanner/base.py
Shared dataclasses for scanner output.
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
from dataclasses import dataclass, field
from typing import List, Sequence

logger = logging.getLogger(__name__)


@dataclass
class RawSecurityFinding:
    """Scanner-agnostic representation of a single security issue."""
    tool: str
    rule_id: str | None
    severity: str          # CRITICAL | HIGH | MEDIUM | LOW | INFO
    confidence: str | None
    file_path: str | None
    line_number: int | None
    code_snippet: str | None
    message: str
    cwe_id: str | None = None
    owasp_category: str | None = None


@dataclass
class RawDependencyFinding:
    """Scanner-agnostic representation of a vulnerable package."""
    package_name: str
    installed_version: str | None
    fixed_version: str | None
    severity: str
    cve_ids: List[str] = field(default_factory=list)
    description: str | None = None
    ecosystem: str = "pip"


# Normalise severity strings from tool-specific labels to our canonical set
_SEVERITY_MAP = {
    "critical": "CRITICAL",
    "high":     "HIGH",
    "medium":   "MEDIUM",
    "moderate": "MEDIUM",
    "low":      "LOW",
    "info":     "INFO",
    "none":     "LOW",
}


def normalise_severity(raw: str) -> str:
    return _SEVERITY_MAP.get(raw.lower(), "INFO")


# ── Subprocess execution helper ────────────────────────────────

async def run_subprocess_in_thread(
    argv: Sequence[str],
    timeout: float,
    cwd: str | None = None,
    capture: bool = True,
) -> tuple[bytes, bytes]:
    """
    Run *argv* with the blocking subprocess API inside a worker thread.

    Fallback for event loops that do not implement asyncio subprocesses.  On
    Windows, uvicorn installs WindowsSelectorEventLoopPolicy whenever it needs
    a subprocess supervisor (``--reload`` or ``--workers > 1``), and that loop
    raises NotImplementedError from asyncio.create_subprocess_exec() — which
    would otherwise silently reduce every scanner to zero findings.

    Returns (stdout, stderr).  Raises asyncio.TimeoutError on timeout and
    FileNotFoundError when the binary is missing, so callers can keep using
    the same exception handlers as the asyncio path.
    """
    def _run() -> tuple[bytes, bytes]:
        completed = subprocess.run(  # noqa: S603 - argv is a fixed scanner command
            list(argv),
            stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture else subprocess.DEVNULL,
            timeout=timeout,
            cwd=cwd,
            check=False,
        )
        return completed.stdout or b"", completed.stderr or b""

    logger.debug("asyncio subprocess unavailable — running %s in a thread", argv[0])
    try:
        return await asyncio.get_running_loop().run_in_executor(None, _run)
    except subprocess.TimeoutExpired as exc:
        raise asyncio.TimeoutError(str(exc)) from exc
