"""
Unit and property-based tests for CoordinatorAgent.

Property tests use the Hypothesis library and run a minimum of 100 iterations.

Feature: careflow-orchestrator
"""

import json
from typing import Dict, List
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from backend.agents.coordinator import CoordinatorAgent, _extract_string_list, _extract_timeline, _parse_gemini_response
from backend.schemas import CarePlan, SpecialtyFindings, TimelineEntry


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

SPECIALTIES = ["radiology", "oncology", "cardiology", "pharmacy"]


@st.composite
def specialty_findings_strategy(draw) -> SpecialtyFindings:
    """Generate a random SpecialtyFindings object."""
    specialty = draw(st.sampled_from(SPECIALTIES))
    summary = draw(st.text(min_size=1, max_size=200))
    action_items = draw(st.lists(st.text(min_size=1, max_size=100), max_size=5))
    return SpecialtyFindings(specialty=specialty, summary=summary, action_items=action_items)


@st.composite
def findings_dict_strategy(draw) -> Dict[str, SpecialtyFindings]:
    """Generate a random dict of 0–4 SpecialtyFindings (one per specialty)."""
    chosen = draw(st.lists(st.sampled_from(SPECIALTIES), min_size=0, max_size=4, unique=True))
    result: Dict[str, SpecialtyFindings] = {}
    for specialty in chosen:
        summary = draw(st.text(min_size=1, max_size=200))
        action_items = draw(st.lists(st.text(min_size=1, max_size=100), max_size=5))
        result[specialty] = SpecialtyFindings(
            specialty=specialty, summary=summary, action_items=action_items
        )
    return result


@st.composite
def failed_agents_strategy(draw) -> List[str]:
    """Generate a random subset of specialty names as failed agents."""
    return draw(st.lists(st.sampled_from(SPECIALTIES), min_size=0, max_size=4, unique=True))


def _make_gemini_response(
    timeline: list | None = None,
    recommendations: list | None = None,
    alerts: list | None = None,
) -> str:
    """Build a minimal valid Gemini JSON response string."""
    return json.dumps(
        {
            "timeline": timeline if timeline is not None else [],
            "recommendations": recommendations if recommendations is not None else [],
            "alerts": alerts if alerts is not None else [],
        }
    )


def _make_coordinator(gemini_response: str) -> CoordinatorAgent:
    """Return a CoordinatorAgent whose GeminiService is mocked."""
    mock_gemini = MagicMock()
    mock_gemini.generate.return_value = gemini_response
    return CoordinatorAgent(gemini_service=mock_gemini)


# ---------------------------------------------------------------------------
# Property 2: Care Plan Structural Invariant
# Validates: Requirements 2.4, 2.5
# ---------------------------------------------------------------------------


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(findings=findings_dict_strategy())
def test_care_plan_structural_invariant(findings: Dict[str, SpecialtyFindings]) -> None:
    """
    **Property 2: Care Plan Structural Invariant**

    For any valid set of specialty findings passed to the Coordinator Agent,
    the resulting Care Plan SHALL always contain a `timeline` array, a
    `recommendations` array, an `alerts` array, and a `findings` object —
    regardless of how many specialties contributed findings.

    **Validates: Requirements 2.4, 2.5**
    Tag: Feature: careflow-orchestrator, Property 2: Care Plan Structural Invariant
    """
    coordinator = _make_coordinator(_make_gemini_response())
    care_plan = coordinator.reconcile(findings=findings)

    # All four required fields must be present
    assert isinstance(care_plan, CarePlan), "reconcile() must return a CarePlan"
    assert isinstance(care_plan.timeline, list), "timeline must be a list"
    assert isinstance(care_plan.recommendations, list), "recommendations must be a list"
    assert isinstance(care_plan.alerts, list), "alerts must be a list"
    assert isinstance(care_plan.findings, dict), "findings must be a dict"

    # case_id must be a non-empty string
    assert isinstance(care_plan.case_id, str) and care_plan.case_id, "case_id must be non-empty"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(findings=findings_dict_strategy())
