"""
PiFace Attendance System - FastAPI Application Entry Point

Configures the ASGI application, middleware, routers, and startup logic.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from piface.backend.database import SessionLocal, init_db
from piface.backend.security import CSRFMiddleware, hash_password

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
setup_complete: bool = False


# ---------------------------------------------------------------------------
# Startup / Shutdown
# ---------------------------------------------------------------------------
def _create_default_admin() -> None:
    """Create the default admin user if one does not already exist."""
    from piface.backend.models import AuthUser  # noqa: WPS433

    db = SessionLocal()
    try:
        existing = db.query(AuthUser).filter(AuthUser.username == "admin").first()
        if existing is None:
            admin = AuthUser(
                username="admin",
                password_hash=hash_password("admin"),
                role="admin",
            )
            db.add(admin)
            db.commit()
            logger.info("Default admin user created.")
        else:
            logger.info("Admin user already exists; skipping creation.")
    except Exception:
        db.rollback()
        logger.exception("Failed to create default admin user.")
    finally:
        db.close()


def _check_setup_complete() -> None:
    """Check persistent settings to determine if initial setup is done."""
    global setup_complete  # noqa: WPS420

    from piface.backend.models import SystemSetting  # noqa: WPS433

    db = SessionLocal()
    try:
        row = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == "setup_complete")
            .first()
        )
        if row is not None and row.value in ("true", "1", "yes"):
            setup_complete = True
            logger.info("Setup is marked complete.")
        else:
            setup_complete = False
            logger.info("Setup is NOT yet complete.")
    except Exception:
        # Table may not exist yet on very first run; treat as incomplete.
        setup_complete = False
        logger.warning(
            "Could not read setup_complete setting; assuming setup incomplete."
        )
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown hooks."""
    init_db()
    _create_default_admin()
    _check_setup_complete()
    logger.info("PiFace Attendance API started.")
    yield
    logger.info("PiFace Attendance API shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PiFace Attendance API",
    version="2.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://192.168.4.1", "http://192.168.4.1", "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000", "http://localhost:8001", "http://127.0.0.1:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# CSRF Middleware
# ---------------------------------------------------------------------------
app.add_middleware(CSRFMiddleware)


# ---------------------------------------------------------------------------
# Setup Wizard Middleware
# ---------------------------------------------------------------------------
_SETUP_ALLOWED_PREFIXES = (
    "/api/auth/",
    "/api/calibration/",
    "/api/setup/",
)

_SETUP_ALLOWED_EXACT = {
    "/api/auth",
    "/api/calibration",
    "/api/setup",
}


@app.middleware("http")
async def setup_wizard_guard(request: Request, call_next):
    """Block most endpoints when initial setup is not complete."""
    if not setup_complete:
        path = request.url.path

        # Always allow auth and calibration routes
        allowed = (
            path.startswith(_SETUP_ALLOWED_PREFIXES)
            or path in _SETUP_ALLOWED_EXACT
        )

        # Allow GET and PUT on /api/settings
        if not allowed and (
            path == "/api/settings" or path.startswith("/api/settings/")
        ):
            if request.method in ("GET", "PUT"):
                allowed = True

        if not allowed and path.startswith("/api/"):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "success": False,
                    "data": None,
                    "error": "Setup not complete",
                },
            )

    return await call_next(request)


# ---------------------------------------------------------------------------
# Route imports (lazy to avoid circular-import issues at module level)
# ---------------------------------------------------------------------------
# Each route module is expected to expose an ``APIRouter`` instance.
# Import names follow the convention <domain>_router (or bare name).

from piface.backend.routes.auth import router as auth_router  # noqa: E402
from piface.backend.routes.employees import router as employees_router  # noqa: E402
from piface.backend.routes.attendance import router as attendance_router  # noqa: E402
from piface.backend.routes.unknowns import router as unknowns_router  # noqa: E402
from piface.backend.routes.reports import router as reports_router  # noqa: E402
from piface.backend.routes.leave import router as leave_router  # noqa: E402
from piface.backend.routes.holidays import router as holidays  # noqa: E402
from piface.backend.routes.settings import router as settings_router  # noqa: E402
from piface.backend.routes.calibration import router as calibration_router  # noqa: E402
from piface.backend.routes.system import router as system_router  # noqa: E402
from piface.backend.routes.stream import router as stream_router  # noqa: E402
from piface.backend.routes.backup import router as backup_router  # noqa: E402
from piface.backend.routes.setup import router as setup_router  # noqa: E402

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(employees_router, prefix="/api/employees", tags=["employees"])
app.include_router(attendance_router, prefix="/api/attendance", tags=["attendance"])
app.include_router(unknowns_router, prefix="/api/unknowns", tags=["unknowns"])
app.include_router(reports_router, prefix="/api/reports", tags=["reports"])
app.include_router(leave_router, prefix="/api/leave", tags=["leave"])
app.include_router(holidays, prefix="/api/holidays", tags=["holidays"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
app.include_router(calibration_router, prefix="/api/calibration", tags=["calibration"])
app.include_router(system_router, prefix="/api/system", tags=["system"])
app.include_router(stream_router, prefix="/api/stream", tags=["stream"])
app.include_router(backup_router, prefix="/api/backup", tags=["backup"])
app.include_router(setup_router, prefix="/api/setup", tags=["setup"])


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Uniform JSON envelope for HTTP errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": str(exc.detail),
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    """Return 422 with a human-readable summary of validation errors."""
    messages = []
    for err in exc.errors():
        loc = " -> ".join(str(part) for part in err.get("loc", []))
        messages.append(f"{loc}: {err.get('msg', 'validation error')}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "data": None,
            "error": "; ".join(messages),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled server errors."""
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "data": None,
            "error": "Internal server error",
        },
    )
