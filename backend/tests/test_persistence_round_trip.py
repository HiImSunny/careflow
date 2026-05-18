"""
Property-based tests for Case persistence round-trip.

Verifies that storing a CarePlan via the Case model and retrieving it
produces a structurally equivalent CarePlan.

Property tests use the Hypothesis library and run a minimum of 100 iterations.

Feature: careflow-orchestrator
"""

from __future__ import annotations

import json
from typing import Dict

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
from backend.models import Case
from backend.schemas import CarePlan, SpecialtyFindings, TimelineEntry


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

SPECIALTIES = ["radiology", "oncology", "cardiology", "pharmacy"]


@st.composite
def timeline_entry_strategy(draw) -> TimelineEntry:
    """Generate a random TimelineEntry."""
    specialty = draw(st.sampled_from(SPECIALTIES))
    timestamp = draw(
        st.text(
            min_size=1,
            max_size=30,
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="-:TZ",
            ),
        )
    )
    description = draw(st.text(min_size=1, max_size=200))
    return TimelineEntry(timestamp=timestamp, specialty=specialty, description=description)


@st.composite
def findings_dict_strategy(draw) -> Dict[str, SpecialtyFindings]:
    """Generate a random dict of 0–4 SpecialtyFindings (one per specialty)."""
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
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"),
                whitelist_characters="-",
            ),
        )
    )
    timeline = draw(st.lists(timeline_entry_strategy(), min_size=0, max_size=5))
    recommendations = draw(
        st.lists(st.text(min_size=1, max_size=150), min_size=0, max_size=5)
    )
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
# pytest fixture — in-memory SQLite session
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session():
    """Provide an isolated in-memory SQLite session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---------------------------------------------------------------------------
# Helper — store and retrieve a CarePlan via the Case model
# ---------------------------------------------------------------------------


def _store_care_plan(session, care_plan: CarePlan) -> str:
    """Persist a CarePlan as a Case record; return the stored case id."""
    case = Case(
        id=care_plan.case_id,
        input_text=None,
        image_ref=None,
        care_plan_json=care_plan.model_dump_json(),
    )
    session.add(case)
    session.commit()
    return case.id


def _retrieve_care_plan(session, case_id: str) -> CarePlan:
    """Retrieve a Case record and deserialize its care_plan_json."""
    case = session.get(Case, case_id)
    assert case is not None, f"Case '{case_id}' not found in database"
    assert case.care_plan_json is not None, "care_plan_json must not be None"
    return CarePlan.model_validate_json(case.care_plan_json)


# ---------------------------------------------------------------------------
# Property 5: Case Persistence Round Trip
# Validates: Requirements 2.6, 8.2, 8.3
# ---------------------------------------------------------------------------


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(care_plan=care_plan_strategy())
def test_persistence_round_trip(care_plan: CarePlan) -> None:
    """
    **Property 5: Case Persistence Round Trip**

    For any submitted case with a Care Plan, storing the case to SQLite and
    then retrieving it SHALL produce a Care Plan that is structurally
    equivalent to the original:
      - same case_id
      - same number of timeline entries
      - same findings keys
      - same recommendations content
      - same alerts content

    **Validates: Requirements 2.6, 8.2, 8.3**
    Tag: Feature: careflow-orchestrator, Property 5: Case Persistence Round Trip
    """
    # Each Hypothesis example gets its own isolated in-memory database.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()

    try:
        # Store
        stored_id = _store_care_plan(session, care_plan)

        # Retrieve
        retrieved = _retrieve_care_plan(session, stored_id)

        # --- Structural equivalence assertions ---

        # 1. case_id is preserved
        assert retrieved.case_id == care_plan.case_id, (
            f"case_id mismatch: expected '{care_plan.case_id}', got '{retrieved.case_id}'"
        )

        # 2. Timeline length is preserved
        assert len(retrieved.timeline) == len(care_plan.timeline), (
            f"Timeline length mismatch: expected {len(care_plan.timeline)}, "
            f"got {len(retrieved.timeline)}"
        )

        # 3. Findings keys are preserved
        assert set(retrieved.findings.keys()) == set(care_plan.findings.keys()), (
            f"Findings keys mismatch: expected {set(care_plan.findings.keys())}, "
            f"got {set(retrieved.findings.keys())}"
        )

        # 4. Recommendations content is preserved
        assert retrieved.recommendations == care_plan.recommendations, (
            f"Recommendations mismatch: expected {care_plan.recommendations}, "
            f"got {retrieved.recommendations}"
        )

        # 5. Alerts content is preserved
        assert retrieved.alerts == care_plan.alerts, (
            f"Alerts mismatch: expected {care_plan.alerts}, "
            f"got {retrieved.alerts}"
        )

    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


# ---------------------------------------------------------------------------
# Unit tests — specific persistence behaviour
# ---------------------------------------------------------------------------


def test_store_and_retrieve_preserves_case_id(db_session) -> None:
    """Storing and retrieving a Case preserves the case_id."""
    plan = CarePlan(
        case_id="unit-test-case-001",
        timeline=[],
        recommendations=[],
        alerts=[],
        findings={},
    )
    _store_care_plan(db_session, plan)
    retrieved = _retrieve_care_plan(db_session, "unit-test-case-001")
    assert retrieved.case_id == "unit-test-case-001"


def test_store_and_retrieve_preserves_timeline_length(db_session) -> None:
    """Storing and retrieving a Case preserves the number of timeline entries."""
    plan = CarePlan(
        case_id="timeline-test-001",
        timeline=[
            TimelineEntry(
                timestamp="2024-01-01T10:00:00Z",
                specialty="cardiology",
                description="Elevated troponin noted",
            ),
            TimelineEntry(
                timestamp="2024-01-01T11:00:00Z",
                specialty="radiology",
                description="Chest X-ray performed",
            ),
        ],
        recommendations=[],
        alerts=[],
        findings={},
    )
    _store_care_plan(db_session, plan)
    retrieved = _retrieve_care_plan(db_session, "timeline-test-001")
    assert len(retrieved.timeline) == 2


def test_store_and_retrieve_preserves_findings_keys(db_session) -> None:
    """Storing and retrieving a Case preserves the findings specialty keys."""
    plan = CarePlan(
        case_id="findings-test-001",
        timeline=[],
        recommendations=[],
        alerts=[],
        findings={
            "cardiology": SpecialtyFindings(
                specialty="cardiology",
                summary="Normal sinus rhythm",
                action_items=["Follow up in 3 months"],
            ),
            "radiology": SpecialtyFindings(
                specialty="radiology",
                summary="No acute findings",
                action_items=[],
            ),
        },
    )
    _store_care_plan(db_session, plan)
    retrieved = _retrieve_care_plan(db_session, "findings-test-001")
    assert set(retrieved.findings.keys()) == {"cardiology", "radiology"}


def test_store_and_retrieve_preserves_recommendations(db_session) -> None:
    """Storing and retrieving a Case preserves the recommendations list."""
    recs = ["Start aspirin 81mg", "Refer to cardiology", "Order ECG"]
    plan = CarePlan(
        case_id="recs-test-001",
        timeline=[],
        recommendations=recs,
        alerts=[],
        findings={},
    )
    _store_care_plan(db_session, plan)
    retrieved = _retrieve_care_plan(db_session, "recs-test-001")
    assert retrieved.recommendations == recs


def test_store_and_retrieve_preserves_alerts(db_session) -> None:
    """Storing and retrieving a Case preserves the alerts list."""
    alerts = ["Drug interaction detected", "Urgent cardiology consult required"]
    plan = CarePlan(
        case_id="alerts-test-001",
        timeline=[],
        recommendations=[],
        alerts=alerts,
        findings={},
    )
    _store_care_plan(db_session, plan)
    retrieved = _retrieve_care_plan(db_session, "alerts-test-001")
    assert retrieved.alerts == alerts


def test_store_and_retrieve_empty_care_plan(db_session) -> None:
    """An empty CarePlan (no timeline, findings, recs, alerts) round-trips correctly."""
    plan = CarePlan(
        case_id="empty-plan-001",
        timeline=[],
        recommendations=[],
        alerts=[],
        findings={},
    )
    _store_care_plan(db_session, plan)
    retrieved = _retrieve_care_plan(db_session, "empty-plan-001")
    assert retrieved.case_id == "empty-plan-001"
    assert retrieved.timeline == []
    assert retrieved.recommendations == []
    assert retrieved.alerts == []
    assert retrieved.findings == {}


def test_retrieve_nonexistent_case_raises(db_session) -> None:
    """Attempting to retrieve a non-existent case raises AssertionError."""
    with pytest.raises(AssertionError, match="not found in database"):
        _retrieve_care_plan(db_session, "does-not-exist")


def test_care_plan_json_is_valid_json(db_session) -> None:
    """The care_plan_json stored in the Case record is valid JSON."""
    plan = CarePlan(
        case_id="json-test-001",
        timeline=[
            TimelineEntry(
                timestamp="2024-06-01T09:00:00Z",
                specialty="oncology",
                description="Biopsy result reviewed",
            )
        ],
        recommendations=["Staging workup"],
        alerts=["Suspicious nodule"],
        findings={
            "oncology": SpecialtyFindings(
                specialty="oncology",
                summary="Possible malignancy",
                action_items=["PET scan"],
            )
        },
    )
    _store_care_plan(db_session, plan)
    case = db_session.get(Case, "json-test-001")
    assert case is not None
    # Must be parseable as JSON
    parsed = json.loads(case.care_plan_json)
    assert parsed["case_id"] == "json-test-001"
    assert "timeline" in parsed
    assert "recommendations" in parsed
    assert "alerts" in parsed
    assert "findings" in parsed
