"""
PiFace Attendance System - Security Utilities

JWT authentication, password hashing, CSRF protection, and rate limiting.
"""

import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JWT Configuration
# ---------------------------------------------------------------------------
_JWT_SECRET_PATH = Path("/opt/piface/config/jwt_secret.key")


def _load_jwt_secret() -> str:
    """Load JWT secret from file, environment variable, or fallback."""
    if _JWT_SECRET_PATH.is_file():
        try:
            secret = _JWT_SECRET_PATH.read_text().strip()
            if secret:
                return secret
        except OSError:
            logger.warning("Failed to read JWT secret from %s", _JWT_SECRET_PATH)

    env_secret = os.environ.get("PIFACE_JWT_SECRET")
    if env_secret:
        return env_secret

    logger.warning(
        "Using development JWT secret. Do NOT use this in production."
    )
    return "dev-secret"


JWT_SECRET: str = _load_jwt_secret()
JWT_ALGORITHM: str = "HS256"
JWT_EXPIRE_HOURS: int = 2

# ---------------------------------------------------------------------------
# Password Hashing
# ---------------------------------------------------------------------------
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches the bcrypt *hashed* value."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT Helpers
# ---------------------------------------------------------------------------
def create_access_token(data: dict) -> str:
    """Create a signed JWT containing *data* with an expiration claim."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Decode and verify a JWT. Raises HTTP 401 on any failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


# ---------------------------------------------------------------------------
# FastAPI Dependencies
# ---------------------------------------------------------------------------
def get_current_user(
    access_token: Optional[str] = Cookie(default=None),
) -> str:
    """Extract and verify the JWT from the ``access_token`` cookie.

    Returns the ``sub`` (username) claim on success.
    Raises HTTP 401 if the cookie is missing or the token is invalid.
    """
    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = verify_token(access_token)
    username: Optional[str] = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return username


def require_auth(
    current_user: str = Depends(get_current_user),
) -> str:
    """Dependency that guarantees an authenticated user (returns username)."""
    return current_user


def require_setup_complete() -> None:
    """Dependency that raises HTTP 403 when setup is not finished.

    Imports the flag at call time to avoid circular imports and to pick up
    runtime changes.
    """
    from piface.backend.main import setup_complete  # noqa: WPS433

    if not setup_complete:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Setup not complete",
        )


# ---------------------------------------------------------------------------
# CSRF Middleware
# ---------------------------------------------------------------------------
class CSRFMiddleware(BaseHTTPMiddleware):
    """Protect state-changing requests with a double-submit cookie pattern.

    On successful login the route should call ``set_csrf_cookie`` to plant a
    CSRF token in a non-httpOnly cookie. This middleware then validates that
    every POST / PUT / DELETE request carries an ``X-CSRF-Token`` header whose
    value matches the cookie.
    """

    _PROTECTED_METHODS = {"POST", "PUT", "DELETE", "PATCH"}
    _SKIP_PATHS = {"/api/auth/login"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if (
            request.method in self._PROTECTED_METHODS
            and request.url.path not in self._SKIP_PATHS
        ):
            cookie_token = request.cookies.get("csrf_token")
            header_token = request.headers.get("X-CSRF-Token")
            if not cookie_token or not header_token or cookie_token != header_token:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "success": False,
                        "data": None,
                        "error": "CSRF validation failed",
                    },
                )
        return await call_next(request)


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_hex(32)


def set_csrf_cookie(response: Response) -> str:
    """Create a CSRF token, set it as a cookie on *response*, and return it."""
    token = generate_csrf_token()
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        samesite="lax",
        secure=False,
    )
    return token


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
class RateLimiter:
    """Simple in-memory rate limiter keyed by IP address.

    Usage::

        limiter = RateLimiter()
        limiter.check_rate_limit(request.client.host)
    """

    def __init__(self) -> None:
        self._store: dict[str, list[float]] = {}
        self._last_cleanup: float = time.monotonic()
        self._cleanup_interval: float = 60.0  # seconds

    def _cleanup(self, window_seconds: int) -> None:
        """Remove entries older than *window_seconds*."""
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        cutoff = now - window_seconds
        keys_to_delete: list[str] = []
        for ip, timestamps in self._store.items():
            self._store[ip] = [ts for ts in timestamps if ts > cutoff]
            if not self._store[ip]:
                keys_to_delete.append(ip)
        for key in keys_to_delete:
            del self._store[key]
        self._last_cleanup = now

    def check_rate_limit(
        self,
        ip: str,
        max_attempts: int = 5,
        window_seconds: int = 300,
    ) -> bool:
        """Record an attempt from *ip* and enforce the rate limit.

        Returns ``True`` if the request is within limits.
        Raises :class:`~fastapi.HTTPException` with status 429 if the limit
        is exceeded.
        """
        self._cleanup(window_seconds)

        now = time.monotonic()
        cutoff = now - window_seconds
        timestamps = self._store.get(ip, [])
        timestamps = [ts for ts in timestamps if ts > cutoff]
        timestamps.append(now)
        self._store[ip] = timestamps

        if len(timestamps) > max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )
        return True


# Module-level rate limiter instance (shared across the application)
rate_limiter = RateLimiter()
