"""
PiFace Attendance System - Attendance Tracking Routes

Real-time attendance status, event management, daily summaries, and SSE live stream.
"""

import asyncio
import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import (
    AttendanceEvent,
    AuditLog,
    DailySummary,
    Holiday,
    LeaveRecord,
    Person,
    SystemSetting,
)
from piface.backend.schemas import (
    ApiResponse,
    AttendanceEventCreate,
    AttendanceEventResponse,
    AttendanceEventUpdate,
    DailySummaryResponse,
)
from piface.backend.security import get_current_user, require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# SSE subscriber management
# ---------------------------------------------------------------------------
_sse_subscribers: list[asyncio.Queue] = []


def broadcast_attendance_event(event_data: dict) -> None:
    """Push an attendance event to all connected SSE subscribers.

    Call this from the face engine when a new event is logged.
    """
    for queue in _sse_subscribers:
        try:
            queue.put_nowait(event_data)
        except asyncio.QueueFull:
            logger.warning("SSE subscriber queue is full; dropping event.")


# ---------------------------------------------------------------------------
# Helper: audit log
# ---------------------------------------------------------------------------
def _log_audit(
    db: Session,
    action: str,
    target_table: str,
    target_id: int,
    performed_by: str,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
) -> None:
    """Insert a record into the audit_log table."""
    try:
        entry = AuditLog(
            action=action,
            target_table=target_table,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            performed_by=performed_by,
        )
        db.add(entry)
        db.flush()
    except Exception:
        logger.warning("Failed to write audit log.", exc_info=True)


