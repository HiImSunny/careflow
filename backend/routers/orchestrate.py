"""
Router for:
  POST /orchestrate              — validates input, runs orchestration pipeline,
                                   persists the Case record, and returns CarePlanResponse.
  GET  /export/pdf/{case_id}     — returns the care plan as a PDF file download.
  GET  /export/emr/{case_id}     — returns the care plan as a plain-text EMR file download.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Case
from backend.schemas import CarePlan, CarePlanResponse, OrchestrateRequest, validate_has_input
from backend.services.crew import run_orchestration
from backend.services.data_loader import load_guidelines
from backend.services.export import ExportService
from backend.services.gemini import GeminiServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/orchestrate", response_model=CarePlanResponse, status_code=200)
async def orchestrate(
    request: OrchestrateRequest,
    db: Session = Depends(get_db),
) -> CarePlanResponse:
    """Run the multi-agent orchestration pipeline for a submitted clinical case.

    - Validates that at least one of text or image_b64 is present (422 if not).
    - Calls ``run_orchestration()`` to produce a ``CarePlan``.
    - Persists a ``Case`` record to SQLite.
    - Returns a ``CarePlanResponse``.

    Raises:
        HTTPException 422: When no input is provided.
        HTTPException 502: When the Gemini service returns an error.
        HTTPException 500: On unexpected errors.
    """
    # ------------------------------------------------------------------
    # 1. Input validation
    # ------------------------------------------------------------------
    if not validate_has_input(request):
        raise HTTPException(
            status_code=422,
            detail="At least one of 'text' or 'image_b64' must be provided.",
        )

    # Ensure a case_id is set (use client-supplied value or generate one).
    if not request.case_id:
        request = request.model_copy(update={"case_id": str(uuid.uuid4())})

    # ------------------------------------------------------------------
    # 2. Load guidelines and run orchestration
    # ------------------------------------------------------------------
    try:
        guidelines = load_guidelines()
        care_plan = run_orchestration(request, guidelines)
    except GeminiServiceError as exc:
        logger.error("Gemini service error during orchestration: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Upstream AI service error: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error during orchestration: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Orchestration error: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # 3. Persist Case record
    # ------------------------------------------------------------------
    try:
        case_record = Case(
            id=care_plan.case_id,
            input_text=request.text,
            image_ref=None,  # image stored as b64 in request; no file ref needed
            care_plan_json=care_plan.model_dump_json(),
        )
        db.add(case_record)
        db.commit()
        db.refresh(case_record)
    except Exception as exc:
        logger.exception("Database persistence error: %s", exc)
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Persistence error: {exc}",
        ) from exc

    # ------------------------------------------------------------------
    # 4. Return response
    # ------------------------------------------------------------------
    return CarePlanResponse(
        case_id=care_plan.case_id,
        timeline=care_plan.timeline,
        recommendations=care_plan.recommendations,
        alerts=care_plan.alerts,
        findings=care_plan.findings,
    )


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

_export_service = ExportService()


def _get_care_plan_for_case(case_id: str, db: Session) -> CarePlan:
    """Retrieve and deserialize the CarePlan for *case_id*, or raise 404/500."""
    case_record: Case | None = db.query(Case).filter(Case.id == case_id).first()
    if case_record is None:
        raise HTTPException(status_code=404, detail=f"Case '{case_id}' not found.")
    if not case_record.care_plan_json:
        raise HTTPException(
            status_code=404,
            detail=f"No care plan stored for case '{case_id}'.",
        )
    try:
        return CarePlan.model_validate(json.loads(case_record.care_plan_json))
    except Exception as exc:
        logger.exception("Failed to deserialize care plan for case %s: %s", case_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to deserialize care plan: {exc}",
        ) from exc


# ---------------------------------------------------------------------------
# GET /export/pdf/{case_id}
# ---------------------------------------------------------------------------


@router.get("/export/pdf/{case_id}", response_class=Response)
def export_pdf(case_id: str, db: Session = Depends(get_db)) -> Response:
    """Return the care plan for *case_id* as a downloadable PDF file.

    Validates: Requirements 7.1, 7.3
    """
    care_plan = _get_care_plan_for_case(case_id, db)
    try:
        pdf_bytes = _export_service.to_pdf(care_plan)
    except Exception as exc:
        logger.exception("PDF generation failed for case %s: %s", case_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation error: {exc}",
        ) from exc

    filename = f"careplan_{case_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# GET /export/emr/{case_id}
# ---------------------------------------------------------------------------


@router.get("/export/emr/{case_id}", response_class=Response)
def export_emr(case_id: str, db: Session = Depends(get_db)) -> Response:
    """Return the care plan for *case_id* as a downloadable plain-text EMR file.

    Validates: Requirements 7.2, 7.4
    """
    care_plan = _get_care_plan_for_case(case_id, db)
    try:
        emr_text = _export_service.to_emr(care_plan)
    except Exception as exc:
        logger.exception("EMR generation failed for case %s: %s", case_id, exc)
        raise HTTPException(
            status_code=500,
            detail=f"EMR generation error: {exc}",
        ) from exc

    filename = f"careplan_{case_id}.txt"
    return Response(
        content=emr_text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
