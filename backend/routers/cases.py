"""
Router for:
  GET /cases         — returns a list of stored cases as CaseListItem
  GET /cases/samples — returns the pre-built sample cases from data/sample_cases.json
"""

from __future__ import annotations

import json
import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Case
from backend.schemas import CarePlan, CaseListItem
from backend.services.data_loader import load_sample_cases

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/cases/samples")
def get_sample_cases() -> list:
    """Return the list of pre-built sample cases from data/sample_cases.json.

    Validates: Requirements 6.1, 6.3
    """
    return load_sample_cases()


@router.get("/cases", response_model=List[CaseListItem])
def list_cases(db: Session = Depends(get_db)) -> List[CaseListItem]:
    """Return all stored cases ordered by creation time (newest first).

    Each item includes the case_id, created_at timestamp, input_text, and the
    deserialized CarePlan (if available).

    Validates: Requirements 8.4
    """
    cases = db.query(Case).order_by(Case.created_at.desc()).all()

    result: List[CaseListItem] = []
    for case in cases:
        care_plan: CarePlan | None = None
        if case.care_plan_json:
            try:
                care_plan = CarePlan.model_validate(json.loads(case.care_plan_json))
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Failed to deserialize care_plan_json for case %s: %s",
                    case.id,
                    exc,
                )

        result.append(
            CaseListItem(
                case_id=case.id,
                created_at=case.created_at.isoformat(),
                input_text=case.input_text,
                care_plan=care_plan,
            )
        )

    return result
