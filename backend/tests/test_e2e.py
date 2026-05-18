"""
End-to-end tests for the CareFlow Orchestrator pipeline.

Loads each of the 3 sample cases from ``data/sample_cases.json``, calls
``run_orchestration()`` with mocked Gemini responses, and verifies that the
returned ``CarePlan`` is structurally valid.

Validates: Requirements 6.1, 6.2, 6.3
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict
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

from backend.schemas import CarePlan, OrchestrateRequest  # noqa: E402
from backend.services.crew import run_orchestration  # noqa: E402

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent.parent / "data"
_SAMPLE_CASES_PATH = _DATA_DIR / "sample_cases.json"
_GUIDELINES_PATH = _DATA_DIR / "guidelines.json"


# ---------------------------------------------------------------------------
# Helpers — build mock Gemini responses
# ---------------------------------------------------------------------------


def _make_orchestrator_response(specialties: list[str]) -> str:
    """Return a JSON string mimicking the Orchestrator Agent's Gemini output."""
    return json.dumps(
        {
            "specialties": specialties,
            "summary": "Mock clinical summary for end-to-end test.",
            "key_findings": ["Finding A", "Finding B"],
        }
    )


def _make_specialty_response(specialty: str) -> str:
    """Return a JSON string mimicking a Specialty Agent's Gemini output."""
    return json.dumps(
        {
            "specialty": specialty,
            "summary": f"Mock {specialty} summary for e2e test.",
            "action_items": [f"Action 1 for {specialty}", f"Action 2 for {specialty}"],
        }
    )


def _make_coordinator_response(specialties: list[str]) -> str:
    """Return a JSON string mimicking the Coordinator Agent's Gemini output."""
    timeline = [
        {
            "timestamp": "2024-01-01T10:00:00Z",
            "specialty": s,
            "description": f"Mock {s} finding.",
        }
        for s in specialties
    ]
    recommendations = [f"Recommendation for {s}" for s in specialties]
    alerts = ["Mock alert: review all findings carefully."]
    return json.dumps(
        {
            "timeline": timeline,
            "recommendations": recommendations,
            "alerts": alerts,
        }
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def sample_cases() -> list[dict]:
    """Load sample cases from data/sample_cases.json."""
    assert _SAMPLE_CASES_PATH.exists(), (
        f"sample_cases.json not found at {_SAMPLE_CASES_PATH}"
    )
    with _SAMPLE_CASES_PATH.open(encoding="utf-8") as fh:
        cases = json.load(fh)
    assert isinstance(cases, list), "sample_cases.json must be a JSON array"
    return cases


@pytest.fixture(scope="module")
def guidelines() -> dict:
    """Load guidelines from data/guidelines.json."""
    assert _GUIDELINES_PATH.exists(), (
        f"guidelines.json not found at {_GUIDELINES_PATH}"
    )
    with _GUIDELINES_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), "guidelines.json must be a JSON object"
    return data


# ---------------------------------------------------------------------------
# Smoke tests — data files
# ---------------------------------------------------------------------------


def test_sample_cases_file_has_at_least_three_cases(sample_cases):
    """Requirement 6.3: at least three sample cases must exist."""
    assert len(sample_cases) >= 3, (
        f"Expected at least 3 sample cases, found {len(sample_cases)}"
    )


def test_sample_cases_have_required_fields(sample_cases):
    """Each sample case must have id, title, specialties, and text fields."""
    for case in sample_cases:
        assert "id" in case, f"Case missing 'id': {case}"
        assert "title" in case, f"Case missing 'title': {case}"
        assert "specialties" in case, f"Case missing 'specialties': {case}"
        assert "text" in case, f"Case missing 'text': {case}"
        assert isinstance(case["specialties"], list), (
            f"'specialties' must be a list in case {case['id']}"
        )
        assert len(case["specialties"]) >= 1, (
            f"Case {case['id']} must have at least one specialty"
        )
        assert isinstance(case["text"], str) and case["text"].strip(), (
            f"Case {case['id']} must have non-empty text"
        )


def test_sample_cases_cover_different_specialty_combinations(sample_cases):
    """Requirement 6.3: cases should cover different specialty combinations."""
    specialty_sets = [frozenset(c["specialties"]) for c in sample_cases]
    # All three cases should have distinct specialty combinations
    assert len(set(specialty_sets)) >= 2, (
        "Sample cases should cover at least 2 different specialty combinations"
    )


