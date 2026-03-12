"""
PiFace Attendance System - Unknown Persons Routes

GET  /           - List all unknown persons with visit stats
PUT  /{id}/rename - Rename an unknown person (convert to known)
DELETE /{id}     - Soft-delete an unknown person
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import AttendanceEvent, AuditLog, Person
from piface.backend.schemas import ApiResponse, UnknownRename
from piface.backend.security import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# GET / - List all unknown persons
# ---------------------------------------------------------------------------
@router.get("/", response_model=ApiResponse)
def list_unknowns(
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """List all active unknown persons with visit count, first_seen, last_seen."""
    results = (
        db.query(
            Person.id,
            Person.name,
            Person.face_image,
            Person.enrolled_at,
            Person.is_active,
            func.count(AttendanceEvent.id).label("visit_count"),
            func.min(AttendanceEvent.timestamp).label("first_seen"),
            func.max(AttendanceEvent.timestamp).label("last_seen"),
        )
        .outerjoin(AttendanceEvent, AttendanceEvent.person_id == Person.id)
        .filter(Person.is_unknown.is_(True), Person.is_active.is_(True))
        .group_by(Person.id)
        .all()
    )

    unknowns = []
    for row in results:
        unknowns.append(
            {
                "id": row.id,
                "name": row.name,
                "has_face_image": row.face_image is not None,
                "enrolled_at": row.enrolled_at.isoformat() if row.enrolled_at else None,
                "visit_count": row.visit_count,
                "first_seen": row.first_seen.isoformat() if row.first_seen else None,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
        )

    return ApiResponse(success=True, data=unknowns)


# ---------------------------------------------------------------------------
# PUT /{id}/rename - Rename unknown to known person
# ---------------------------------------------------------------------------
@router.put("/{id}/rename", response_model=ApiResponse)
def rename_unknown(
    id: int,
    body: UnknownRename,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Convert an unknown person to a known person by assigning identity fields.

    All past attendance_events remain linked via person_id.
    """
    person = db.query(Person).filter(Person.id == id).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with id {id} not found",
        )

    if not person.is_unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Person is not marked as unknown",
        )

    # Capture old values for audit
    old_values = {
        "name": person.name,
        "employee_id": person.employee_id,
        "department": person.department,
        "job_title": person.job_title,
        "phone": person.phone,
        "is_unknown": person.is_unknown,
    }

    # Update person fields
    person.name = body.name
    person.employee_id = body.employee_id
    person.department = body.department
    person.job_title = body.job_title
    person.phone = body.phone
    person.is_unknown = False

    new_values = {
        "name": person.name,
        "employee_id": person.employee_id,
        "department": person.department,
        "job_title": person.job_title,
        "phone": person.phone,
        "is_unknown": person.is_unknown,
    }

    # Audit log
    audit = AuditLog(
        action="RENAME_UNKNOWN",
        target_table="persons",
        target_id=person.id,
        old_value=json.dumps(old_values),
        new_value=json.dumps(new_values),
        performed_by=current_user,
        performed_at=datetime.now(timezone.utc),
    )
    db.add(audit)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to rename unknown person %d", id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to rename unknown person",
        )

    logger.info(
        "User %s renamed unknown person %d to %r", current_user, id, body.name
    )

    return ApiResponse(
        success=True,
        data={
            "id": person.id,
            "name": person.name,
            "employee_id": person.employee_id,
            "department": person.department,
            "job_title": person.job_title,
            "phone": person.phone,
            "is_unknown": person.is_unknown,
        },
    )


# ---------------------------------------------------------------------------
# DELETE /{id} - Soft-delete unknown person
# ---------------------------------------------------------------------------
@router.delete("/{id}", response_model=ApiResponse)
def delete_unknown(
    id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Soft-delete an unknown person by setting is_active=False."""
    person = db.query(Person).filter(Person.id == id).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with id {id} not found",
        )

    if not person.is_unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Person is not marked as unknown; use the employees endpoint",
        )

    person.is_active = False

    # Audit log
    audit = AuditLog(
        action="DELETE_UNKNOWN",
        target_table="persons",
        target_id=person.id,
        old_value=json.dumps({"is_active": True}),
        new_value=json.dumps({"is_active": False}),
        performed_by=current_user,
        performed_at=datetime.now(timezone.utc),
    )
    db.add(audit)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to soft-delete unknown person %d", id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete unknown person",
        )

    logger.info("User %s soft-deleted unknown person %d", current_user, id)

    return ApiResponse(success=True, data={"id": id, "deleted": True})
