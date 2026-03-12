"""
PiFace Attendance System - Setup Wizard Routes

POST /company  - Save company name and admin credentials
POST /hours    - Save working-hours configuration
GET  /summary  - Return current setup configuration summary
POST /complete - Mark setup as finished
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import AuthUser, SystemSetting
from piface.backend.schemas import ApiResponse
from piface.backend.security import hash_password, require_auth

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class CompanyRequest(BaseModel):
    company_name: str
    admin_username: str
    admin_password: str


class HoursRequest(BaseModel):
    shift_start: str
    shift_end: str
    late_threshold_minutes: int
    weekend_days: list[str]


class CompleteRequest(BaseModel):
    setup_complete: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _upsert_setting(db: Session, key: str, value: str) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None:
        db.add(SystemSetting(key=key, value=value))
    else:
        row.value = value
        row.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# POST /company
# ---------------------------------------------------------------------------
@router.post("/company", response_model=ApiResponse)
def setup_company(
    body: CompanyRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    _upsert_setting(db, "company_name", body.company_name)

    # Update admin credentials
    admin = db.query(AuthUser).filter(AuthUser.username == "admin").first()
    if admin is None:
        admin = AuthUser(
            username=body.admin_username,
            password_hash=hash_password(body.admin_password),
            role="admin",
        )
        db.add(admin)
    else:
        admin.username = body.admin_username
        admin.password_hash = hash_password(body.admin_password)

    db.commit()
    return ApiResponse(success=True, data={"company_name": body.company_name})


# ---------------------------------------------------------------------------
# POST /hours
# ---------------------------------------------------------------------------
@router.post("/hours", response_model=ApiResponse)
def setup_hours(
    body: HoursRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    _upsert_setting(db, "shift_start", body.shift_start)
    _upsert_setting(db, "shift_end", body.shift_end)
    _upsert_setting(db, "late_threshold_minutes", str(body.late_threshold_minutes))
    _upsert_setting(db, "weekend_days", json.dumps(body.weekend_days))
    db.commit()
    return ApiResponse(success=True, data={"saved": True})


# ---------------------------------------------------------------------------
# GET /summary
# ---------------------------------------------------------------------------
@router.get("/summary", response_model=ApiResponse)
def setup_summary(
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    keys = [
        "company_name", "shift_start", "shift_end",
        "late_threshold_minutes", "weekend_days",
    ]
    result = {}
    for key in keys:
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if row and row.value is not None:
            if key == "weekend_days":
                try:
                    result[key] = json.loads(row.value)
                except (json.JSONDecodeError, TypeError):
                    result[key] = []
            elif key == "late_threshold_minutes":
                try:
                    result[key] = int(row.value)
                except ValueError:
                    result[key] = 15
            else:
                result[key] = row.value
    return ApiResponse(success=True, data=result)


# ---------------------------------------------------------------------------
# POST /complete
# ---------------------------------------------------------------------------
@router.post("/complete", response_model=ApiResponse)
def setup_complete_route(
    body: CompleteRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    import piface.backend.main as main_module

    _upsert_setting(db, "setup_complete", "true" if body.setup_complete else "false")
    db.commit()

    # Update the in-memory flag so the middleware stops blocking
    main_module.setup_complete = body.setup_complete

    return ApiResponse(success=True, data={"setup_complete": body.setup_complete})