def test_guidelines_file_has_all_four_specialties(guidelines):
    """Guidelines must include entries for all four supported specialties."""
    required = {"radiology", "oncology", "cardiology", "pharmacy"}
    missing = required - set(guidelines.keys())
    assert not missing, f"guidelines.json is missing specialties: {missing}"


# ---------------------------------------------------------------------------
# End-to-end orchestration tests — one per sample case
# ---------------------------------------------------------------------------


def _run_e2e_for_case(case: dict, guidelines: dict) -> CarePlan:
    """Run orchestration for a single sample case with mocked Gemini.

    Uses dependency injection (``orchestrator_agent`` and ``coordinator_agent``
    parameters of ``run_orchestration``) so that no real GeminiService is
    instantiated and no API key is required.

    The mock Gemini responses are:
    - Orchestrator Agent: returns a valid decomposition for the case's specialties.
    - Specialty Agents: each returns valid structured findings.
    - Coordinator Agent: returns a valid timeline/recommendations/alerts response.

    Returns the resulting CarePlan.
    """
    from backend.agents.coordinator import CoordinatorAgent
    from backend.agents.orchestrator import OrchestratorAgent

    specialties: list[str] = case["specialties"]

    # ── Mock Gemini for the Orchestrator Agent ──────────────────────────────
    orchestrator_gemini = MagicMock()
    orchestrator_gemini.generate.return_value = _make_orchestrator_response(specialties)
    mock_orchestrator = OrchestratorAgent(gemini_service=orchestrator_gemini)

    # ── Mock Gemini for the Coordinator Agent ───────────────────────────────
    coordinator_gemini = MagicMock()
    coordinator_gemini.generate.return_value = _make_coordinator_response(specialties)
    mock_coordinator = CoordinatorAgent(gemini_service=coordinator_gemini)

    # ── Mock Gemini for each Specialty Agent ────────────────────────────────
    # Patch the GeminiService constructor so that specialty agents created
    # inside run_orchestration receive a mock instead of a real service.
    specialty_call_counter: dict[str, int] = {}

    def _mock_specialty_generate(prompt: str, image_b64=None) -> str:
        # Determine which specialty is being called by inspecting the prompt.
        for s in specialties:
            if s in prompt.lower():
                return _make_specialty_response(s)
        # Fallback: return a generic specialty response
        return _make_specialty_response(specialties[0])

    mock_specialty_gemini = MagicMock()
    mock_specialty_gemini.generate.side_effect = _mock_specialty_generate

    with patch(
        "backend.services.gemini.GeminiService.__init__",
        return_value=None,
    ), patch(
        "backend.services.gemini.GeminiService.generate",
        side_effect=_mock_specialty_generate,
    ):
        request = OrchestrateRequest(
            text=case["text"],
            case_id=case["id"],
        )
        care_plan = run_orchestration(
            request,
            guidelines,
            orchestrator_agent=mock_orchestrator,
            coordinator_agent=mock_coordinator,
        )

    return care_plan


def _assert_care_plan_structurally_valid(care_plan: CarePlan, case: dict) -> None:
    """Assert that a CarePlan has all required structural fields."""
    assert isinstance(care_plan, CarePlan), (
        f"run_orchestration() must return a CarePlan, got {type(care_plan)}"
    )
    assert isinstance(care_plan.case_id, str) and care_plan.case_id, (
        "care_plan.case_id must be a non-empty string"
    )
    assert isinstance(care_plan.timeline, list), (
        "care_plan.timeline must be a list"
    )
    assert isinstance(care_plan.recommendations, list), (
        "care_plan.recommendations must be a list"
    )
    assert isinstance(care_plan.alerts, list), (
        "care_plan.alerts must be a list"
    )
    assert isinstance(care_plan.findings, dict), (
        "care_plan.findings must be a dict"
    )

    # Each finding must be structurally valid
    for specialty, findings in care_plan.findings.items():
        assert isinstance(specialty, str) and specialty, (
            "findings key must be a non-empty string"
        )
        assert isinstance(findings.specialty, str) and findings.specialty, (
            f"findings[{specialty}].specialty must be non-empty"
        )
        assert isinstance(findings.summary, str) and findings.summary, (
            f"findings[{specialty}].summary must be non-empty"
        )
        assert isinstance(findings.action_items, list), (
            f"findings[{specialty}].action_items must be a list"
        )


