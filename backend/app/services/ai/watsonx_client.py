"""
app/services/ai/watsonx_client.py
IBM watsonx.ai SDK wrapper for generating code analysis.
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.services.ai.prompts import AIAnalysis, build_analysis_prompt, parse_ai_response
from app.services.scanner.base import RawDependencyFinding, RawSecurityFinding

logger = logging.getLogger(__name__)


async def generate_analysis(
    security_findings: list[RawSecurityFinding],
    dep_findings: list[RawDependencyFinding],
) -> AIAnalysis:
    """
    Build a prompt from findings, call watsonx.ai, and return parsed AIAnalysis.
    Falls back to a placeholder analysis if the API is unavailable.
    """
    if not settings.WATSONX_API_KEY or not settings.WATSONX_PROJECT_ID:
        logger.warning("watsonx.ai credentials not set — returning placeholder analysis.")
        return _placeholder_analysis(security_findings, dep_findings)

    prompt = build_analysis_prompt(security_findings, dep_findings)

    try:
        # Import here to avoid import errors if the package is not installed
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference
        from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams

        credentials = Credentials(
            url=settings.WATSONX_URL,
            api_key=settings.WATSONX_API_KEY,
        )
        client = APIClient(credentials)

        model = ModelInference(
            model_id=settings.WATSONX_MODEL_ID,
            api_client=client,
            project_id=settings.WATSONX_PROJECT_ID,
            params={
                GenParams.MAX_NEW_TOKENS: 1024,
                GenParams.TEMPERATURE: 0.1,
                GenParams.STOP_SEQUENCES: ["```"],
            },
        )

        response: dict[str, Any] = model.generate(prompt=prompt)
        raw_text: str = (
            response.get("results", [{}])[0].get("generated_text", "")
        )
        return parse_ai_response(raw_text)

    except Exception as exc:
        logger.error("watsonx.ai call failed: %s", exc, exc_info=True)
        return _placeholder_analysis(security_findings, dep_findings)


def _placeholder_analysis(
    security_findings: list[RawSecurityFinding],
    dep_findings: list[RawDependencyFinding],
) -> AIAnalysis:
    """Fallback analysis used when watsonx.ai is unavailable."""
    n_sec = len(security_findings)
    n_dep = len(dep_findings)
    high_sev = [f for f in security_findings if f.severity in ("CRITICAL", "HIGH")]

    summary = (
        f"The scan detected {n_sec} security issue(s) and {n_dep} dependency vulnerability(ies). "
    )
    if high_sev:
        summary += (
            f"Notable high-severity findings include: "
            + "; ".join(f.message[:80] for f in high_sev[:3])
            + "."
        )
    elif n_sec == 0 and n_dep == 0:
        summary = "No security issues or vulnerable dependencies were detected."

    suggestions = [
        {"index": i, "suggestion": f"Review and remediate: {f.message[:150]}"}
        for i, f in enumerate(security_findings[:10])
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
