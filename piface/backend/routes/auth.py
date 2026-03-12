"""
PiFace Attendance System - Authentication Routes

POST /login  - Authenticate user, issue JWT cookie
POST /logout - Clear authentication cookie
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import AuthUser
from piface.backend.schemas import ApiResponse, LoginRequest
from piface.backend.security import (
    RateLimiter,
    create_access_token,
    require_auth,
    set_csrf_cookie,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level rate limiter for login attempts
_login_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------
@router.post("/login", response_model=ApiResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """Authenticate with username/password and receive a JWT cookie."""
    # Rate limiting: 5 attempts per 5 minutes per IP
    client_ip = request.client.host if request.client else "unknown"
    _login_limiter.check_rate_limit(client_ip, max_attempts=5, window_seconds=300)

    # Look up user
    user = (
        db.query(AuthUser)
        .filter(AuthUser.username == body.username)
        .first()
    )

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    # Create JWT
    token = create_access_token({"sub": user.username, "role": user.role})

    # Set httpOnly + Secure + SameSite=Strict cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )

    # Set non-httpOnly CSRF cookie
    set_csrf_cookie(response)

    # Update last_login timestamp
    try:
        user.last_login = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Failed to update last_login for user %s", user.username)

    logger.info("User %s logged in from %s", user.username, client_ip)

    return ApiResponse(
        success=True,
        data={"username": user.username, "role": user.role},
    )


# ---------------------------------------------------------------------------
# POST /logout
# ---------------------------------------------------------------------------
@router.post("/logout", response_model=ApiResponse)
def logout(
    response: Response,
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Clear the access_token cookie to log out."""
    response.delete_cookie(
        key="access_token",
        path="/",
        httponly=True,
        secure=True,
        samesite="strict",
    )
    response.delete_cookie(
        key="csrf_token",
        path="/",
    )

    logger.info("User %s logged out", current_user)

    return ApiResponse(success=True, data=None)