def test_e2e_sample_case_1(sample_cases, guidelines):
    """
    End-to-end test for sample case 1 (Chest Pain with Imaging).

    Loads sample-1, runs orchestration with mocked Gemini, and verifies
    the returned CarePlan is structurally valid.

    Validates: Requirements 6.1, 6.2, 6.3
    """
    case = next((c for c in sample_cases if c["id"] == "sample-1"), None)
    assert case is not None, "sample-1 not found in sample_cases.json"

    care_plan = _run_e2e_for_case(case, guidelines)
    _assert_care_plan_structurally_valid(care_plan, case)

    # Case-specific assertions: cardiology and radiology should be in findings
    assert "cardiology" in care_plan.findings or "radiology" in care_plan.findings, (
        "sample-1 should produce cardiology or radiology findings"
    )


def test_e2e_sample_case_2(sample_cases, guidelines):
    """
    End-to-end test for sample case 2 (Lung Mass with Medication Review).

    Loads sample-2, runs orchestration with mocked Gemini, and verifies
    the returned CarePlan is structurally valid.

    Validates: Requirements 6.1, 6.2, 6.3
    """
    case = next((c for c in sample_cases if c["id"] == "sample-2"), None)
    assert case is not None, "sample-2 not found in sample_cases.json"

    care_plan = _run_e2e_for_case(case, guidelines)
    _assert_care_plan_structurally_valid(care_plan, case)

    # Case-specific assertions: radiology, oncology, or pharmacy should appear
    expected = {"radiology", "oncology", "pharmacy"}
    assert expected & set(care_plan.findings.keys()), (
        "sample-2 should produce radiology, oncology, or pharmacy findings"
    )


def test_e2e_sample_case_3(sample_cases, guidelines):
    """
    End-to-end test for sample case 3 (Multi-Specialty Complex Case).

    Loads sample-3, runs orchestration with mocked Gemini, and verifies
    the returned CarePlan is structurally valid.

    Validates: Requirements 6.1, 6.2, 6.3
    """
    case = next((c for c in sample_cases if c["id"] == "sample-3"), None)
    assert case is not None, "sample-3 not found in sample_cases.json"

    care_plan = _run_e2e_for_case(case, guidelines)
    _assert_care_plan_structurally_valid(care_plan, case)

    # sample-3 covers all four specialties — at least 2 should appear
    all_specialties = {"cardiology", "oncology", "pharmacy", "radiology"}
    found = all_specialties & set(care_plan.findings.keys())
    assert len(found) >= 2, (
        f"sample-3 should produce findings for at least 2 specialties, got: {found}"
    )


def test_e2e_all_sample_cases(sample_cases, guidelines):
    """
    Parametric end-to-end test: runs orchestration for every sample case
    and verifies structural validity.

    Validates: Requirements 6.1, 6.2, 6.3
    """
    for case in sample_cases:
        care_plan = _run_e2e_for_case(case, guidelines)
        _assert_care_plan_structurally_valid(care_plan, case)


def test_e2e_care_plan_case_id_matches_request(sample_cases, guidelines):
    """
    The returned CarePlan.case_id must match the case_id sent in the request.

    Validates: Requirements 6.1, 6.2
    """
    case = sample_cases[0]
    care_plan = _run_e2e_for_case(case, guidelines)
    assert care_plan.case_id == case["id"], (
        f"Expected case_id '{case['id']}', got '{care_plan.case_id}'"
    )


def test_e2e_care_plan_findings_are_non_empty_for_valid_case(sample_cases, guidelines):
    """
    For a valid sample case with known specialties, the findings dict must
    be non-empty after orchestration.

    Validates: Requirements 6.1, 6.2
    """
    case = sample_cases[0]  # sample-1 has cardiology + radiology
    care_plan = _run_e2e_for_case(case, guidelines)
    assert len(care_plan.findings) > 0, (
        "CarePlan.findings must be non-empty for a valid sample case"
    )
