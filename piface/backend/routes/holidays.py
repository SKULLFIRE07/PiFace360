"""
PiFace Attendance System - Holidays Router (standalone mount)

This module provides the same holiday endpoints that are also available
under the /api/leave/holidays path.  It is mounted separately at
/api/holidays by main.py for convenience.

The implementation is self-contained to avoid circular-import complexity.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import Holiday
from piface.backend.schemas import ApiResponse, HolidayCreate, HolidayResponse
from piface.backend.security import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=ApiResponse)
def list_holidays(
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    holidays = db.query(Holiday).order_by(Holiday.date).all()
    data = [HolidayResponse.model_validate(h).model_dump() for h in holidays]
    return ApiResponse(success=True, data=data)


@router.post("/", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_holiday(
    body: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    existing = db.query(Holiday).filter(Holiday.date == body.date).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A holiday already exists on this date",
        )
    holiday = Holiday(date=body.date, name=body.name)
    db.add(holiday)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create holiday",
        )
    return ApiResponse(
        success=True,
        data=HolidayResponse.model_validate(holiday).model_dump(),
    )


@router.delete("/{id}", response_model=ApiResponse)
def delete_holiday(
    id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    holiday = db.query(Holiday).filter(Holiday.id == id).first()
    if holiday is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Holiday with id {id} not found",
        )
    db.delete(holiday)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete holiday",
        )
    return ApiResponse(success=True, data={"id": id, "deleted": True})
