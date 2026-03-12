"""
PiFace Attendance System - Settings Routes

GET / - Return all system settings as key-value dict (excluding auth keys)
PUT / - Update settings with audit logging
PUT /password - Change admin password
PUT /wifi - Update WiFi settings (no-op on laptop)
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import AuditLog, AuthUser, SystemSetting
from piface.backend.schemas import ApiResponse
from piface.backend.security import hash_password, require_auth, verify_password

logger = logging.getLogger(__name__)

router = APIRouter()

# Keys that must never be exposed via the settings API
_AUTH_EXCLUDED_KEYS = frozenset({
    "jwt_secret",
    "password_hash",
    "admin_password",
    "auth_secret",
    "csrf_secret",
    "api_key",
    "secret_key",
})


# ---------------------------------------------------------------------------
# GET / - Return all settings
# ---------------------------------------------------------------------------
@router.get("/", response_model=ApiResponse)
def get_settings(
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return all system settings as a key-value dictionary.

    Auth-related keys are excluded for security.
    """
    rows = db.query(SystemSetting).all()

    settings = {}
    for row in rows:
        if row.key.lower() not in _AUTH_EXCLUDED_KEYS:
            settings[row.key] = row.value

    # The useAuth hook reads setup_complete and user from this response.
    # Convert setup_complete string to boolean for the frontend.
    sc = settings.get("setup_complete", "false")
    settings["setup_complete"] = sc in ("true", "1", "yes")
    settings["user"] = {"username": current_user, "role": "admin"}

    # Parse weekend_days JSON string to list for frontend
    wd = settings.get("weekend_days")
    if wd and isinstance(wd, str):
        try:
            settings["weekend_days"] = json.loads(wd)
        except (json.JSONDecodeError, TypeError):
            pass

    return ApiResponse(success=True, data=settings)


# ---------------------------------------------------------------------------
# PUT / - Update settings
# ---------------------------------------------------------------------------
@router.put("/", response_model=ApiResponse)
def update_settings(
    body: dict,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Update system settings. Accepts a dict of {key: value} pairs.

    Values may be strings, numbers, booleans, or lists — all are serialized
    to strings for storage.
    """
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No settings provided",
        )

    # Prevent writing auth-related keys
    for key in body:
        if key.lower() in _AUTH_EXCLUDED_KEYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update auth-related setting: {key}",
            )

    updated = {}
    for key, new_value in body.items():
        # Serialize non-string values for DB storage
        if isinstance(new_value, (list, dict)):
            stored_value = json.dumps(new_value)
        elif isinstance(new_value, bool):
            stored_value = "true" if new_value else "false"
        else:
            stored_value = str(new_value)

        row = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == key)
            .first()
        )

        old_value = row.value if row else None

        if row is None:
            row = SystemSetting(key=key, value=stored_value)
            db.add(row)
        else:
            row.value = stored_value
            row.updated_at = datetime.now(timezone.utc)

        # Audit log
        audit = AuditLog(
            action="UPDATE_SETTING",
            target_table="system_settings",
            target_id=None,
            old_value=json.dumps({"key": key, "value": old_value}),
            new_value=json.dumps({"key": key, "value": stored_value}),
            performed_by=current_user,
            performed_at=datetime.now(timezone.utc),
        )
        db.add(audit)
        updated[key] = stored_value

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to update settings")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update settings",
        )

    logger.info(
        "User %s updated settings: %s",
        current_user,
        ", ".join(updated.keys()),
    )

    return ApiResponse(success=True, data=updated)


# ---------------------------------------------------------------------------
# PUT /password - Change admin password
# ---------------------------------------------------------------------------
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.put("/password", response_model=ApiResponse)
def change_password(
    body: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Change the current user's password."""
    user = db.query(AuthUser).filter(AuthUser.username == current_user).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password_hash = hash_password(body.new_password)
    db.commit()

    return ApiResponse(success=True, data={"message": "Password updated"})


# ---------------------------------------------------------------------------
# PUT /wifi - Update WiFi settings (Pi-specific, no-op on laptop)
# ---------------------------------------------------------------------------
class WifiRequest(BaseModel):
    ssid: str
    password: str


@router.put("/wifi", response_model=ApiResponse)
def update_wifi(
    body: WifiRequest,
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Update WiFi settings. On laptop/dev mode this is a no-op."""
    logger.info("WiFi update requested: SSID=%s (no-op in dev mode)", body.ssid)
    return ApiResponse(
        success=True,
        data={"message": "WiFi settings saved (no-op in development mode)"},
    )