# ---------------------------------------------------------------------------
# Helper: recompute daily summary
# ---------------------------------------------------------------------------
def recompute_daily_summary(
    db: Session, person_id: int, target_date: date
) -> None:
    """Recompute the daily summary for a specific person and date.

    Queries all events for the person on that date, computes totals,
    and UPSERTs into the daily_summaries table.
    """
    events = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.person_id == person_id,
            AttendanceEvent.date == target_date,
        )
        .order_by(AttendanceEvent.timestamp.asc())
        .all()
    )

    # Defaults
    first_in_time = None
    last_out_time = None
    total_in_out_events = len(events)
    total_hours_worked = None
    longest_break_minutes = None
    total_break_minutes = None
    is_late = None
    is_early_leave = None
    overtime_minutes = None
    summary_status = "ABSENT"

    if events:
        # Find first IN and last OUT
        for ev in events:
            if ev.event_type == "IN":
                first_in_time = ev.timestamp
                break

        for ev in reversed(events):
            if ev.event_type == "OUT":
                last_out_time = ev.timestamp
                break

        # Compute worked hours from IN/OUT pairs
        worked_seconds = 0.0
        breaks = []
        current_in = None

        for ev in events:
            if ev.event_type == "IN":
                if current_in is None:
                    current_in = ev.timestamp
            elif ev.event_type == "OUT":
                if current_in is not None:
                    delta = (ev.timestamp - current_in).total_seconds()
                    worked_seconds += delta
                    current_in = None
                # Track breaks: time between OUT and next IN
                # (handled after pairing)

        # If still clocked in (last event is IN with no OUT), count up to now
        if current_in is not None:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            # Only count if the date is today
            if target_date == date.today():
                delta = (now - current_in).total_seconds()
                worked_seconds += delta

        total_hours_worked = round(worked_seconds / 3600.0, 2) if worked_seconds > 0 else 0.0

        # Compute breaks: consecutive OUT -> IN pairs
        break_durations = []
        last_out = None
        for ev in events:
            if ev.event_type == "OUT":
                last_out = ev.timestamp
            elif ev.event_type == "IN" and last_out is not None:
                break_seconds = (ev.timestamp - last_out).total_seconds()
                if break_seconds > 0:
                    break_durations.append(break_seconds)
                last_out = None

        if break_durations:
            total_break_minutes = int(sum(break_durations) / 60.0)
            longest_break_minutes = int(max(break_durations) / 60.0)
        else:
            total_break_minutes = 0
            longest_break_minutes = 0

        # Check late / early leave / overtime from system settings
        try:
            work_start_setting = (
                db.query(SystemSetting)
                .filter(SystemSetting.key == "work_start_time")
                .first()
            )
            work_end_setting = (
                db.query(SystemSetting)
                .filter(SystemSetting.key == "work_end_time")
                .first()
            )
            work_hours_setting = (
                db.query(SystemSetting)
                .filter(SystemSetting.key == "standard_work_hours")
                .first()
            )

            if work_start_setting and first_in_time:
                parts = work_start_setting.value.split(":")
                work_start = time(int(parts[0]), int(parts[1]))
                if first_in_time.time() > work_start:
                    is_late = True
                else:
                    is_late = False

            if work_end_setting and last_out_time:
                parts = work_end_setting.value.split(":")
                work_end = time(int(parts[0]), int(parts[1]))
                if last_out_time.time() < work_end:
                    is_early_leave = True
                else:
                    is_early_leave = False

            standard_hours = 8.0
            if work_hours_setting:
                try:
                    standard_hours = float(work_hours_setting.value)
                except (ValueError, TypeError):
                    pass

            if total_hours_worked and total_hours_worked > standard_hours:
                overtime_minutes = int((total_hours_worked - standard_hours) * 60)
            else:
                overtime_minutes = 0

        except Exception:
            logger.warning(
                "Failed to check late/early/overtime settings.", exc_info=True
            )

        # Determine status
        if total_hours_worked and total_hours_worked > 0:
            standard_hours_val = 8.0
            if total_hours_worked >= standard_hours_val * 0.5:
                summary_status = "PRESENT"
            else:
                summary_status = "HALF_DAY"

    # Check leave records
    leave = (
        db.query(LeaveRecord)
        .filter(
            LeaveRecord.person_id == person_id,
            LeaveRecord.date == target_date,
        )
        .first()
    )
    if leave is not None:
        summary_status = "ON_LEAVE"

    # Check holidays
    holiday = db.query(Holiday).filter(Holiday.date == target_date).first()
    if holiday is not None:
        summary_status = "HOLIDAY"

    # UPSERT into daily_summaries
    existing = (
        db.query(DailySummary)
        .filter(
            DailySummary.person_id == person_id,
            DailySummary.date == target_date,
        )
        .first()
    )

    if existing:
        existing.first_in_time = first_in_time
        existing.last_out_time = last_out_time
        existing.total_in_out_events = total_in_out_events
        existing.total_hours_worked = total_hours_worked
        existing.longest_break_minutes = longest_break_minutes
        existing.total_break_minutes = total_break_minutes
        existing.is_late = is_late
        existing.is_early_leave = is_early_leave
        existing.overtime_minutes = overtime_minutes
        existing.status = summary_status
    else:
        summary = DailySummary(
            person_id=person_id,
            date=target_date,
            first_in_time=first_in_time,
            last_out_time=last_out_time,
            total_in_out_events=total_in_out_events,
            total_hours_worked=total_hours_worked,
            longest_break_minutes=longest_break_minutes,
            total_break_minutes=total_break_minutes,
            is_late=is_late,
            is_early_leave=is_early_leave,
            overtime_minutes=overtime_minutes,
            status=summary_status,
        )
        db.add(summary)

    try:
        db.flush()
    except Exception:
        logger.exception(
            "Failed to upsert daily summary for person %d on %s",
            person_id,
            target_date,
        )


