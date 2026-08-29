"""
app/services/ai/watsonx_client.py
IBM watsonx.ai SDK wrapper for generating code analysis.

Design principles:
- Credentials are read exclusively from app.config.settings — never hardcoded.
- The blocking SDK call runs in a thread-pool executor to avoid blocking the
  asyncio event loop.
- Each error category (missing credentials, import failure, timeout, API error,
  parse failure) is handled separately and logged with enough context to diagnose.
- The public generate_analysis() function never raises; it always returns an
  AIAnalysis (real or placeholder).
- Scanner findings passed in are never mutated.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.config import settings
from app.services.ai.prompts import (
    AIAnalysis,
    _placeholder_analysis,
    build_analysis_prompt,
    parse_ai_response,
)
from app.services.scanner.base import RawDependencyFinding, RawSecurityFinding

logger = logging.getLogger(__name__)

# Timeout (seconds) for a single watsonx.ai generate() call.
_WATSONX_TIMEOUT_SECONDS = 60


async def generate_analysis(
    security_findings: list[RawSecurityFinding],
    dep_findings: list[RawDependencyFinding],
) -> AIAnalysis:
    """
    Build a prompt, call watsonx.ai, parse the response, and return an
    AIAnalysis.  Falls back to a placeholder on any error.

    This coroutine is safe to await from the scan pipeline — the blocking
    SDK call is dispatched to a thread-pool executor.
    """
    if not settings.WATSONX_API_KEY or not settings.WATSONX_PROJECT_ID:
        logger.warning(
            "watsonx.ai credentials not configured "
            "(WATSONX_API_KEY / WATSONX_PROJECT_ID) — using placeholder analysis."
        )
        return _placeholder_analysis(security_findings, dep_findings)

    prompt = build_analysis_prompt(security_findings, dep_findings)

    try:
        raw_text = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None,
                _call_watsonx_sync,
                prompt,
            ),
            timeout=_WATSONX_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "watsonx.ai call timed out after %d s — using placeholder analysis.",
            _WATSONX_TIMEOUT_SECONDS,
        )
        return _placeholder_analysis(security_findings, dep_findings)
    except _WatsonxImportError as exc:
        logger.error("ibm-watsonx-ai SDK not installed: %s — using placeholder.", exc)
        return _placeholder_analysis(security_findings, dep_findings)
    except _WatsonxAuthError as exc:
        logger.error("watsonx.ai authentication failed: %s — using placeholder.", exc)
        return _placeholder_analysis(security_findings, dep_findings)
    except _WatsonxAPIError as exc:
        logger.error("watsonx.ai API error: %s — using placeholder.", exc)
        return _placeholder_analysis(security_findings, dep_findings)
    except Exception as exc:
        logger.error(
            "Unexpected error calling watsonx.ai: %s — using placeholder.", exc,
            exc_info=True,
        )
        return _placeholder_analysis(security_findings, dep_findings)

    analysis = parse_ai_response(raw_text)
    logger.info(
        "watsonx.ai analysis complete — summary_len=%d suggestions=%d",
        len(analysis.summary),
        len(analysis.fix_suggestions),
    )
    return analysis


# ── Internal sync call (runs in executor) ─────────────────────

class _WatsonxImportError(RuntimeError):
    """Raised when the ibm-watsonx-ai package is not installed."""


class _WatsonxAuthError(RuntimeError):
    """Raised when watsonx.ai rejects the credentials."""


class _WatsonxAPIError(RuntimeError):
    """Raised for other non-auth API-level errors."""


def _call_watsonx_sync(prompt: str) -> str:
    """
    Synchronous wrapper around the ibm-watsonx-ai SDK.
    Runs inside a thread-pool executor — do NOT call directly from async code.

    Returns the raw generated text string.
    Raises typed exceptions so the async caller can handle each case.
    """
    try:
        from ibm_watsonx_ai import APIClient, Credentials
        from ibm_watsonx_ai.foundation_models import ModelInference
        from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    except ImportError as exc:
        raise _WatsonxImportError(str(exc)) from exc

    try:
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
        raw_text: str = response.get("results", [{}])[0].get("generated_text", "")
        return raw_text

    except Exception as exc:
        exc_str = str(exc).lower()
        # Surface auth errors distinctly so they can be logged more helpfully
        if any(k in exc_str for k in ("401", "403", "unauthorized", "forbidden", "api key")):
            raise _WatsonxAuthError(str(exc)) from exc
        raise _WatsonxAPIError(str(exc)) from exc
