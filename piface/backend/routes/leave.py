"""
PiFace Attendance System - Leave Record Routes

GET    /         - List leave records (with optional filters)
POST   /         - Create a leave record
DELETE /{id}     - Delete a leave record
GET    /holidays - List all holidays
POST   /holidays - Create a holiday
DELETE /holidays/{id} - Delete a holiday
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import (
    AttendanceEvent,
    DailySummary,
    Holiday,
    LeaveRecord,
    Person,
)
from piface.backend.schemas import (
    ApiResponse,
    HolidayCreate,
    HolidayResponse,
    LeaveRecordCreate,
    LeaveRecordResponse,
)
from piface.backend.security import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _recompute_daily_summary(db: Session, person_id: int, target_date) -> None:
    """Recompute the daily_summary row for a person on a given date.

    If the person has a leave record for that date, the status is set to
    ON_LEAVE.  Otherwise the summary is rebuilt from attendance events.
    """
    # Check for leave
    leave = (
        db.query(LeaveRecord)
        .filter(
            LeaveRecord.person_id == person_id,
            LeaveRecord.date == target_date,
        )
        .first()
    )

    # Check for holiday
    holiday = db.query(Holiday).filter(Holiday.date == target_date).first()

    # Fetch or create the summary row
    summary = (
        db.query(DailySummary)
        .filter(
            DailySummary.person_id == person_id,
            DailySummary.date == target_date,
        )
        .first()
    )
    if summary is None:
        summary = DailySummary(person_id=person_id, date=target_date)
        db.add(summary)

    if leave is not None:
        summary.status = "ON_LEAVE"
        summary.first_in_time = None
        summary.last_out_time = None
        summary.total_hours_worked = None
        summary.total_break_minutes = None
        summary.total_in_out_events = 0
        db.flush()
        return

    if holiday is not None:
        summary.status = "HOLIDAY"
        db.flush()
        return

    # Recompute from attendance events
    events = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.person_id == person_id,
            AttendanceEvent.date == target_date,
        )
        .order_by(AttendanceEvent.timestamp)
        .all()
    )

    if not events:
        summary.status = "ABSENT"
        summary.first_in_time = None
        summary.last_out_time = None
        summary.total_hours_worked = 0
        summary.total_break_minutes = 0
        summary.total_in_out_events = 0
        db.flush()
        return

    in_events = [e for e in events if e.event_type == "IN"]
    out_events = [e for e in events if e.event_type == "OUT"]

    summary.first_in_time = in_events[0].timestamp if in_events else None
    summary.last_out_time = out_events[-1].timestamp if out_events else None
    summary.total_in_out_events = len(events)

    # Calculate total hours and breaks
    total_seconds = 0.0
    total_break_seconds = 0.0
    last_in = None

    for event in events:
        if event.event_type == "IN":
            if last_in is not None and out_events:
                # There was a gap (break) between last OUT and this IN
                pass
            last_in = event.timestamp
        elif event.event_type == "OUT" and last_in is not None:
            delta = (event.timestamp - last_in).total_seconds()
            total_seconds += max(delta, 0)
            last_in = None

    # Calculate breaks: time between an OUT and the next IN
    sorted_events = sorted(events, key=lambda e: e.timestamp)
    for i in range(len(sorted_events) - 1):
        if sorted_events[i].event_type == "OUT" and sorted_events[i + 1].event_type == "IN":
            break_delta = (
                sorted_events[i + 1].timestamp - sorted_events[i].timestamp
            ).total_seconds()
            total_break_seconds += max(break_delta, 0)

    summary.total_hours_worked = round(total_seconds / 3600, 2)
    summary.total_break_minutes = int(total_break_seconds / 60)

    # Determine status
    if summary.total_hours_worked and summary.total_hours_worked >= 4:
        summary.status = "PRESENT" if summary.total_hours_worked >= 6 else "HALF_DAY"
    elif in_events:
        summary.status = "HALF_DAY"
    else:
        summary.status = "ABSENT"

    db.flush()


# ---------------------------------------------------------------------------
# GET / - List leave records
# ---------------------------------------------------------------------------
@router.get("/", response_model=ApiResponse)
def list_leave_records(
    person_id: int | None = Query(default=None),
    date_from: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """List leave records with optional filters."""
    query = db.query(LeaveRecord)

    if person_id is not None:
        query = query.filter(LeaveRecord.person_id == person_id)
    if date_from is not None:
        from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
        query = query.filter(LeaveRecord.date >= from_date)
    if date_to is not None:
        to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
        query = query.filter(LeaveRecord.date <= to_date)

    records = query.order_by(LeaveRecord.date.desc()).all()

    # Enrich with employee name for frontend display
    person_ids = {r.person_id for r in records}
    persons = {p.id: p for p in db.query(Person).filter(Person.id.in_(person_ids)).all()} if person_ids else {}

    data = []
    for r in records:
        row = LeaveRecordResponse.model_validate(r).model_dump()
        person = persons.get(r.person_id)
        row["employee_name"] = person.name if person else "Unknown"
        row["name"] = person.name if person else "Unknown"
        row["start_date"] = row["date"]
        row["end_date"] = row["date"]
        data.append(row)

    return ApiResponse(success=True, data=data)


# ---------------------------------------------------------------------------
# POST / - Create leave record
# ---------------------------------------------------------------------------
@router.post("/", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_leave_record(
    body: dict,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Create a leave record and recompute the daily summary.

    Accepts frontend format: {employee_id, start_date, end_date, leave_type, note}
    or original format: {person_id, date, leave_type, note}
    """
    # Normalize field names from frontend
    person_id = body.get("person_id") or body.get("employee_id")
    if person_id is not None:
        person_id = int(person_id)
    start_date_str = body.get("date") or body.get("start_date")
    end_date_str = body.get("end_date") or start_date_str
    leave_type = body.get("leave_type", "Vacation")
    note = body.get("note")

    if not person_id or not start_date_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="person_id/employee_id and date/start_date are required",
        )

    # Verify person exists
    person = db.query(Person).filter(Person.id == person_id).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with id {person_id} not found",
        )

    # Parse dates
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
    end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date() if end_date_str else start_date

    # Create leave records for each day in the range
    from datetime import timedelta
    created = []
    current = start_date
    while current <= end_date:
        existing = (
            db.query(LeaveRecord)
            .filter(
                LeaveRecord.person_id == person_id,
                LeaveRecord.date == current,
            )
            .first()
        )
        if existing is None:
            record = LeaveRecord(
                person_id=person_id,
                date=current,
                leave_type=leave_type,
                note=note,
            )
            db.add(record)
            db.flush()
            _recompute_daily_summary(db, person_id, current)
            created.append(record)
        current += timedelta(days=1)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to create leave record")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create leave record",
        )

    logger.info(
        "User %s created leave records for person %d from %s to %s",
        current_user,
        person_id,
        start_date_str,
        end_date_str,
    )

    if created:
        return ApiResponse(
            success=True,
            data=LeaveRecordResponse.model_validate(created[0]).model_dump(),
        )
    return ApiResponse(
        success=True,
        data={"message": "Leave records already exist for the given dates"},
    )


