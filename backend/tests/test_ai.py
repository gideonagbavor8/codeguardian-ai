"""
tests/test_ai.py
Comprehensive tests for the watsonx.ai analysis layer.

All tests use mocked responses — no real API key is required.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.ai.prompts import (
    AIAnalysis,
    _MAX_FINDINGS_IN_PROMPT,
    _MAX_FIX_SUGGESTIONS,
    _placeholder_analysis,
    _validate_fix_suggestions,
    build_analysis_prompt,
    parse_ai_response,
)
from app.services.scanner.base import RawDependencyFinding, RawSecurityFinding


# ── Shared fixtures ───────────────────────────────────────────

def _sec(severity: str = "HIGH", msg: str = "Bad code") -> RawSecurityFinding:
    return RawSecurityFinding(
        tool="bandit",
        rule_id="B001",
        severity=severity,
        confidence="HIGH",
        file_path="app.py",
        line_number=10,
        code_snippet="dangerous()",
        message=msg,
        cwe_id="CWE-89",
    )


def _dep(severity: str = "HIGH") -> RawDependencyFinding:
    return RawDependencyFinding(
        package_name="requests",
        installed_version="2.25.0",
        fixed_version="2.31.0",
        severity=severity,
        cve_ids=["CVE-2023-32681"],
        description="Proxy leak",
        ecosystem="pip",
    )


VALID_AI_JSON = json.dumps({
    "summary": "The code uses pickle which enables remote code execution.",
    "fix_suggestions": [
        {"index": 0, "suggestion": "Replace pickle.loads() with json.loads()."},
        {"index": 1, "suggestion": "Upgrade requests to >=2.31.0."},
    ],
    "narrative": "Two issues found; remediate before production deployment.",
})


# ═════════════════════════════════════════════════════════════
# 1. build_analysis_prompt
# ═════════════════════════════════════════════════════════════

class TestBuildAnalysisPrompt:
    def test_contains_security_findings(self):
        prompt = build_analysis_prompt([_sec()], [])
        assert "B001" in prompt
        assert "CWE-89" in prompt
        assert "Bad code" in prompt

    def test_contains_dependency_findings(self):
        prompt = build_analysis_prompt([], [_dep()])
        assert "requests" in prompt
        assert "CVE-2023-32681" in prompt
        assert "2.25.0" in prompt

    def test_none_blocks_when_empty(self):
        prompt = build_analysis_prompt([], [])
        assert "(none)" in prompt

    def test_prompt_requests_json(self):
        prompt = build_analysis_prompt([_sec()], [])
        assert '"summary"' in prompt
        assert '"fix_suggestions"' in prompt
        assert '"narrative"' in prompt

    def test_caps_findings_at_max(self):
        """Prompt must not include more than _MAX_FINDINGS_IN_PROMPT entries."""
        findings = [_sec(msg=f"issue {i}") for i in range(30)]
        prompt = build_analysis_prompt(findings, [])
        # Count bracketed indices [0], [1], … in the security section
        import re
        indices = re.findall(r"\[(\d+)\]", prompt)
        max_idx = max(int(i) for i in indices)
        assert max_idx < _MAX_FINDINGS_IN_PROMPT

    def test_finding_count_in_header_reflects_cap(self):
        findings = [_sec() for _ in range(25)]
        prompt = build_analysis_prompt(findings, [])
        assert f"SECURITY FINDINGS ({_MAX_FINDINGS_IN_PROMPT} total)" in prompt


# ═════════════════════════════════════════════════════════════
# 2. parse_ai_response
# ═════════════════════════════════════════════════════════════

class TestParseAiResponse:
    def test_parses_valid_json(self):
        result = parse_ai_response(VALID_AI_JSON)
        assert result.summary == "The code uses pickle which enables remote code execution."
        assert len(result.fix_suggestions) == 2
        assert result.fix_suggestions[0]["suggestion"] == "Replace pickle.loads() with json.loads()."
        assert result.narrative == "Two issues found; remediate before production deployment."

    def test_strips_markdown_json_fence(self):
        wrapped = f"```json\n{VALID_AI_JSON}\n```"
        result = parse_ai_response(wrapped)
        assert result.summary != ""
        assert len(result.fix_suggestions) == 2

    def test_strips_plain_code_fence(self):
        wrapped = f"```\n{VALID_AI_JSON}\n```"
        result = parse_ai_response(wrapped)
        assert result.summary != ""

    def test_extracts_json_from_prose_prefix(self):
        """Model sometimes prepends prose before the JSON block."""
        with_prose = f"Here is my analysis:\n{VALID_AI_JSON}\nEnd."
        result = parse_ai_response(with_prose)
        assert result.summary != ""
        assert len(result.fix_suggestions) == 2

    def test_empty_string_returns_fallback(self):
        result = parse_ai_response("")
        assert result.summary == ""
        assert result.narrative == "AI returned an empty response."
        assert result.fix_suggestions == []

    def test_whitespace_only_returns_fallback(self):
        result = parse_ai_response("   \n  ")
        assert "empty" in result.narrative.lower()

    def test_invalid_json_returns_fallback(self):
        result = parse_ai_response("THIS IS NOT JSON AT ALL")
        assert "could not be parsed" in result.narrative
        assert result.fix_suggestions == []

    def test_json_array_of_non_objects_returns_fallback(self):
        """A plain JSON array with no extractable object returns fallback."""
        result = parse_ai_response('["item1", "item2"]')
        # The regex extracts no {...} block from a pure string-array; falls through
        # to json.loads which parses a list, triggering the "not a JSON object" branch.
        assert "not a JSON object" in result.narrative

    def test_json_array_with_inner_object_extracts_it(self):
        """When the response is an array containing an object, the parser
        extracts the first {} block and uses it — this is graceful recovery."""
        result = parse_ai_response('[{"summary": "extracted", "fix_suggestions": [], "narrative": "n"}]')
        assert result.summary == "extracted"

    def test_missing_keys_return_empty_strings(self):
        result = parse_ai_response('{"summary": "s"}')
        assert result.summary == "s"
        assert result.narrative == ""
        assert result.fix_suggestions == []

    def test_fix_suggestions_with_missing_suggestion_key_dropped(self):
        data = {
            "summary": "s",
            "fix_suggestions": [
                {"index": 0},                          # no "suggestion" key → dropped
                {"index": 1, "suggestion": "fix it"},  # valid
            ],
            "narrative": "n",
        }
        result = parse_ai_response(json.dumps(data))
        assert len(result.fix_suggestions) == 1
        assert result.fix_suggestions[0]["suggestion"] == "fix it"

    def test_fix_suggestions_non_dict_items_dropped(self):
        data = {
            "summary": "s",
            "fix_suggestions": ["string", None, 42, {"index": 0, "suggestion": "ok"}],
            "narrative": "n",
        }
        result = parse_ai_response(json.dumps(data))
        assert len(result.fix_suggestions) == 1

    def test_fix_suggestions_capped_at_max(self):
        data = {
            "summary": "s",
            "fix_suggestions": [
                {"index": i, "suggestion": f"fix {i}"} for i in range(30)
            ],
            "narrative": "n",
        }
        result = parse_ai_response(json.dumps(data))
        assert len(result.fix_suggestions) <= _MAX_FIX_SUGGESTIONS

    def test_non_string_summary_coerced(self):
        """If the model returns a number for summary, coerce it to str."""
        data = {"summary": 42, "fix_suggestions": [], "narrative": "n"}
        result = parse_ai_response(json.dumps(data))
        assert result.summary == "42"

    def test_fix_suggestions_blank_suggestion_dropped(self):
        data = {
            "summary": "s",
            "fix_suggestions": [{"index": 0, "suggestion": "   "}],
            "narrative": "n",
        }
        result = parse_ai_response(json.dumps(data))
        assert result.fix_suggestions == []


# ═════════════════════════════════════════════════════════════
# 3. _validate_fix_suggestions
# ═════════════════════════════════════════════════════════════

class TestValidateFixSuggestions:
    def test_valid_list(self):
        raw = [{"index": 0, "suggestion": "do this"}]
        result = _validate_fix_suggestions(raw)
        assert len(result) == 1
        assert result[0]["index"] == 0

    def test_none_returns_empty(self):
        assert _validate_fix_suggestions(None) == []

    def test_string_returns_empty(self):
        assert _validate_fix_suggestions("not a list") == []

    def test_float_index_coerced_to_int(self):
        raw = [{"index": 1.0, "suggestion": "fix"}]
        result = _validate_fix_suggestions(raw)
        assert result[0]["index"] == 1

    def test_missing_index_uses_position(self):
        raw = [{"suggestion": "fix A"}, {"suggestion": "fix B"}]
        result = _validate_fix_suggestions(raw)
        assert result[0]["index"] == 0
        assert result[1]["index"] == 1


# ═════════════════════════════════════════════════════════════
# 4. _placeholder_analysis
# ═════════════════════════════════════════════════════════════

class TestPlaceholderAnalysis:
    def test_no_findings_clean_message(self):
        result = _placeholder_analysis([], [])
        assert "no security issues" in result.summary.lower()
        assert result.fix_suggestions == []

    def test_counts_in_summary(self):
        result = _placeholder_analysis([_sec()], [_dep()])
        assert "1 security issue" in result.summary
        assert "1 dependency" in result.summary

    def test_high_severity_message_in_summary(self):
        result = _placeholder_analysis([_sec("HIGH", "Pickle deserialization risk")], [])
        assert "Pickle" in result.summary

    def test_generates_suggestions_for_findings(self):
        findings = [_sec() for _ in range(3)]
        result = _placeholder_analysis(findings, [])
        assert len(result.fix_suggestions) == 3

    def test_narrative_mentions_credentials(self):
        result = _placeholder_analysis([], [])
        assert "WATSONX_API_KEY" in result.narrative

    def test_suggestions_capped_at_max(self):
        findings = [_sec() for _ in range(25)]
        result = _placeholder_analysis(findings, [])
        assert len(result.fix_suggestions) <= _MAX_FIX_SUGGESTIONS


# ═════════════════════════════════════════════════════════════
# 5. generate_analysis (async, mocked watsonx)
# ═════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_generate_analysis_no_credentials_returns_placeholder():
    """When credentials are empty, placeholder is returned immediately."""
    from app.services.ai.watsonx_client import generate_analysis
    with patch("app.services.ai.watsonx_client.settings") as mock_settings:
        mock_settings.WATSONX_API_KEY = ""
        mock_settings.WATSONX_PROJECT_ID = ""
        result = await generate_analysis([_sec()], [])
    assert isinstance(result, AIAnalysis)
    assert "WATSONX_API_KEY" in result.narrative


@pytest.mark.asyncio
async def test_generate_analysis_success_with_mocked_sdk():
    """Happy path: SDK returns valid JSON → AIAnalysis populated."""
    from app.services.ai.watsonx_client import generate_analysis

    with patch("app.services.ai.watsonx_client.settings") as mock_settings, \
         patch("app.services.ai.watsonx_client._call_watsonx_sync",
               return_value=VALID_AI_JSON) as mock_call:
        mock_settings.WATSONX_API_KEY = "test-key"
        mock_settings.WATSONX_PROJECT_ID = "test-project"
        mock_settings.WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
        mock_settings.WATSONX_MODEL_ID = "ibm/granite-13b-instruct-v2"

        result = await generate_analysis([_sec()], [_dep()])

    assert result.summary == "The code uses pickle which enables remote code execution."
    assert len(result.fix_suggestions) == 2
    assert result.narrative == "Two issues found; remediate before production deployment."
    mock_call.assert_called_once()


@pytest.mark.asyncio
async def test_generate_analysis_timeout_returns_placeholder():
    """asyncio.TimeoutError → placeholder, no exception raised."""
    from app.services.ai.watsonx_client import generate_analysis

    async def _slow_executor(*args, **kwargs):
        raise asyncio.TimeoutError()

    with patch("app.services.ai.watsonx_client.settings") as mock_settings, \
         patch("app.services.ai.watsonx_client.asyncio.wait_for",
               side_effect=asyncio.TimeoutError()):
        mock_settings.WATSONX_API_KEY = "key"
        mock_settings.WATSONX_PROJECT_ID = "proj"
        result = await generate_analysis([_sec()], [])

    assert isinstance(result, AIAnalysis)
    assert result.fix_suggestions != []   # placeholder generates suggestions


@pytest.mark.asyncio
async def test_generate_analysis_import_error_returns_placeholder():
    """Missing SDK → placeholder."""
    from app.services.ai.watsonx_client import _WatsonxImportError, generate_analysis

    with patch("app.services.ai.watsonx_client.settings") as mock_settings, \
         patch("app.services.ai.watsonx_client.asyncio.wait_for",
               side_effect=_WatsonxImportError("No module named ibm_watsonx_ai")):
        mock_settings.WATSONX_API_KEY = "key"
        mock_settings.WATSONX_PROJECT_ID = "proj"
        result = await generate_analysis([_sec()], [])

    assert isinstance(result, AIAnalysis)


@pytest.mark.asyncio
async def test_generate_analysis_auth_error_returns_placeholder():
    """401/403 from API → placeholder."""
    from app.services.ai.watsonx_client import _WatsonxAuthError, generate_analysis

    with patch("app.services.ai.watsonx_client.settings") as mock_settings, \
         patch("app.services.ai.watsonx_client.asyncio.wait_for",
               side_effect=_WatsonxAuthError("401 Unauthorized")):
        mock_settings.WATSONX_API_KEY = "bad-key"
        mock_settings.WATSONX_PROJECT_ID = "proj"
        result = await generate_analysis([_sec()], [])

    assert isinstance(result, AIAnalysis)


@pytest.mark.asyncio
async def test_generate_analysis_api_error_returns_placeholder():
    """Generic API error → placeholder."""
    from app.services.ai.watsonx_client import _WatsonxAPIError, generate_analysis

    with patch("app.services.ai.watsonx_client.settings") as mock_settings, \
         patch("app.services.ai.watsonx_client.asyncio.wait_for",
               side_effect=_WatsonxAPIError("500 Internal Server Error")):
        mock_settings.WATSONX_API_KEY = "key"
        mock_settings.WATSONX_PROJECT_ID = "proj"
        result = await generate_analysis([_sec()], [])

    assert isinstance(result, AIAnalysis)


@pytest.mark.asyncio
async def test_generate_analysis_malformed_response_uses_fallback():
    """Valid API call but model returns garbage → fallback AIAnalysis."""
    from app.services.ai.watsonx_client import generate_analysis

    with patch("app.services.ai.watsonx_client.settings") as mock_settings, \
         patch("app.services.ai.watsonx_client._call_watsonx_sync",
               return_value="I cannot answer that."):
        mock_settings.WATSONX_API_KEY = "key"
        mock_settings.WATSONX_PROJECT_ID = "proj"
        mock_settings.WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
        mock_settings.WATSONX_MODEL_ID = "ibm/granite-13b-instruct-v2"
        result = await generate_analysis([_sec()], [])

    # parse_ai_response fallback: summary contains the raw text
    assert "could not be parsed" in result.narrative
    assert result.fix_suggestions == []


@pytest.mark.asyncio
async def test_generate_analysis_empty_response_uses_fallback():
    """Model returns empty string → fallback."""
    from app.services.ai.watsonx_client import generate_analysis

    with patch("app.services.ai.watsonx_client.settings") as mock_settings, \
         patch("app.services.ai.watsonx_client._call_watsonx_sync", return_value=""):
        mock_settings.WATSONX_API_KEY = "key"
        mock_settings.WATSONX_PROJECT_ID = "proj"
        mock_settings.WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
        mock_settings.WATSONX_MODEL_ID = "ibm/granite-13b-instruct-v2"
        result = await generate_analysis([], [])

    assert "empty" in result.narrative.lower()


@pytest.mark.asyncio
async def test_generate_analysis_does_not_mutate_findings():
    """Scanner findings list must not be modified by the AI layer."""
    from app.services.ai.watsonx_client import generate_analysis

    original_findings = [_sec("HIGH"), _sec("MEDIUM")]
    original_ids = [id(f) for f in original_findings]

    with patch("app.services.ai.watsonx_client.settings") as mock_settings, \
         patch("app.services.ai.watsonx_client._call_watsonx_sync",
               return_value=VALID_AI_JSON):
        mock_settings.WATSONX_API_KEY = "key"
        mock_settings.WATSONX_PROJECT_ID = "proj"
        mock_settings.WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
        mock_settings.WATSONX_MODEL_ID = "ibm/granite-13b-instruct-v2"
        await generate_analysis(original_findings, [])

    # Same objects, same order — nothing mutated
    assert [id(f) for f in original_findings] == original_ids
    assert original_findings[0].severity == "HIGH"
    assert original_findings[1].severity == "MEDIUM"


# ═════════════════════════════════════════════════════════════
# 6. _call_watsonx_sync
# ═════════════════════════════════════════════════════════════

class TestCallWatsonxSync:
    def test_raises_import_error_when_sdk_missing(self):
        """If ibm_watsonx_ai is not importable, raises _WatsonxImportError."""
        from app.services.ai.watsonx_client import _WatsonxImportError, _call_watsonx_sync

        with patch("builtins.__import__", side_effect=ImportError("no module")):
            with pytest.raises(_WatsonxImportError):
                _call_watsonx_sync("test prompt")

    def test_raises_auth_error_for_401(self):
        from app.services.ai.watsonx_client import _WatsonxAuthError, _call_watsonx_sync

        # Mock the SDK classes inside the function scope
        mock_model = MagicMock()
        mock_model.generate.side_effect = Exception("401 Unauthorized — invalid api key")

        with patch.dict("sys.modules", {
            "ibm_watsonx_ai": MagicMock(),
            "ibm_watsonx_ai.foundation_models": MagicMock(),
            "ibm_watsonx_ai.metanames": MagicMock(),
        }):
            import sys
            mock_pkg = sys.modules["ibm_watsonx_ai"]
            mock_pkg.Credentials.return_value = MagicMock()
            mock_pkg.APIClient.return_value = MagicMock()

            mock_fm = sys.modules["ibm_watsonx_ai.foundation_models"]
            mock_fm.ModelInference.return_value = mock_model

            mock_meta = sys.modules["ibm_watsonx_ai.metanames"]
            mock_meta.GenTextParamsMetaNames.MAX_NEW_TOKENS = "max_new_tokens"
            mock_meta.GenTextParamsMetaNames.TEMPERATURE = "temperature"
            mock_meta.GenTextParamsMetaNames.STOP_SEQUENCES = "stop_sequences"

            with patch("app.services.ai.watsonx_client.settings") as s:
                s.WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
                s.WATSONX_API_KEY = "key"
                s.WATSONX_PROJECT_ID = "proj"
                s.WATSONX_MODEL_ID = "ibm/granite-13b-instruct-v2"

                with pytest.raises(_WatsonxAuthError):
                    _call_watsonx_sync("prompt")

    def test_raises_api_error_for_generic_exception(self):
        from app.services.ai.watsonx_client import _WatsonxAPIError, _call_watsonx_sync

        mock_model = MagicMock()
        mock_model.generate.side_effect = Exception("500 Internal Server Error")

        with patch.dict("sys.modules", {
            "ibm_watsonx_ai": MagicMock(),
            "ibm_watsonx_ai.foundation_models": MagicMock(),
            "ibm_watsonx_ai.metanames": MagicMock(),
        }):
            import sys
            mock_pkg = sys.modules["ibm_watsonx_ai"]
            mock_pkg.Credentials.return_value = MagicMock()
            mock_pkg.APIClient.return_value = MagicMock()

            mock_fm = sys.modules["ibm_watsonx_ai.foundation_models"]
            mock_fm.ModelInference.return_value = mock_model

            mock_meta = sys.modules["ibm_watsonx_ai.metanames"]
            mock_meta.GenTextParamsMetaNames.MAX_NEW_TOKENS = "max_new_tokens"
            mock_meta.GenTextParamsMetaNames.TEMPERATURE = "temperature"
            mock_meta.GenTextParamsMetaNames.STOP_SEQUENCES = "stop_sequences"

            with patch("app.services.ai.watsonx_client.settings") as s:
                s.WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
                s.WATSONX_API_KEY = "key"
                s.WATSONX_PROJECT_ID = "proj"
                s.WATSONX_MODEL_ID = "ibm/granite-13b-instruct-v2"

                with pytest.raises(_WatsonxAPIError):
                    _call_watsonx_sync("prompt")

    def test_returns_generated_text_on_success(self):
        from app.services.ai.watsonx_client import _call_watsonx_sync

        mock_model = MagicMock()
        mock_model.generate.return_value = {
            "results": [{"generated_text": VALID_AI_JSON}]
        }

        with patch.dict("sys.modules", {
            "ibm_watsonx_ai": MagicMock(),
            "ibm_watsonx_ai.foundation_models": MagicMock(),
            "ibm_watsonx_ai.metanames": MagicMock(),
        }):
            import sys
            mock_pkg = sys.modules["ibm_watsonx_ai"]
            mock_pkg.Credentials.return_value = MagicMock()
            mock_pkg.APIClient.return_value = MagicMock()

            mock_fm = sys.modules["ibm_watsonx_ai.foundation_models"]
            mock_fm.ModelInference.return_value = mock_model

            mock_meta = sys.modules["ibm_watsonx_ai.metanames"]
            mock_meta.GenTextParamsMetaNames.MAX_NEW_TOKENS = "max_new_tokens"
            mock_meta.GenTextParamsMetaNames.TEMPERATURE = "temperature"
            mock_meta.GenTextParamsMetaNames.STOP_SEQUENCES = "stop_sequences"

            with patch("app.services.ai.watsonx_client.settings") as s:
                s.WATSONX_URL = "https://us-south.ml.cloud.ibm.com"
                s.WATSONX_API_KEY = "key"
                s.WATSONX_PROJECT_ID = "proj"
                s.WATSONX_MODEL_ID = "ibm/granite-13b-instruct-v2"

                result = _call_watsonx_sync("prompt")

        assert result == VALID_AI_JSON
