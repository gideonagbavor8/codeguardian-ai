"""
app/services/scanner/dep_auditor.py
Audits a dependency file (requirements.txt or package.json) for known CVEs.
Uses pip-audit for Python, npm audit for Node.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from typing import List

from app.services.scanner.base import (
    RawDependencyFinding,
    normalise_severity,
    run_subprocess_in_thread,
)

logger = logging.getLogger(__name__)

# pip-audit vulnerability IDs that carry a CVSS severity hint
# (pip-audit does not emit a severity field directly; we derive it from aliases
# or fall back to the PYSEC prefix convention).
_PYSEC_DEFAULT_SEVERITY = "MEDIUM"


def _severity_from_aliases(aliases: list[str]) -> str:
    """
    pip-audit does not include a severity field in its JSON output.
    We approximate from aliases:
      - GHSA IDs encode severity in their second segment for newer advisories
        (e.g. GHSA-xxxx-xxxx-xxxx — not machine-readable, so we skip this)
      - Fall back to MEDIUM as a conservative default when no signal is available.

    If callers want precise CVSS scores they should call the OSV API separately;
    for the MVP MEDIUM is a safe, honest default.
    """
    # If there's no alias at all, default LOW
    if not aliases:
        return "LOW"
    return _PYSEC_DEFAULT_SEVERITY


async def audit_dependencies(
    dep_file_content: str,
    ecosystem: str = "pip",
) -> List[RawDependencyFinding]:
    """
    Run the appropriate auditor for the given *ecosystem*.
    Returns normalised RawDependencyFinding list. Never raises.
    """
    if ecosystem == "pip":
        return await _audit_pip(dep_file_content)
    if ecosystem == "npm":
        return await _audit_npm(dep_file_content)
    return []


# ── pip-audit ─────────────────────────────────────────────────

async def _audit_pip(requirements_txt: str) -> List[RawDependencyFinding]:
    findings: List[RawDependencyFinding] = []

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(requirements_txt)
        tmp_path = tmp.name

    argv = [
        "pip-audit",
        "--format", "json",
        "--progress-spinner", "off",
        "-r", tmp_path,
    ]

    try:
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
        except NotImplementedError:
            # Event loop without asyncio subprocess support (Windows
            # SelectorEventLoop) — run pip-audit in a worker thread instead.
            stdout, stderr = await run_subprocess_in_thread(argv, timeout=120)

        raw_text = stdout.decode("utf-8", errors="replace").strip()
        if not raw_text:
            logger.warning("pip-audit produced no output. stderr: %s", stderr.decode()[:500])
            return findings

        raw = json.loads(raw_text)

        for dep in raw.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                aliases: list[str] = vuln.get("aliases", [])
                fix_versions: list[str] = vuln.get("fix_versions", [])
                cve_ids = [a for a in aliases if a.startswith("CVE-")]

                findings.append(
                    RawDependencyFinding(
                        package_name=dep.get("name", "unknown"),
                        installed_version=dep.get("version"),
                        fixed_version=fix_versions[0] if fix_versions else None,
                        severity=_severity_from_aliases(aliases),
                        cve_ids=cve_ids,
                        description=vuln.get("description"),
                        ecosystem="pip",
                    )
                )
    except asyncio.TimeoutError:
        logger.error("pip-audit timed out after 120 s")
    except json.JSONDecodeError as exc:
        logger.error("pip-audit JSON parse error: %s", exc)
    except Exception as exc:
        logger.error("pip-audit failed: %s", exc, exc_info=True)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return findings


# ── npm audit ─────────────────────────────────────────────────

async def _audit_npm(package_json: str) -> List[RawDependencyFinding]:
    findings: List[RawDependencyFinding] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_path = os.path.join(tmp_dir, "package.json")
        with open(pkg_path, "w", encoding="utf-8") as f:
            f.write(package_json)

        install_argv = ["npm", "install", "--package-lock-only", "--ignore-scripts"]
        audit_argv = ["npm", "audit", "--json"]

        try:
            # Generate package-lock.json first (required by npm audit)
            try:
                install_proc = await asyncio.create_subprocess_exec(
                    *install_argv,
                    cwd=tmp_dir,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(install_proc.wait(), timeout=60)

                proc = await asyncio.create_subprocess_exec(
                    *audit_argv,
                    cwd=tmp_dir,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            except NotImplementedError:
                # Event loop without asyncio subprocess support (Windows
                # SelectorEventLoop) — run npm in a worker thread instead.
                await run_subprocess_in_thread(
                    install_argv, timeout=60, cwd=tmp_dir, capture=False
                )
                stdout, stderr = await run_subprocess_in_thread(
                    audit_argv, timeout=120, cwd=tmp_dir
                )

            raw_text = stdout.decode("utf-8", errors="replace").strip()
            if not raw_text:
                return findings

            raw = json.loads(raw_text)

            for _name, vuln_data in raw.get("vulnerabilities", {}).items():
                # CVEs may appear as string items in the "via" list
                cves = [
                    v for v in vuln_data.get("via", [])
                    if isinstance(v, str) and v.startswith("CVE-")
                ]
                fix_info = vuln_data.get("fixAvailable")
                fixed_version = (
                    fix_info.get("version") if isinstance(fix_info, dict) else None
                )
                findings.append(
                    RawDependencyFinding(
                        package_name=vuln_data.get("name", _name),
                        installed_version=None,
                        fixed_version=fixed_version,
                        severity=normalise_severity(vuln_data.get("severity", "low")),
                        cve_ids=cves,
                        description=None,
                        ecosystem="npm",
                    )
                )
        except asyncio.TimeoutError:
            logger.error("npm audit timed out")
        except json.JSONDecodeError as exc:
            logger.error("npm audit JSON parse error: %s", exc)
        except Exception as exc:
            logger.error("npm audit failed: %s", exc, exc_info=True)

    return findings
