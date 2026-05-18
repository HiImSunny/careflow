"""
Pydantic schemas and type definitions for CareFlow Orchestrator.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


class OrchestrateRequest(BaseModel):
    """Request body for POST /api/orchestrate."""

    text: Optional[str] = None
    image_b64: Optional[str] = None  # base64-encoded image
    case_id: Optional[str] = None  # client-generated UUID


class TimelineEntry(BaseModel):
    """A single entry in the care plan timeline."""

    timestamp: str
    specialty: str
    description: str


class SpecialtyFindings(BaseModel):
    """Structured findings produced by a Specialty Agent."""

    specialty: str
    summary: str
    action_items: List[str]


class CarePlan(BaseModel):
    """Unified care plan reconciled by the Coordinator Agent."""

    case_id: str
    timeline: List[TimelineEntry]
    recommendations: List[str]
    alerts: List[str]
    findings: Dict[str, SpecialtyFindings]


class CarePlanResponse(BaseModel):
    """Response body for POST /api/orchestrate."""

    case_id: str
    timeline: List[TimelineEntry]
    recommendations: List[str]
    alerts: List[str]
    findings: Dict[str, SpecialtyFindings]


class AgentMessage(BaseModel):
    """A message emitted by an agent during orchestration."""

    agent: str
    content: str
    timestamp: str


class CaseListItem(BaseModel):
    """Summary of a stored case returned by GET /api/cases."""

    case_id: str
    created_at: str
    input_text: Optional[str] = None
    care_plan: Optional[CarePlan] = None


def validate_has_input(request: OrchestrateRequest) -> bool:
    """Return True only when at least one of text or image_b64 is non-null and non-empty.

    Validates: Requirements 1.4, 2.5, 3.5
    """
    has_text = bool(request.text and request.text.strip())
    has_image = bool(request.image_b64 and request.image_b64.strip())
    return has_text or has_image