# ---------------------------------------------------------------------------
# GET /today - All persons with current status for today
# ---------------------------------------------------------------------------
@router.get("/today", response_model=ApiResponse)
def get_today_status(
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return all active persons with their current attendance status for today."""
    today = date.today()

    try:
        persons = (
            db.query(Person)
            .filter(Person.is_active.is_(True), Person.is_unknown.is_(False))
            .order_by(Person.name)
            .all()
        )

        # Check if today is a holiday
        holiday = db.query(Holiday).filter(Holiday.date == today).first()
        is_holiday = holiday is not None

        results = []
        for person in persons:
            # Get today's events
            events = (
                db.query(AttendanceEvent)
                .filter(
                    AttendanceEvent.person_id == person.id,
                    AttendanceEvent.date == today,
                )
                .order_by(AttendanceEvent.timestamp.asc())
                .all()
            )

            # Check leave
            leave = (
                db.query(LeaveRecord)
                .filter(
                    LeaveRecord.person_id == person.id,
                    LeaveRecord.date == today,
                )
                .first()
            )

            # Determine status
            if is_holiday:
                person_status = "HOLIDAY"
            elif leave is not None:
                person_status = "ON_LEAVE"
            elif not events:
                person_status = "NOT_ARRIVED"
            else:
                last_event = events[-1]
                person_status = "IN" if last_event.event_type == "IN" else "OUT"

            # Compute first_in_time
            first_in = None
            for ev in events:
                if ev.event_type == "IN":
                    first_in = ev.timestamp
                    break

            # Last event time
            last_event_time = events[-1].timestamp if events else None

            # Hours worked so far
            hours_worked = 0.0
            current_in = None
            for ev in events:
                if ev.event_type == "IN":
                    if current_in is None:
                        current_in = ev.timestamp
                elif ev.event_type == "OUT":
                    if current_in is not None:
                        delta = (ev.timestamp - current_in).total_seconds()
                        hours_worked += delta
                        current_in = None

            # If currently clocked in, add time up to now
            if current_in is not None:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                hours_worked += (now - current_in).total_seconds()

            hours_worked = round(hours_worked / 3600.0, 2)

            results.append({
                "id": person.id,
                "name": person.name,
                "employee_id": person.employee_id,
                "department": person.department,
                "status": person_status,
                "first_in_time": first_in.isoformat() if first_in else None,
                "last_event_time": last_event_time.isoformat() if last_event_time else None,
                "hours_worked": hours_worked,
                "total_events": len(events),
            })

        # Build summary counts
        total = len(results)
        present = sum(1 for r in results if r["status"] in ("IN", "OUT"))
        absent = sum(1 for r in results if r["status"] == "NOT_ARRIVED")
        on_leave_count = sum(1 for r in results if r["status"] == "ON_LEAVE")
        on_holiday = sum(1 for r in results if r["status"] == "HOLIDAY")

        # Average hours for present employees
        present_hours = [r["hours_worked"] for r in results if r["status"] in ("IN", "OUT") and r["hours_worked"]]
        avg_hours = round(sum(present_hours) / len(present_hours), 1) if present_hours else 0

        # Include both naming conventions so frontend works
        summary = {
            "total": total,
            "present": present,
            "total_present": present,
            "absent": absent,
            "total_absent": absent,
            "on_leave": on_leave_count,
            "on_holiday": on_holiday,
            "average_hours": avg_hours,
        }

        # Map employee fields to frontend-friendly names
        for r in results:
            r["first_in"] = r["first_in_time"]
            r["hours"] = r["hours_worked"]

        return ApiResponse(success=True, data={"employees": results, "summary": summary})

    except Exception:
        logger.exception("Failed to compute today's attendance status.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve today's attendance status.",
        )


# ---------------------------------------------------------------------------
# GET /events - Paginated event log
# ---------------------------------------------------------------------------
@router.get("/events", response_model=ApiResponse)
def list_events(
    person_id: Optional[int] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    event_type: Optional[str] = Query(default=None, pattern="^(IN|OUT)$"),
    sort_by: Optional[str] = Query(default="timestamp"),
    sort_order: Optional[str] = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return a paginated list of attendance events with person name joined."""
    try:
        query = db.query(AttendanceEvent, Person.name, Person.department).join(
            Person, AttendanceEvent.person_id == Person.id
        )

        if person_id is not None:
            query = query.filter(AttendanceEvent.person_id == person_id)
        if date_from is not None:
            query = query.filter(AttendanceEvent.date >= date_from)
        if date_to is not None:
            query = query.filter(AttendanceEvent.date <= date_to)
        if event_type is not None:
            query = query.filter(AttendanceEvent.event_type == event_type)

        # Total count (before pagination)
        count_query = query.with_entities(func.count(AttendanceEvent.id))
        total = count_query.scalar() or 0

        # Sort
        sort_map = {
            "timestamp": AttendanceEvent.timestamp,
            "person_name": Person.name,
            "department": Person.department,
            "event_type": AttendanceEvent.event_type,
            "confidence": AttendanceEvent.confidence,
        }
        sort_col = sort_map.get(sort_by, AttendanceEvent.timestamp)
        order_fn = sort_col.asc() if sort_order == "asc" else sort_col.desc()

        # Paginate
        offset = (page - 1) * per_page
        rows = (
            query.order_by(order_fn)
            .offset(offset)
            .limit(per_page)
            .all()
        )

        events_data = []
        for event, person_name, department in rows:
            events_data.append({
                "id": event.id,
                "person_id": event.person_id,
                "person_name": person_name,
                "department": department,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "confidence": event.confidence,
                "snapshot_path": event.snapshot_path,
                "date": event.date.isoformat() if event.date else None,
                "is_manual": event.is_manual,
                "corrected_by": event.corrected_by,
            })

        return ApiResponse(
            success=True,
            data={
                "events": events_data,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": max(1, (total + per_page - 1) // per_page),
            },
        )

    except Exception:
        logger.exception("Failed to list attendance events.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve attendance events.",
        )


# ---------------------------------------------------------------------------
# POST /events - Manual event entry
# ---------------------------------------------------------------------------
@router.post("/events", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    body: AttendanceEventCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Create a manual attendance event."""
    # Verify person exists
    person = db.query(Person).filter(Person.id == body.person_id).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Person with id {body.person_id} not found.",
        )

    try:
        event = AttendanceEvent(
            person_id=body.person_id,
            event_type=body.event_type,
            timestamp=body.timestamp,
            is_manual=True,
            corrected_by=None,
        )
        # Store the username of who created it; corrected_by is an int column
        # so we look up the auth user id
        from piface.backend.models import AuthUser

        auth_user = (
            db.query(AuthUser).filter(AuthUser.username == current_user).first()
        )
        if auth_user:
            event.corrected_by = auth_user.id

        db.add(event)
        db.flush()

        # Audit log
        _log_audit(
            db,
            action="CREATE_EVENT",
            target_table="attendance_events",
            target_id=event.id,
            performed_by=current_user,
            new_value=json.dumps({
                "person_id": body.person_id,
                "event_type": body.event_type,
                "timestamp": body.timestamp.isoformat(),
                "is_manual": True,
            }),
        )

        # Recompute daily summary for the event's date
        event_date = body.timestamp.date()
        recompute_daily_summary(db, body.person_id, event_date)

        db.commit()

        # Return the created event
        return ApiResponse(
            success=True,
            data=AttendanceEventResponse.model_validate(event).model_dump(),
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to create manual attendance event.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create attendance event.",
        )


# ---------------------------------------------------------------------------
# PUT /events/{id} - Correct an event
# ---------------------------------------------------------------------------
@router.put("/events/{event_id}", response_model=ApiResponse)
def update_event(
    event_id: int,
    body: AttendanceEventUpdate,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Correct an existing attendance event."""
    event = db.query(AttendanceEvent).filter(AttendanceEvent.id == event_id).first()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance event with id {event_id} not found.",
        )

    old_values = {
        "event_type": event.event_type,
        "timestamp": event.timestamp.isoformat() if event.timestamp else None,
    }

    try:
        updated_fields = {}
        if body.event_type is not None:
            event.event_type = body.event_type
            updated_fields["event_type"] = body.event_type
        if body.timestamp is not None:
            event.timestamp = body.timestamp
            # Recompute the date field
            event.date = body.timestamp.date()
            updated_fields["timestamp"] = body.timestamp.isoformat()

        event.is_manual = True

        # Set corrected_by
        from piface.backend.models import AuthUser

        auth_user = (
            db.query(AuthUser).filter(AuthUser.username == current_user).first()
        )
        if auth_user:
            event.corrected_by = auth_user.id

        _log_audit(
            db,
            action="UPDATE_EVENT",
            target_table="attendance_events",
            target_id=event_id,
            performed_by=current_user,
            old_value=json.dumps(old_values),
            new_value=json.dumps(updated_fields),
        )

        # Recompute daily summary
        # If the timestamp changed, recompute for both old and new dates
        old_date = None
        if "timestamp" in old_values and old_values["timestamp"]:
            old_date = datetime.fromisoformat(old_values["timestamp"]).date()

        event_date = event.date if event.date else (event.timestamp.date() if event.timestamp else None)

        if event_date:
            recompute_daily_summary(db, event.person_id, event_date)
        if old_date and old_date != event_date:
            recompute_daily_summary(db, event.person_id, old_date)

        db.commit()
        db.refresh(event)

        return ApiResponse(
            success=True,
            data=AttendanceEventResponse.model_validate(event).model_dump(),
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to update attendance event %d.", event_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update attendance event.",
        )


# ---------------------------------------------------------------------------
# DELETE /events/{id} - Delete an erroneous event
# ---------------------------------------------------------------------------
@router.delete("/events/{event_id}", response_model=ApiResponse)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Delete an erroneous attendance event and recompute daily summary."""
    event = db.query(AttendanceEvent).filter(AttendanceEvent.id == event_id).first()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attendance event with id {event_id} not found.",
        )

    person_id = event.person_id
    event_date = event.date if event.date else (event.timestamp.date() if event.timestamp else None)

    try:
        _log_audit(
            db,
            action="DELETE_EVENT",
            target_table="attendance_events",
            target_id=event_id,
            performed_by=current_user,
            old_value=json.dumps({
                "person_id": person_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
            }),
        )

        db.delete(event)

        # Recompute daily summary
        if event_date:
            recompute_daily_summary(db, person_id, event_date)

        db.commit()

        return ApiResponse(
            success=True,
            data={"id": event_id, "deleted": True},
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to delete attendance event %d.", event_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete attendance event.",
        )


# ---------------------------------------------------------------------------
# GET /summary - Daily summaries
# ---------------------------------------------------------------------------
@router.get("/summary", response_model=ApiResponse)
def get_summaries(
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    person_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return daily summaries with optional filters."""
    try:
        query = db.query(DailySummary, Person.name).join(
            Person, DailySummary.person_id == Person.id
        )

        if person_id is not None:
            query = query.filter(DailySummary.person_id == person_id)
        if date_from is not None:
            query = query.filter(DailySummary.date >= date_from)
        if date_to is not None:
            query = query.filter(DailySummary.date <= date_to)

        rows = query.order_by(DailySummary.date.desc(), Person.name).all()

        summaries = []
        for summary, person_name in rows:
            data = DailySummaryResponse.model_validate(summary).model_dump()
            data["person_name"] = person_name
            summaries.append(data)

        return ApiResponse(success=True, data=summaries)

    except Exception:
        logger.exception("Failed to retrieve daily summaries.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve daily summaries.",
        )


# ---------------------------------------------------------------------------
# GET /live - SSE endpoint for real-time attendance events
# ---------------------------------------------------------------------------
@router.get("/live")
async def live_events(
    request: Request,
) -> StreamingResponse:
    """Server-Sent Events endpoint for real-time attendance events.

    Authentication is checked via the access_token cookie.
    Supports Last-Event-Id header for reconnection.
    """
    # Auth check from cookie
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    # Verify the token (will raise 401 if invalid)
    from piface.backend.security import verify_token

    verify_token(access_token)

    # Get Last-Event-Id for reconnection support
    last_event_id = request.headers.get("Last-Event-Id")

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_subscribers.append(queue)

    async def event_stream():
        event_counter = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
        try:
            # Send initial connection event
            yield f"id: {event_counter}\nevent: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"

            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    # Wait for an event with a timeout (for keepalive)
                    event_data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_counter += 1
                    yield f"id: {event_counter}\nevent: attendance\ndata: {json.dumps(event_data)}\n\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            if queue in _sse_subscribers:
                _sse_subscribers.remove(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Aliases: frontend calls /attendance instead of /attendance/events
# ---------------------------------------------------------------------------
@router.get("/", response_model=ApiResponse)
def list_events_alias(
    person_id: Optional[int] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    event_type: Optional[str] = Query(default=None, pattern="^(IN|OUT)$"),
    manual_only: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Alias for GET /events — the frontend calls GET /attendance directly."""
    return list_events(
        person_id=person_id,
        date_from=date_from,
        date_to=date_to,
        event_type=event_type,
        page=page,
        per_page=per_page,
        db=db,
        current_user=current_user,
    )


@router.post("/", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_event_alias(
    body: AttendanceEventCreate,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Alias for POST /events."""
    return create_event(body=body, db=db, current_user=current_user)


@router.put("/{event_id}", response_model=ApiResponse)
def update_event_alias(
    event_id: int,
    body: AttendanceEventUpdate,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Alias for PUT /events/{event_id}."""
    return update_event(event_id=event_id, body=body, db=db, current_user=current_user)


@router.delete("/{event_id}", response_model=ApiResponse)
def delete_event_alias(
    event_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Alias for DELETE /events/{event_id}."""
    return delete_event(event_id=event_id, db=db, current_user=current_user)


# ---------------------------------------------------------------------------
# GET /calendar - Monthly attendance calendar data
# ---------------------------------------------------------------------------
@router.get("/calendar", response_model=ApiResponse)
def attendance_calendar(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return daily attendance counts for a given month (for calendar view)."""
    try:
        from calendar import monthrange

        _, last_day = monthrange(year, month)
        start = date(year, month, 1)
        end = date(year, month, last_day)

        rows = (
            db.query(
                AttendanceEvent.date,
                AttendanceEvent.event_type,
                func.count(AttendanceEvent.id),
            )
            .filter(AttendanceEvent.date >= start, AttendanceEvent.date <= end)
            .group_by(AttendanceEvent.date, AttendanceEvent.event_type)
            .all()
        )

        # Build a dict of {date_str: status} for the frontend calendar
        day_counts: dict[str, dict] = {}
        for d, event_type, count in rows:
            key = d.isoformat() if d else ""
            if key not in day_counts:
                day_counts[key] = {"in": 0, "out": 0}
            if event_type == "IN":
                day_counts[key]["in"] = count
            elif event_type == "OUT":
                day_counts[key]["out"] = count

        # Convert to {date: status_string} for frontend CalendarView
        days_map: dict[str, str] = {}
        for key, counts in day_counts.items():
            if counts["in"] > 0:
                days_map[key] = "present"
            elif counts["out"] > 0:
                days_map[key] = "present"
            else:
                days_map[key] = "absent"

        return ApiResponse(success=True, data={"days": days_map})

    except Exception:
        logger.exception("Failed to generate attendance calendar.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate attendance calendar.",
        )


# ---------------------------------------------------------------------------
# GET /export - CSV export
# ---------------------------------------------------------------------------
@router.get("/export")
def export_attendance_csv(
    person_id: Optional[int] = Query(default=None),
    date_from: Optional[date] = Query(default=None),
    date_to: Optional[date] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
):
    """Export attendance events as CSV."""
    import csv
    import io

    from fastapi.responses import Response as FastAPIResponse

    query = db.query(AttendanceEvent, Person.name).join(
        Person, AttendanceEvent.person_id == Person.id
    )
    if person_id:
        query = query.filter(AttendanceEvent.person_id == person_id)
    if date_from:
        query = query.filter(AttendanceEvent.date >= date_from)
    if date_to:
        query = query.filter(AttendanceEvent.date <= date_to)
    if event_type:
        query = query.filter(AttendanceEvent.event_type == event_type)

    rows = query.order_by(AttendanceEvent.timestamp.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Time", "Name", "Type", "Confidence", "Manual"])
    for event, person_name in rows:
        writer.writerow([
            event.date.isoformat() if event.date else "",
            event.timestamp.strftime("%H:%M:%S") if event.timestamp else "",
            person_name,
            event.event_type,
            f"{event.confidence:.2f}" if event.confidence else "",
            "Yes" if event.is_manual else "No",
        ])

    return FastAPIResponse(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=attendance_export.csv"},
    )
