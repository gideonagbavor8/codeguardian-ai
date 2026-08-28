"""
app/services/ai/prompts.py
Prompt templates and structured-response parser for watsonx.ai.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.scanner.base import RawDependencyFinding, RawSecurityFinding


@dataclass
class AIAnalysis:
    summary: str = ""
    fix_suggestions: list[dict[str, Any]] = field(default_factory=list)
    narrative: str = ""


def build_analysis_prompt(
    security_findings: list[RawSecurityFinding],
    dep_findings: list[RawDependencyFinding],
) -> str:
    """
    Build a structured prompt that instructs the model to return a JSON object
    with keys: summary, fix_suggestions (array), narrative.
    """
    sec_lines: list[str] = []
    for i, f in enumerate(security_findings):
        sec_lines.append(
            f"  [{i}] {f.severity} | {f.tool} | rule={f.rule_id} | "
            f"line={f.line_number} | cwe={f.cwe_id}\n"
            f"      Message: {f.message}\n"
            f"      Code:    {(f.code_snippet or '').strip()[:200]}"
        )

    dep_lines: list[str] = []
    for j, d in enumerate(dep_findings):
        cves = ", ".join(d.cve_ids) if d.cve_ids else "none"
        dep_lines.append(
            f"  [{j}] {d.severity} | {d.package_name}@{d.installed_version} → "
            f"fix={d.fixed_version} | CVEs: {cves}"
        )

    sec_block = "\n".join(sec_lines) if sec_lines else "  (none)"
    dep_block = "\n".join(dep_lines) if dep_lines else "  (none)"

    prompt = f"""You are a senior application security engineer reviewing code scan results.

SECURITY FINDINGS ({len(security_findings)} total):
{sec_block}

DEPENDENCY VULNERABILITIES ({len(dep_findings)} total):
{dep_block}

Instructions:
1. Write a concise SUMMARY (2-4 sentences) explaining the most important security issues in plain English for a developer.
2. For each security finding listed above, provide a specific, actionable FIX SUGGESTION. Reference the finding by its index number [0], [1], etc.
3. Write a NARRATIVE (1-2 sentences) assessing the overall code health and release readiness.

Respond ONLY with valid JSON in this exact format — no markdown, no extra text:
{{
  "summary": "<plain English summary>",
  "fix_suggestions": [
    {{"index": 0, "suggestion": "<actionable fix for finding [0]>"}},
    {{"index": 1, "suggestion": "<actionable fix for finding [1]>"}}
  ],
  "narrative": "<overall assessment>"
}}"""

    return prompt


def parse_ai_response(raw_text: str) -> AIAnalysis:
    """
    Parse the model's text response into an AIAnalysis dataclass.
    Handles cases where the model wraps JSON in markdown fences.
    """
    # Strip markdown code fences if present
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        return AIAnalysis(
            summary=data.get("summary", ""),
            fix_suggestions=data.get("fix_suggestions", []),
            narrative=data.get("narrative", ""),
        )
    except (json.JSONDecodeError, ValueError):
        # Fallback: return the raw text as the summary
        return AIAnalysis(
            summary=raw_text[:1000],
            fix_suggestions=[],
            narrative="AI analysis could not be parsed.",
        )
