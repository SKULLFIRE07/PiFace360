"""
PiFace Attendance System - Calibration Routes

GET  /get - Return current in_vector and out_vector from settings
POST /set - Store normalised direction vectors
"""

import json
import logging
import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import SystemSetting
from piface.backend.schemas import ApiResponse, CalibrationSet
from piface.backend.security import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize(vector: list[float]) -> list[float]:
    """Return the unit-length version of *vector*. Raises if zero-length."""
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot normalise a zero-length vector",
        )
    return [v / magnitude for v in vector]


def _get_vector(db: Session, key: str) -> list[float] | None:
    """Read a JSON-encoded vector from system_settings, or return None."""
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is None or not row.value:
        return None
    try:
        return json.loads(row.value)
    except (json.JSONDecodeError, TypeError):
        return None


def _set_vector(db: Session, key: str, vector: list[float]) -> None:
    """Write a vector as JSON into system_settings."""
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    encoded = json.dumps(vector)
    if row is None:
        row = SystemSetting(key=key, value=encoded)
        db.add(row)
    else:
        row.value = encoded
        row.updated_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# GET /get - Return current calibration vectors
# ---------------------------------------------------------------------------
@router.get("/get", response_model=ApiResponse)
def get_calibration(
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return the current in_vector and out_vector from system settings."""
    in_vector = _get_vector(db, "in_vector")
    out_vector = _get_vector(db, "out_vector")

    return ApiResponse(
        success=True,
        data={
            "in_vector": in_vector,
            "out_vector": out_vector,
            "is_calibrated": in_vector is not None and out_vector is not None,
        },
    )


# ---------------------------------------------------------------------------
# POST /set - Store calibration vectors
# ---------------------------------------------------------------------------
def _parse_vector(v) -> list[float]:
    """Convert a vector from either {x1,y1,x2,y2} dict or [float...] list."""
    if isinstance(v, dict):
        # Frontend sends arrow endpoints; convert to direction vector [dx, dy]
        return [v.get("x2", 0) - v.get("x1", 0), v.get("y2", 0) - v.get("y1", 0)]
    return list(v)


@router.post("/set", response_model=ApiResponse)
def set_calibration(
    body: dict,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Accept in_vector and out_vector, normalise them, and store as JSON.

    Accepts vectors as either [float...] arrays or {x1, y1, x2, y2} dicts.
    """
    raw_in = body.get("in_vector")
    raw_out = body.get("out_vector")

    if not raw_in or not raw_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="in_vector and out_vector are required",
        )

    in_vec = _parse_vector(raw_in)
    out_vec = _parse_vector(raw_out)

    if len(in_vec) == 0 or len(out_vec) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vectors must not be empty",
        )

    in_norm = _normalize(in_vec)
    out_norm = _normalize(out_vec)

    _set_vector(db, "in_vector", in_norm)
    _set_vector(db, "out_vector", out_norm)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to save calibration vectors")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save calibration vectors",
        )

    logger.info("User %s updated calibration vectors", current_user)

    return ApiResponse(
        success=True,
        data={
            "in_vector": in_norm,
            "out_vector": out_norm,
        },
    )
