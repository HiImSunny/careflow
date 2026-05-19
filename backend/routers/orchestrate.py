"""
Router for:
  POST /orchestrate              — accepts the request, starts orchestration as a
                                   background task, and returns {case_id, status}
                                   immediately (202 Accepted) so the frontend can
                                   connect SSE and watch messages stream in real-time.
  GET  /orchestrate/{case_id}/result
                                 — returns the completed care plan once ready.
  GET  /export/pdf/{case_id}     — returns the care plan as a PDF file download.
  GET  /export/emr/{case_id}     — returns the care plan as a plain-text EMR file download.
"""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
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


# ---------------------------------------------------------------------------
# Background orchestration task
# ---------------------------------------------------------------------------


def _run_orchestration_background(
    request: OrchestrateRequest,
    guidelines: dict,
) -> None:
    """Run orchestration synchronously in a background thread.

    Persists the Case record and stores the care plan result so the frontend
    can fetch it via GET /api/orchestrate/{case_id}/result.

    This function is intentionally synchronous — FastAPI's BackgroundTasks
    runs it in a thread pool, which is exactly what we want so that
    ``run_orchestration`` (and its ThreadPoolExecutor workers) can call
    ``publish_agent_message`` via ``loop.call_soon_threadsafe``.
    """
    from backend.database import SessionLocal  # local import to avoid circular deps
    from backend.routers.chat import store_result

    case_id = request.case_id
    assert case_id is not None  # always set before this is called

    try:
        care_plan = run_orchestration(request, guidelines)
    except GeminiServiceError as exc:
        logger.error("Gemini service error during background orchestration: %s", exc)
        # Publish an error event so the SSE client knows something went wrong.
        try:
            from backend.routers.chat import publish_agent_message
            from datetime import datetime, timezone
            publish_agent_message(
                case_id,
                {
                    "agent": "system",
                    "content": f"Orchestration failed: {exc}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "error",
                },
            )
            publish_agent_message(case_id, None)  # close SSE stream
        except Exception:
            pass
        return
    except Exception as exc:
        logger.exception("Unexpected error during background orchestration: %s", exc)
        try:
            from backend.routers.chat import publish_agent_message
            from datetime import datetime, timezone
            publish_agent_message(
                case_id,
                {
                    "agent": "system",
                    "content": f"Orchestration error: {exc}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "type": "error",
                },
            )
            publish_agent_message(case_id, None)
        except Exception:
            pass
        return

    # Store result so frontend can fetch it after the SSE "complete" event.
    store_result(case_id, care_plan.model_dump())

    # Persist Case record to the database.
    db: Session = SessionLocal()
    try:
        case_record = Case(
            id=care_plan.case_id,
            input_text=request.text,
            image_ref=None,
            care_plan_json=care_plan.model_dump_json(),
        )
        db.add(case_record)
        db.commit()
    except Exception as exc:
        logger.exception("Database persistence error in background task: %s", exc)
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /orchestrate — returns 202 immediately, runs orchestration in background
# ---------------------------------------------------------------------------


@router.post("/orchestrate", status_code=202)
async def orchestrate(
    request: OrchestrateRequest,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    """Accept a clinical case and start orchestration as a background task.

    Returns 202 Accepted with ``{case_id, status: "processing"}`` immediately
    so the frontend can connect to the SSE stream before any agent work begins.

    The frontend should:
    1. Receive the ``case_id`` from this response.
    2. Connect to ``GET /api/chat/{case_id}`` to stream agent messages.
    3. When the SSE ``type: complete`` event arrives, fetch
       ``GET /api/orchestrate/{case_id}/result`` for the full care plan.

    Raises:
        HTTPException 422: When no input is provided.
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

    case_id = request.case_id

    # ------------------------------------------------------------------
    # 2. Load guidelines (fast, synchronous) and enqueue background task
    # ------------------------------------------------------------------
    guidelines = load_guidelines()
    background_tasks.add_task(_run_orchestration_background, request, guidelines)

    # ------------------------------------------------------------------
    # 3. Return immediately so the frontend can connect SSE
    # ------------------------------------------------------------------
    return JSONResponse(
        status_code=202,
        content={"case_id": case_id, "status": "processing"},
    )


# ---------------------------------------------------------------------------
# GET /orchestrate/{case_id}/result — returns care plan once ready
# ---------------------------------------------------------------------------


@router.get("/orchestrate/{case_id}/result")
async def orchestrate_result(case_id: str) -> JSONResponse:
    """Return the completed care plan for *case_id*.

    The frontend fetches this after receiving the ``type: complete`` SSE event.

    Returns:
        200 with the care plan JSON when ready.
        404 when the result is not yet available.
    """
    from backend.routers.chat import get_result

    result = get_result(case_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Result for case '{case_id}' is not yet available.",
        )
    return JSONResponse(content=result)


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
