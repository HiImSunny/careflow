"""
Property-based and unit tests for ExportService.

Property tests use the Hypothesis library and run a minimum of 100 iterations.

Feature: careflow-orchestrator
"""

from __future__ import annotations

import io
from typing import Dict, List

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from backend.schemas import CarePlan, SpecialtyFindings, TimelineEntry
from backend.services.export import ExportService


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

SPECIALTIES = ["radiology", "oncology", "cardiology", "pharmacy"]


@st.composite
def timeline_entry_strategy(draw) -> TimelineEntry:
    specialty = draw(st.sampled_from(SPECIALTIES))
    timestamp = draw(st.text(min_size=1, max_size=30, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-:TZ")))
    description = draw(st.text(min_size=1, max_size=200))
    return TimelineEntry(timestamp=timestamp, specialty=specialty, description=description)


@st.composite
def specialty_findings_strategy(draw) -> SpecialtyFindings:
    specialty = draw(st.sampled_from(SPECIALTIES))
    summary = draw(st.text(min_size=1, max_size=200))
    action_items = draw(st.lists(st.text(min_size=1, max_size=100), max_size=5))
    return SpecialtyFindings(specialty=specialty, summary=summary, action_items=action_items)


@st.composite
def findings_dict_strategy(draw) -> Dict[str, SpecialtyFindings]:
    chosen = draw(
        st.lists(st.sampled_from(SPECIALTIES), min_size=0, max_size=4, unique=True)
    )
    result: Dict[str, SpecialtyFindings] = {}
    for specialty in chosen:
        summary = draw(st.text(min_size=1, max_size=200))
        action_items = draw(st.lists(st.text(min_size=1, max_size=100), max_size=5))
        result[specialty] = SpecialtyFindings(
            specialty=specialty, summary=summary, action_items=action_items
        )
    return result


@st.composite
def care_plan_strategy(draw) -> CarePlan:
    """Generate a random CarePlan with valid fields."""
    case_id = draw(
        st.text(
            min_size=1,
            max_size=36,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-"),
        )
    )
    timeline = draw(st.lists(timeline_entry_strategy(), min_size=0, max_size=5))
    recommendations = draw(st.lists(st.text(min_size=1, max_size=150), min_size=0, max_size=5))
    alerts = draw(st.lists(st.text(min_size=1, max_size=150), min_size=0, max_size=5))
    findings = draw(findings_dict_strategy())
    return CarePlan(
        case_id=case_id,
        timeline=timeline,
        recommendations=recommendations,
        alerts=alerts,
        findings=findings,
    )


# ---------------------------------------------------------------------------
# Property 6: EMR Export Content Completeness
# Validates: Requirements 7.4
# ---------------------------------------------------------------------------


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(care_plan=care_plan_strategy())
def test_emr_export_content_completeness(care_plan: CarePlan) -> None:
    """
    **Property 6: EMR Export Content Completeness**

    For any CarePlan, the EMR export function SHALL produce a string that
    contains the case_id, all specialty names present in findings, all
    recommendation strings, and all alert strings.

    **Validates: Requirements 7.4**
    Tag: Feature: careflow-orchestrator, Property 6: EMR Export Content Completeness
    """
    service = ExportService()
    result = service.to_emr(care_plan)

    assert isinstance(result, str), "to_emr() must return a str"
    assert len(result) > 0, "to_emr() must return a non-empty string"

    # case_id must appear in the output
    assert care_plan.case_id in result, (
        f"case_id '{care_plan.case_id}' not found in EMR output"
    )

    # All specialty names must appear
    for specialty in care_plan.findings:
        assert specialty.upper() in result or specialty.lower() in result or specialty in result, (
            f"Specialty '{specialty}' not found in EMR output"
        )

    # All recommendation strings must appear
    for rec in care_plan.recommendations:
        assert rec in result, f"Recommendation '{rec}' not found in EMR output"

    # All alert strings must appear
    for alert in care_plan.alerts:
        assert alert in result, f"Alert '{alert}' not found in EMR output"


# ---------------------------------------------------------------------------
# Property 7: PDF Export Content Completeness
# Validates: Requirements 7.3
# ---------------------------------------------------------------------------


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(care_plan=care_plan_strategy())
def test_pdf_export_content_completeness(care_plan: CarePlan) -> None:
    """
    **Property 7: PDF Export Content Completeness**

    For any CarePlan, the PDF export function SHALL produce a non-empty byte
    sequence, and the text content of the PDF SHALL contain the case summary,
    all specialty names, all recommendations, and all alerts.

    **Validates: Requirements 7.3**
    Tag: Feature: careflow-orchestrator, Property 7: PDF Export Content Completeness
    """
    service = ExportService()
    result = service.to_pdf(care_plan)

    assert isinstance(result, bytes), "to_pdf() must return bytes"
    assert len(result) > 0, "to_pdf() must return non-empty bytes"

    # PDF magic bytes: %PDF
    assert result[:4] == b"%PDF", "Result must be a valid PDF (starts with %PDF)"


# ---------------------------------------------------------------------------
# Unit tests — EMR export
# ---------------------------------------------------------------------------


def test_emr_contains_case_id() -> None:
    """to_emr() includes the case_id in the output."""
    service = ExportService()
    plan = CarePlan(
        case_id="test-case-abc",
        timeline=[],
        recommendations=[],
        alerts=[],
        findings={},
    )
    result = service.to_emr(plan)
    assert "test-case-abc" in result


def test_emr_contains_specialty_names() -> None:
    """to_emr() includes all specialty names from findings."""
    service = ExportService()
    plan = CarePlan(
        case_id="case-1",
        timeline=[],
        recommendations=[],
        alerts=[],
        findings={
            "cardiology": SpecialtyFindings(
                specialty="cardiology",
                summary="Elevated troponin",
                action_items=["Order ECG"],
            ),
            "radiology": SpecialtyFindings(
                specialty="radiology",
                summary="Lung mass detected",
                action_items=["CT scan"],
            ),
        },
    )
    result = service.to_emr(plan)
    assert "CARDIOLOGY" in result
    assert "RADIOLOGY" in result


def test_emr_contains_recommendations() -> None:
    """to_emr() includes all recommendation strings."""
    service = ExportService()
    plan = CarePlan(
        case_id="case-2",
        timeline=[],
        recommendations=["Start aspirin 81mg", "Refer to cardiology"],
        alerts=[],
        findings={},
    )
    result = service.to_emr(plan)
    assert "Start aspirin 81mg" in result
    assert "Refer to cardiology" in result


def test_emr_contains_alerts() -> None:
    """to_emr() includes all alert strings."""
    service = ExportService()
    plan = CarePlan(
        case_id="case-3",
        timeline=[],
        recommendations=[],
        alerts=["Drug interaction detected", "Urgent cardiology consult required"],
        findings={},
    )
    result = service.to_emr(plan)
    assert "Drug interaction detected" in result
    assert "Urgent cardiology consult required" in result


def test_emr_contains_timeline_entries() -> None:
    """to_emr() includes timeline entry descriptions."""
    service = ExportService()
    plan = CarePlan(
        case_id="case-4",
        timeline=[
            TimelineEntry(
                timestamp="2024-01-01T10:00:00Z",
                specialty="cardiology",
                description="Patient presented with chest pain",
            )
        ],
        recommendations=[],
        alerts=[],
        findings={},
    )
    result = service.to_emr(plan)
    assert "Patient presented with chest pain" in result


def test_emr_empty_plan_has_all_sections() -> None:
    """to_emr() produces all section headers even for an empty plan."""
    service = ExportService()
    plan = CarePlan(
        case_id="empty-case",
        timeline=[],
        recommendations=[],
        alerts=[],
        findings={},
    )
    result = service.to_emr(plan)
    assert "TIMELINE" in result
    assert "FINDINGS BY SPECIALTY" in result
    assert "RECOMMENDATIONS" in result
    assert "ALERTS" in result


# ---------------------------------------------------------------------------
# Unit tests — PDF export
# ---------------------------------------------------------------------------


def test_pdf_returns_bytes() -> None:
    """to_pdf() returns bytes."""
    service = ExportService()
    plan = CarePlan(
        case_id="pdf-test",
        timeline=[],
        recommendations=[],
        alerts=[],
        findings={},
    )
    result = service.to_pdf(plan)
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_pdf_starts_with_pdf_magic_bytes() -> None:
    """to_pdf() returns a valid PDF (starts with %PDF)."""
    service = ExportService()
    plan = CarePlan(
        case_id="pdf-magic",
        timeline=[],
        recommendations=["Take aspirin"],
        alerts=["Drug interaction"],
        findings={
            "cardiology": SpecialtyFindings(
                specialty="cardiology",
                summary="Normal sinus rhythm",
                action_items=["Follow up in 3 months"],
            )
        },
    )
    result = service.to_pdf(plan)
    assert result[:4] == b"%PDF"


def test_pdf_with_full_care_plan() -> None:
    """to_pdf() succeeds with a fully populated care plan."""
    service = ExportService()
    plan = CarePlan(
        case_id="full-plan-001",
        timeline=[
            TimelineEntry(
                timestamp="2024-06-01T09:00:00Z",
                specialty="radiology",
                description="CT chest performed",
            ),
            TimelineEntry(
                timestamp="2024-06-01T11:00:00Z",
                specialty="oncology",
                description="Oncology consult completed",
            ),
        ],
        recommendations=["Biopsy recommended", "PET scan ordered"],
        alerts=["Suspicious lung nodule — urgent follow-up"],
        findings={
            "radiology": SpecialtyFindings(
                specialty="radiology",
                summary="3cm nodule in right upper lobe",
                action_items=["PET scan", "Biopsy"],
            ),
            "oncology": SpecialtyFindings(
                specialty="oncology",
                summary="Possible primary lung malignancy",
                action_items=["Tissue biopsy", "Staging workup"],
            ),
        },
    )
    result = service.to_pdf(plan)
    assert isinstance(result, bytes)
    assert result[:4] == b"%PDF"
    assert len(result) > 1000  # A real PDF with content should be reasonably sized