def test_care_plan_structural_invariant_with_partial_gemini_response(
    findings: Dict[str, SpecialtyFindings],
) -> None:
    """
    **Property 2 (partial response): Care Plan Structural Invariant**

    Even when Gemini returns partial data (missing keys), the Care Plan
    must still have all four required fields defaulting to empty lists/dicts.

    **Validates: Requirements 2.4, 2.5**
    """
    # Gemini returns an empty object — all fields should default
    coordinator = _make_coordinator("{}")
    care_plan = coordinator.reconcile(findings=findings)

    assert isinstance(care_plan.timeline, list)
    assert isinstance(care_plan.recommendations, list)
    assert isinstance(care_plan.alerts, list)
    assert isinstance(care_plan.findings, dict)


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(findings=findings_dict_strategy())
def test_care_plan_structural_invariant_on_gemini_error(
    findings: Dict[str, SpecialtyFindings],
) -> None:
    """
    **Property 2 (Gemini error): Care Plan Structural Invariant**

    Even when Gemini raises an error, the Care Plan must still be returned
    with all four required fields (defaulting to empty).

    **Validates: Requirements 2.4, 2.5**
    """
    mock_gemini = MagicMock()
    mock_gemini.generate.side_effect = RuntimeError("upstream failure")
    coordinator = CoordinatorAgent(gemini_service=mock_gemini)

    care_plan = coordinator.reconcile(findings=findings)

    assert isinstance(care_plan.timeline, list)
    assert isinstance(care_plan.recommendations, list)
    assert isinstance(care_plan.alerts, list)
    assert isinstance(care_plan.findings, dict)


# ---------------------------------------------------------------------------
# Property 3: Coordinator Resilience Under Partial Failure
# Validates: Requirements 2.8
# ---------------------------------------------------------------------------


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    findings=findings_dict_strategy(),
    failed_agents=failed_agents_strategy(),
)
def test_coordinator_resilience_under_partial_failure(
    findings: Dict[str, SpecialtyFindings],
    failed_agents: List[str],
) -> None:
    """
    **Property 3: Coordinator Resilience Under Partial Failure**

    For any subset of Specialty Agents that fail during execution (including
    all failing), the Coordinator Agent SHALL still produce a structurally
    valid Care Plan and SHALL include at least one entry in the `alerts`
    array for each failed agent.

    **Validates: Requirements 2.8**
    Tag: Feature: careflow-orchestrator, Property 3: Coordinator Resilience Under Partial Failure
    """
    coordinator = _make_coordinator(_make_gemini_response())
    care_plan = coordinator.reconcile(findings=findings, failed_agents=failed_agents)

    # Structural validity
    assert isinstance(care_plan, CarePlan)
    assert isinstance(care_plan.timeline, list)
    assert isinstance(care_plan.recommendations, list)
    assert isinstance(care_plan.alerts, list)
    assert isinstance(care_plan.findings, dict)

    # Each failed agent must have a corresponding warning alert
    for specialty in failed_agents:
        expected_warning = f"WARNING: {specialty} agent failed — findings unavailable"
        assert expected_warning in care_plan.alerts, (
            f"Expected alert for failed agent '{specialty}' not found in alerts: {care_plan.alerts}"
        )


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(failed_agents=failed_agents_strategy())
def test_coordinator_resilience_all_agents_failed(failed_agents: List[str]) -> None:
    """
    **Property 3 (all failed): Coordinator Resilience Under Partial Failure**

    When ALL agents fail (empty findings), the Care Plan must still be valid
    and contain a warning for every failed agent.

    **Validates: Requirements 2.8**
    """
    coordinator = _make_coordinator(_make_gemini_response())
    care_plan = coordinator.reconcile(findings={}, failed_agents=failed_agents)

    assert isinstance(care_plan, CarePlan)
    assert isinstance(care_plan.alerts, list)

    for specialty in failed_agents:
        expected_warning = f"WARNING: {specialty} agent failed — findings unavailable"
        assert expected_warning in care_plan.alerts


# ---------------------------------------------------------------------------
# Unit tests — specific behaviour
# ---------------------------------------------------------------------------


def test_reconcile_returns_care_plan_with_case_id() -> None:
    """reconcile() embeds the provided case_id in the returned CarePlan."""
    coordinator = _make_coordinator(_make_gemini_response())
    care_plan = coordinator.reconcile(findings={}, case_id="test-case-123")
    assert care_plan.case_id == "test-case-123"


def test_reconcile_passes_findings_through() -> None:
    """reconcile() preserves the input findings in the returned CarePlan."""
    findings = {
        "cardiology": SpecialtyFindings(
            specialty="cardiology",
            summary="Elevated troponin",
            action_items=["ECG", "Cardiology consult"],
        )
    }
    coordinator = _make_coordinator(_make_gemini_response())
    care_plan = coordinator.reconcile(findings=findings)
    assert "cardiology" in care_plan.findings
    assert care_plan.findings["cardiology"].summary == "Elevated troponin"


def test_reconcile_appends_failed_agent_warnings() -> None:
    """reconcile() appends exactly one warning per failed agent."""
    coordinator = _make_coordinator(_make_gemini_response())
    care_plan = coordinator.reconcile(
        findings={},
        failed_agents=["radiology", "pharmacy"],
    )
    assert "WARNING: radiology agent failed — findings unavailable" in care_plan.alerts
    assert "WARNING: pharmacy agent failed — findings unavailable" in care_plan.alerts


