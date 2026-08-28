"""
app/services/scanner/dep_auditor.py
Audits a dependency file (requirements.txt or package.json) for known CVEs.
Uses pip-audit for Python, npm audit for Node.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import List

from app.services.scanner.base import RawDependencyFinding, normalise_severity


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
    elif ecosystem == "npm":
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

    try:
        proc = await asyncio.create_subprocess_exec(
            "pip-audit", "--format", "json", "--progress-spinner", "off",
            "-r", tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
        raw = json.loads(stdout.decode())

        for dep in raw.get("dependencies", []):
            for vuln in dep.get("vulns", []):
                fix_versions = vuln.get("fix_versions", [])
                findings.append(
                    RawDependencyFinding(
                        package_name=dep.get("name", "unknown"),
                        installed_version=dep.get("version"),
                        fixed_version=fix_versions[0] if fix_versions else None,
                        severity=normalise_severity(
                            vuln.get("aliases", [""])[0][:4] if vuln.get("aliases") else "LOW"
                        ),
                        cve_ids=[
                            a for a in vuln.get("aliases", [])
                            if a.startswith("CVE-")
                        ],
                        description=vuln.get("description"),
                        ecosystem="pip",
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


# ── npm audit ─────────────────────────────────────────────────

async def _audit_npm(package_json: str) -> List[RawDependencyFinding]:
    findings: List[RawDependencyFinding] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        pkg_path = os.path.join(tmp_dir, "package.json")
        with open(pkg_path, "w", encoding="utf-8") as f:
            f.write(package_json)

        try:
            # npm audit requires a lock file; we use --package-lock-only to generate one first
            await asyncio.create_subprocess_exec(
                "npm", "install", "--package-lock-only", "--ignore-scripts",
                cwd=tmp_dir,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            proc = await asyncio.create_subprocess_exec(
                "npm", "audit", "--json",
                cwd=tmp_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=120)
            raw = json.loads(stdout.decode())

            for _name, vuln_data in raw.get("vulnerabilities", {}).items():
                cves = [
                    v for v in vuln_data.get("via", [])
                    if isinstance(v, str) and v.startswith("CVE-")
                ]
                findings.append(
                    RawDependencyFinding(
                        package_name=vuln_data.get("name", _name),
                        installed_version=None,
                        fixed_version=vuln_data.get("fixAvailable", {}).get("version")
                        if isinstance(vuln_data.get("fixAvailable"), dict)
                        else None,
                        severity=normalise_severity(vuln_data.get("severity", "low")),
                        cve_ids=cves,
                        description=None,
                        ecosystem="npm",
                    )
                )
        except Exception:
            pass

    return findings
