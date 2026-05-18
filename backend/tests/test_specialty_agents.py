"""
Unit tests for the four Specialty Agents (Radiology, Oncology, Cardiology, Pharmacy).

Tests cover:
- Successful analysis returning valid SpecialtyFindings
- Correct specialty name on each agent
- SpecialtyAgentError raised on GeminiServiceError
- SpecialtyAgentError raised on malformed JSON
- SpecialtyAgentError raised when required fields are missing
- Markdown code-fence stripping in responses
"""

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out google.generativeai before any backend imports so that the tests
# work even when the package is not installed or incompatible with the current
# Python version (e.g. Python 3.14 + protobuf C extension issues).
# ---------------------------------------------------------------------------
_google_mod = ModuleType("google")
_genai_mod = ModuleType("google.generativeai")
_genai_mod.configure = MagicMock()
_genai_mod.GenerativeModel = MagicMock()
sys.modules.setdefault("google", _google_mod)
sys.modules["google.generativeai"] = _genai_mod

from backend.agents.base import SpecialtyAgentBase, SpecialtyAgentError  # noqa: E402
from backend.agents.cardiology import CardiologyAgent  # noqa: E402
from backend.agents.oncology import OncologyAgent  # noqa: E402
from backend.agents.pharmacy import PharmacyAgent  # noqa: E402
from backend.agents.radiology import RadiologyAgent  # noqa: E402
from backend.schemas import SpecialtyFindings  # noqa: E402
from backend.services.gemini import GeminiServiceError  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_RESPONSES = {
    "radiology": json.dumps(
        {
            "specialty": "radiology",
            "summary": "Chest X-ray shows bilateral infiltrates.",
            "action_items": ["Order CT chest", "Consult pulmonology"],
        }
    ),
    "oncology": json.dumps(
        {
            "specialty": "oncology",
            "summary": "Elevated CA-125 warrants further workup.",
            "action_items": ["Order PET scan", "Refer to oncology MDT"],
        }
    ),
    "cardiology": json.dumps(
        {
            "specialty": "cardiology",
            "summary": "ST-elevation in leads II, III, aVF.",
            "action_items": ["Activate cath lab", "Administer aspirin 300 mg"],
        }
    ),
    "pharmacy": json.dumps(
        {
            "specialty": "pharmacy",
            "summary": "Warfarin and amiodarone interaction detected.",
            "action_items": ["Reduce warfarin dose by 30-50%", "Monitor INR closely"],
        }
    ),
}

AGENT_CLASSES = {
    "radiology": RadiologyAgent,
    "oncology": OncologyAgent,
    "cardiology": CardiologyAgent,
    "pharmacy": PharmacyAgent,
}


def make_agent(specialty: str, mock_response: str):
    """Return an agent instance with a mocked GeminiService."""
    mock_gemini = MagicMock()
    mock_gemini.generate.return_value = mock_response
    return AGENT_CLASSES[specialty](gemini_service=mock_gemini)


# ---------------------------------------------------------------------------
# Tests: SpecialtyAgentBase contract
# ---------------------------------------------------------------------------


def test_all_agents_are_subclasses_of_base():
    for cls in AGENT_CLASSES.values():
        assert issubclass(cls, SpecialtyAgentBase)


def test_specialty_class_attributes():
    assert RadiologyAgent.specialty == "radiology"
    assert OncologyAgent.specialty == "oncology"
    assert CardiologyAgent.specialty == "cardiology"
    assert PharmacyAgent.specialty == "pharmacy"


# ---------------------------------------------------------------------------
# Tests: Successful analysis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("specialty", list(AGENT_CLASSES.keys()))
def test_analyze_returns_specialty_findings(specialty):
    agent = make_agent(specialty, VALID_RESPONSES[specialty])
    result = agent.analyze("Patient with chest pain.", ["Guideline A", "Guideline B"])

    assert isinstance(result, SpecialtyFindings)
    assert result.specialty == specialty
    assert isinstance(result.summary, str) and result.summary
    assert isinstance(result.action_items, list)