def test_reconcile_no_duplicate_warnings() -> None:
    """reconcile() does not duplicate warnings when Gemini already includes one."""
    # Gemini response already contains a warning for radiology
    gemini_alerts = ["WARNING: radiology agent failed — findings unavailable"]
    coordinator = _make_coordinator(_make_gemini_response(alerts=gemini_alerts))
    care_plan = coordinator.reconcile(findings={}, failed_agents=["radiology"])
    warning = "WARNING: radiology agent failed — findings unavailable"
    assert care_plan.alerts.count(warning) == 1


def test_reconcile_parses_timeline_from_gemini() -> None:
    """reconcile() correctly parses timeline entries from Gemini's response."""
    timeline_data = [
        {
            "timestamp": "2024-01-01T10:00:00Z",
            "specialty": "cardiology",
            "description": "Elevated troponin noted",
        }
    ]
    coordinator = _make_coordinator(_make_gemini_response(timeline=timeline_data))
    care_plan = coordinator.reconcile(findings={})
    assert len(care_plan.timeline) == 1
    assert care_plan.timeline[0].specialty == "cardiology"
    assert care_plan.timeline[0].description == "Elevated troponin noted"


def test_reconcile_parses_recommendations_from_gemini() -> None:
    """reconcile() correctly parses recommendations from Gemini's response."""
    recs = ["Order ECG", "Refer to cardiology"]
    coordinator = _make_coordinator(_make_gemini_response(recommendations=recs))
    care_plan = coordinator.reconcile(findings={})
    assert care_plan.recommendations == recs


def test_reconcile_handles_malformed_json_gracefully() -> None:
    """reconcile() returns a valid CarePlan even when Gemini returns invalid JSON."""
    mock_gemini = MagicMock()
    mock_gemini.generate.return_value = "not valid json at all"
    coordinator = CoordinatorAgent(gemini_service=mock_gemini)
    care_plan = coordinator.reconcile(findings={})
    assert isinstance(care_plan.timeline, list)
    assert isinstance(care_plan.recommendations, list)
    assert isinstance(care_plan.alerts, list)


def test_reconcile_handles_gemini_error_gracefully() -> None:
    """reconcile() returns a valid CarePlan even when Gemini raises an exception."""
    mock_gemini = MagicMock()
    mock_gemini.generate.side_effect = RuntimeError("API unavailable")
    coordinator = CoordinatorAgent(gemini_service=mock_gemini)
    care_plan = coordinator.reconcile(findings={})
    assert isinstance(care_plan.timeline, list)
    assert isinstance(care_plan.recommendations, list)
    assert isinstance(care_plan.alerts, list)


def test_reconcile_strips_markdown_fences() -> None:
    """reconcile() handles Gemini responses wrapped in markdown code fences."""
    payload = json.dumps({"timeline": [], "recommendations": ["Take aspirin"], "alerts": []})
    wrapped = f"```json\n{payload}\n```"
    coordinator = _make_coordinator(wrapped)
    care_plan = coordinator.reconcile(findings={})
    assert "Take aspirin" in care_plan.recommendations


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


def test_parse_gemini_response_valid_json() -> None:
    raw = '{"timeline": [], "recommendations": ["a"], "alerts": []}'
    result = _parse_gemini_response(raw)
    assert result["recommendations"] == ["a"]


def test_parse_gemini_response_strips_fences() -> None:
    raw = '```json\n{"timeline": [], "recommendations": [], "alerts": ["x"]}\n```'
    result = _parse_gemini_response(raw)
    assert result["alerts"] == ["x"]


def test_parse_gemini_response_raises_on_invalid() -> None:
    with pytest.raises(ValueError):
        _parse_gemini_response("this is not json")


def test_extract_string_list_with_valid_list() -> None:
    assert _extract_string_list(["a", "b", "c"]) == ["a", "b", "c"]


def test_extract_string_list_with_non_list() -> None:
    assert _extract_string_list(None) == []
    assert _extract_string_list("string") == []
    assert _extract_string_list(42) == []


def test_extract_timeline_with_valid_entries() -> None:
    raw = [
        {"timestamp": "2024-01-01T00:00:00Z", "specialty": "radiology", "description": "Mass found"}
    ]
    entries = _extract_timeline(raw)
    assert len(entries) == 1
    assert entries[0].specialty == "radiology"


def test_extract_timeline_skips_malformed_entries() -> None:
    raw = [
        {"timestamp": "2024-01-01T00:00:00Z", "specialty": "radiology", "description": "OK"},
        "not a dict",
        None,
    ]
    entries = _extract_timeline(raw)
    assert len(entries) == 1


def test_extract_timeline_with_non_list() -> None:
    assert _extract_timeline(None) == []
    assert _extract_timeline("bad") == []
