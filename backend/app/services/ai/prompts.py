"""
app/services/ai/prompts.py
Prompt templates and structured-response parser for watsonx.ai.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.scanner.base import RawDependencyFinding, RawSecurityFinding

logger = logging.getLogger(__name__)

# Maximum number of security findings included in the AI prompt.
# Keeps prompts within token budgets for large codebases.
_MAX_FINDINGS_IN_PROMPT = 20
# Maximum fix suggestions stored (mirrors the prompt cap).
_MAX_FIX_SUGGESTIONS = _MAX_FINDINGS_IN_PROMPT


@dataclass
class AIAnalysis:
    """Structured output from the AI analysis layer."""
    summary: str = ""
    fix_suggestions: list[dict[str, Any]] = field(default_factory=list)
    narrative: str = ""


# ── Prompt builder ────────────────────────────────────────────

def build_analysis_prompt(
    security_findings: list[RawSecurityFinding],
    dep_findings: list[RawDependencyFinding],
) -> str:
    """
    Build a structured prompt instructing the model to return a JSON object
    with keys: summary, fix_suggestions (array), narrative.

    Caps findings at _MAX_FINDINGS_IN_PROMPT so the prompt stays within token
    limits even for large scans.
    """
    capped = security_findings[:_MAX_FINDINGS_IN_PROMPT]

    sec_lines: list[str] = []
    for i, f in enumerate(capped):
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

    prompt = (
        "You are a senior application security engineer reviewing code scan results.\n\n"
        f"SECURITY FINDINGS ({len(capped)} total):\n"
        f"{sec_block}\n\n"
        f"DEPENDENCY VULNERABILITIES ({len(dep_findings)} total):\n"
        f"{dep_block}\n\n"
        "Instructions:\n"
        "1. Write a concise SUMMARY (2-4 sentences) explaining the most important "
        "security issues in plain English for a developer.\n"
        "2. For each security finding listed above, provide a specific, actionable "
        "FIX SUGGESTION. Reference the finding by its index number [0], [1], etc.\n"
        "3. Write a NARRATIVE (1-2 sentences) assessing the overall code health "
        "and release readiness.\n\n"
        'Respond ONLY with valid JSON in this exact format — no markdown, no extra text:\n'
        '{\n'
        '  "summary": "<plain English summary>",\n'
        '  "fix_suggestions": [\n'
        '    {"index": 0, "suggestion": "<actionable fix for finding [0]>"},\n'
        '    {"index": 1, "suggestion": "<actionable fix for finding [1]>"}\n'
        '  ],\n'
        '  "narrative": "<overall assessment>"\n'
        '}'
    )
    return prompt


# ── Response parser ───────────────────────────────────────────

def parse_ai_response(raw_text: str) -> AIAnalysis:
    """
    Parse the model's text response into an AIAnalysis dataclass.

    Robustness guarantees:
    - Strips markdown code fences (```json … ```) if present.
    - Extracts the first JSON object even when there is leading/trailing prose.
    - Validates that fix_suggestions items are dicts with string 'suggestion'.
    - Falls back gracefully on any parse or validation failure.
    - Never raises.
    """
    if not raw_text or not raw_text.strip():
        logger.warning("AI response was empty")
        return _parse_fallback("", "AI returned an empty response.")

    text = raw_text.strip()

    # Strip markdown fences: ```json … ``` or ``` … ```
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)
    text = text.strip()

    # If the model added prose before/after the JSON, extract the first {...} block
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        text = json_match.group(0)

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("AI response JSON parse failed: %s — raw: %.200s", exc, raw_text)
        return _parse_fallback(raw_text, "AI response could not be parsed as JSON.")

    if not isinstance(data, dict):
        logger.warning("AI response was not a JSON object — raw: %.200s", raw_text)
        return _parse_fallback(raw_text, "AI response was not a JSON object.")

    summary = _coerce_str(data.get("summary"), "")
    narrative = _coerce_str(data.get("narrative"), "")
    fix_suggestions = _validate_fix_suggestions(data.get("fix_suggestions"))

    return AIAnalysis(
        summary=summary,
        fix_suggestions=fix_suggestions,
        narrative=narrative,
    )


def _coerce_str(value: Any, default: str) -> str:
    """Return value as a string if it is str-like, otherwise the default."""
    if isinstance(value, str):
        return value
    if value is not None:
        return str(value)
    return default


def _validate_fix_suggestions(raw: Any) -> list[dict[str, Any]]:
    """
    Validate and normalise the fix_suggestions array.

    Accepts:
      - A list of {"index": int, "suggestion": str} dicts.
    Drops items that are not dicts or that lack a "suggestion" key.
    Caps at _MAX_FIX_SUGGESTIONS entries.
    """
    if not isinstance(raw, list):
        return []

    validated: list[dict[str, Any]] = []
    for item in raw[:_MAX_FIX_SUGGESTIONS]:
        if not isinstance(item, dict):
            continue
        suggestion = item.get("suggestion")
        if not isinstance(suggestion, str) or not suggestion.strip():
            continue
        validated.append({
            "index": int(item["index"]) if isinstance(item.get("index"), (int, float)) else len(validated),
            "suggestion": suggestion.strip(),
        })
    return validated


def _parse_fallback(raw_text: str, reason: str) -> AIAnalysis:
    """Return a degraded AIAnalysis when parsing fails."""
    return AIAnalysis(
        summary=raw_text[:500] if raw_text else "",
        fix_suggestions=[],
        narrative=reason,
    )


# ── Placeholder (no-credentials fallback) ────────────────────

def _placeholder_analysis(
    security_findings: list[RawSecurityFinding],
    dep_findings: list[RawDependencyFinding],
) -> AIAnalysis:
    """
    Fallback analysis used when watsonx.ai credentials are absent or the API
    is unavailable.  Produces a deterministic, human-readable summary from the
    raw findings so the report is still useful without AI.
    """
    n_sec = len(security_findings)
    n_dep = len(dep_findings)
    high_sev = [f for f in security_findings if f.severity in ("CRITICAL", "HIGH")]

    if n_sec == 0 and n_dep == 0:
        summary = "No security issues or vulnerable dependencies were detected."
    else:
        summary = (
            f"The scan detected {n_sec} security issue(s) and "
            f"{n_dep} dependency vulnerability(ies). "
        )
        if high_sev:
            summary += (
                "Notable high-severity findings include: "
                + "; ".join(f.message[:80] for f in high_sev[:3])
                + "."
            )

    suggestions = [
        {"index": i, "suggestion": f"Review and remediate: {f.message[:150]}"}
        for i, f in enumerate(security_findings[:_MAX_FIX_SUGGESTIONS])
    ]

    narrative = (
        "AI narrative unavailable — configure WATSONX_API_KEY and WATSONX_PROJECT_ID "
        "to enable intelligent code review summaries."
    )

    return AIAnalysis(
        summary=summary,
        fix_suggestions=suggestions,
        narrative=narrative,
    )