# ---------------------------------------------------------------------------
# DELETE /{id} - Delete leave record
# ---------------------------------------------------------------------------
@router.delete("/{id}", response_model=ApiResponse)
def delete_leave_record(
    id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Delete a leave record and recompute the daily summary."""
    record = db.query(LeaveRecord).filter(LeaveRecord.id == id).first()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Leave record with id {id} not found",
        )

    person_id = record.person_id
    target_date = record.date

    db.delete(record)
    db.flush()

    _recompute_daily_summary(db, person_id, target_date)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to delete leave record %d", id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete leave record",
        )

    logger.info("User %s deleted leave record %d", current_user, id)

    return ApiResponse(success=True, data={"id": id, "deleted": True})


# ---------------------------------------------------------------------------
# GET /holidays - List holidays
# ---------------------------------------------------------------------------
@router.get("/holidays", response_model=ApiResponse)
def list_holidays(
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """List all holidays."""
    holidays = db.query(Holiday).order_by(Holiday.date).all()
    data = [HolidayResponse.model_validate(h).model_dump() for h in holidays]
    return ApiResponse(success=True, data=data)


# ---------------------------------------------------------------------------
# POST /holidays - Create holiday
# ---------------------------------------------------------------------------
@router.post("/holidays", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_holiday(
    body: HolidayCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Create a new holiday."""
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
        logger.exception("Failed to create holiday")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create holiday",
        )

    logger.info("User %s created holiday %r on %s", current_user, body.name, body.date)

    return ApiResponse(
        success=True,
        data=HolidayResponse.model_validate(holiday).model_dump(),
    )


# ---------------------------------------------------------------------------
# DELETE /holidays/{id} - Delete holiday
# ---------------------------------------------------------------------------
@router.delete("/holidays/{id}", response_model=ApiResponse)
def delete_holiday(
    id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Delete a holiday."""
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
        logger.exception("Failed to delete holiday %d", id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete holiday",
        )

    logger.info("User %s deleted holiday %d", current_user, id)

    return ApiResponse(success=True, data={"id": id, "deleted": True})
