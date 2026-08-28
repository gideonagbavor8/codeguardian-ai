"""
app/services/scanner/base.py
Shared dataclasses for scanner output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


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