@pytest.mark.parametrize("specialty", list(AGENT_CLASSES.keys()))
def test_analyze_passes_case_summary_to_gemini(specialty):
    mock_gemini = MagicMock()
    mock_gemini.generate.return_value = VALID_RESPONSES[specialty]
    agent = AGENT_CLASSES[specialty](gemini_service=mock_gemini)

    case_summary = "72-year-old male with chest pain and shortness of breath."
    agent.analyze(case_summary, [])

    call_args = mock_gemini.generate.call_args
    prompt_sent = call_args[0][0]  # first positional arg
    assert case_summary in prompt_sent


@pytest.mark.parametrize("specialty", list(AGENT_CLASSES.keys()))
def test_analyze_includes_guidelines_in_prompt(specialty):
    mock_gemini = MagicMock()
    mock_gemini.generate.return_value = VALID_RESPONSES[specialty]
    agent = AGENT_CLASSES[specialty](gemini_service=mock_gemini)

    guidelines = ["Use ACE inhibitors for heart failure", "Monitor renal function"]
    agent.analyze("Some case.", guidelines)

    prompt_sent = mock_gemini.generate.call_args[0][0]
    for guideline in guidelines:
        assert guideline in prompt_sent


@pytest.mark.parametrize("specialty", list(AGENT_CLASSES.keys()))
def test_analyze_with_empty_guidelines(specialty):
    agent = make_agent(specialty, VALID_RESPONSES[specialty])
    result = agent.analyze("Patient case.", [])
    assert isinstance(result, SpecialtyFindings)


# ---------------------------------------------------------------------------
# Tests: Error handling — GeminiServiceError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("specialty", list(AGENT_CLASSES.keys()))
def test_analyze_raises_specialty_agent_error_on_gemini_failure(specialty):
    mock_gemini = MagicMock()
    mock_gemini.generate.side_effect = GeminiServiceError("API quota exceeded")
    agent = AGENT_CLASSES[specialty](gemini_service=mock_gemini)

    with pytest.raises(SpecialtyAgentError) as exc_info:
        agent.analyze("Patient case.", [])

    assert exc_info.value.specialty == specialty
    assert exc_info.value.detail  # non-empty detail


# ---------------------------------------------------------------------------
# Tests: Error handling — malformed JSON
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("specialty", list(AGENT_CLASSES.keys()))
def test_analyze_raises_specialty_agent_error_on_malformed_json(specialty):
    agent = make_agent(specialty, "This is not JSON at all.")

    with pytest.raises(SpecialtyAgentError) as exc_info:
        agent.analyze("Patient case.", [])

    assert exc_info.value.specialty == specialty
    assert "parse" in exc_info.value.detail.lower() or "json" in exc_info.value.detail.lower()


# ---------------------------------------------------------------------------
# Tests: Error handling — missing required fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("specialty", list(AGENT_CLASSES.keys()))
@pytest.mark.parametrize("missing_field", ["specialty", "summary", "action_items"])
def test_analyze_raises_error_when_field_missing(specialty, missing_field):
    data = {
        "specialty": specialty,
        "summary": "Some summary.",
        "action_items": ["Do something"],
    }
    del data[missing_field]
    agent = make_agent(specialty, json.dumps(data))

    with pytest.raises(SpecialtyAgentError) as exc_info:
        agent.analyze("Patient case.", [])

    assert exc_info.value.specialty == specialty
    assert missing_field in exc_info.value.detail


# ---------------------------------------------------------------------------
# Tests: Markdown code-fence stripping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("specialty", list(AGENT_CLASSES.keys()))
def test_analyze_strips_markdown_code_fences(specialty):
    raw_data = {
        "specialty": specialty,
        "summary": "Summary with code fence.",
        "action_items": ["Action 1"],
    }
    fenced_response = f"```json\n{json.dumps(raw_data)}\n```"
    agent = make_agent(specialty, fenced_response)

    result = agent.analyze("Patient case.", [])
    assert result.specialty == specialty
    assert result.summary == "Summary with code fence."


# ---------------------------------------------------------------------------
# Tests: SpecialtyAgentError attributes
# ---------------------------------------------------------------------------


def test_specialty_agent_error_attributes():
    err = SpecialtyAgentError(specialty="radiology", detail="Something went wrong")
    assert err.specialty == "radiology"
    assert err.detail == "Something went wrong"
    assert "radiology" in str(err)
    assert "Something went wrong" in str(err)
