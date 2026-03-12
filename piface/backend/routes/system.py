"""
PiFace Attendance System - System Routes

GET  /status              - System status (uptime, disk, temp, camera, etc.)
GET  /health              - Health check for all services (no auth)
POST /restart/{service}   - Restart a system service
POST /factory-reset       - Full factory reset
"""

import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from piface.backend.database import DB_PATH, get_db
from piface.backend.models import (
    AttendanceEvent,
    AuditLog,
    AuthUser,
    DailySummary,
    Holiday,
    LeaveRecord,
    Person,
    SystemSetting,
)
from piface.backend.schemas import ApiResponse, SystemStatusResponse
from piface.backend.security import require_auth, verify_password

logger = logging.getLogger(__name__)

router = APIRouter()

_ALLOWED_SERVICES = frozenset({"piface-engine", "piface-leds", "face-engine", "led-controller"})
_RESTART_SCRIPT = Path("/opt/piface/helpers/restart_service.sh")
_LED_SOCKET = Path("/run/piface/leds.sock")
_THERMAL_ZONE = Path("/sys/class/thermal/thermal_zone0/temp")
_FRAME_FILE_PROD = Path("/run/piface/latest_frame.jpg")
_FRAME_FILE = _FRAME_FILE_PROD if _FRAME_FILE_PROD.parent.exists() else Path("/tmp/piface-latest-frame.jpg")


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------
class FactoryResetRequest(BaseModel):
    password: str


# ---------------------------------------------------------------------------
# GET /status - System status
# ---------------------------------------------------------------------------
@router.get("/status", response_model=ApiResponse)
def system_status(
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return system status information."""
    # Uptime
    uptime_str = "unknown"
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.read().split()[0])
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime_str = f"{days}d {hours}h {minutes}m"
    except (OSError, ValueError, IndexError):
        pass

    # Database size
    db_size_mb = 0.0
    try:
        if DB_PATH.exists():
            db_size_mb = round(DB_PATH.stat().st_size / (1024 * 1024), 2)
    except OSError:
        pass

    # Disk free
    disk_free_mb = 0.0
    try:
        stat = os.statvfs(str(DB_PATH.parent))
        disk_free_mb = round((stat.f_bavail * stat.f_frsize) / (1024 * 1024), 2)
    except OSError:
        pass

    # CPU temperature
    cpu_temp = None
    try:
        if _THERMAL_ZONE.exists():
            raw = _THERMAL_ZONE.read_text().strip()
            cpu_temp = round(int(raw) / 1000.0, 1)
    except (OSError, ValueError):
        pass

    # Camera status
    camera_status = "disconnected"
    # Check common video device paths
    for dev in ("/dev/video0", "/dev/video1"):
        if Path(dev).exists():
            camera_status = "connected"
            break
    # Also consider the shared frame file as a camera proxy
    if camera_status == "disconnected" and _FRAME_FILE.exists():
        camera_status = "connected"

    # Last detection
    last_detection = None
    try:
        row = (
            db.query(func.max(AttendanceEvent.timestamp))
            .scalar()
        )
        if row is not None:
            last_detection = row
    except Exception:
        pass

    response_data = SystemStatusResponse(
        uptime=uptime_str,
        db_size_mb=db_size_mb,
        disk_free_mb=disk_free_mb,
        cpu_temp=cpu_temp,
        camera_status=camera_status,
        last_detection=last_detection,
    )

    data = response_data.model_dump()
    # Add frontend-friendly aliases
    data["db_size"] = f"{db_size_mb} MB"
    data["disk_free"] = f"{disk_free_mb} MB"

    return ApiResponse(success=True, data=data)


# ---------------------------------------------------------------------------
# GET /health - Health check (no auth)
# ---------------------------------------------------------------------------
@router.get("/health", response_model=ApiResponse)
def health_check(
    db: Session = Depends(get_db),
) -> ApiResponse:
    """Health check for all three services. No authentication required."""
    # LED controller: check if socket exists
    led_status = "healthy" if _LED_SOCKET.exists() else "unavailable"

    # Web server: if we can respond, it's healthy
    web_status = "healthy"

    # Face engine: check PID file or recent event
    engine_status = "unknown"
    pid_file = Path("/run/piface/engine.pid")
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            # Check if process is actually running
            os.kill(pid, 0)
            engine_status = "healthy"
        except (ValueError, OSError, ProcessLookupError):
            engine_status = "unavailable"
    else:
        # Fallback: check if there was a detection in the last 5 minutes
        try:
            from datetime import timedelta

            cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
            recent = (
                db.query(AttendanceEvent)
                .filter(AttendanceEvent.timestamp >= cutoff)
                .first()
            )
            engine_status = "healthy" if recent is not None else "unknown"
        except Exception:
            engine_status = "unknown"

    return ApiResponse(
        success=True,
        data={
            "led_controller": led_status,
            "web_server": web_status,
            "face_engine": engine_status,
        },
    )


# ---------------------------------------------------------------------------
# POST /restart/{service} - Restart a service
# ---------------------------------------------------------------------------
@router.post("/restart/{service}", response_model=ApiResponse)
def restart_service(
    service: str,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Restart a system service by name."""
    if service not in _ALLOWED_SERVICES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid service name. Allowed: {', '.join(sorted(_ALLOWED_SERVICES))}",
        )

    if not _RESTART_SCRIPT.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Restart script not found",
        )

    # Audit log
    audit = AuditLog(
        action="RESTART_SERVICE",
        target_table=None,
        target_id=None,
        old_value=None,
        new_value=json.dumps({"service": service}),
        performed_by=current_user,
        performed_at=datetime.now(timezone.utc),
    )
    db.add(audit)

    try:
        db.commit()
    except Exception:
        db.rollback()

    # Execute restart
    try:
        result = subprocess.run(
            [str(_RESTART_SCRIPT), service],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            logger.error(
                "Restart script failed for %s: %s", service, result.stderr
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to restart {service}: {result.stderr.strip()}",
            )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restart of {service} timed out",
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Restart script not executable or not found",
        )

    logger.info("User %s restarted service %s", current_user, service)

    return ApiResponse(
        success=True,
        data={"service": service, "status": "restarted"},
    )


# ---------------------------------------------------------------------------
# POST /factory-reset - Full factory reset
# ---------------------------------------------------------------------------
@router.post("/factory-reset", response_model=ApiResponse)
def factory_reset(
    body: FactoryResetRequest,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Perform a full factory reset. Requires admin password verification.

    Deletes all data: attendance events, daily summaries, persons, leave
    records, and holidays. Resets settings and marks setup as incomplete.
    """
    # Verify admin password
    admin = (
        db.query(AuthUser)
        .filter(AuthUser.username == current_user)
        .first()
    )
    if admin is None or not verify_password(body.password, admin.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    # Audit log (before deletion)
    audit = AuditLog(
        action="FACTORY_RESET",
        target_table=None,
        target_id=None,
        old_value=None,
        new_value=json.dumps({"initiated_by": current_user}),
        performed_by=current_user,
        performed_at=datetime.now(timezone.utc),
    )
    db.add(audit)

    try:
        db.flush()

        # Delete data in dependency order
        db.query(AttendanceEvent).delete()
        db.query(DailySummary).delete()
        db.query(LeaveRecord).delete()
        db.query(Holiday).delete()
        db.query(Person).delete()

        # Reset settings (keep auth-related, remove everything else)
        db.query(SystemSetting).filter(
            SystemSetting.key != "setup_complete"
        ).delete()

        # Mark setup as incomplete
        setup_row = (
            db.query(SystemSetting)
            .filter(SystemSetting.key == "setup_complete")
            .first()
        )
        if setup_row:
            setup_row.value = "false"
        else:
            db.add(SystemSetting(key="setup_complete", value="false"))

        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Factory reset failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Factory reset failed",
        )

    # Update the in-memory flag
    try:
        import piface.backend.main as main_module

        main_module.setup_complete = False
    except Exception:
        pass

    logger.warning("FACTORY RESET performed by user %s", current_user)

    return ApiResponse(
        success=True,
        data={"status": "factory_reset_complete"},
    )


# ---------------------------------------------------------------------------
# POST /backup - Create a database backup
# ---------------------------------------------------------------------------
@router.post("/backup", response_model=ApiResponse)
def create_backup(
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Create a backup of the database file."""
    import shutil

    backup_dir = DB_PATH.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"attendance_{timestamp}.db"

    try:
        shutil.copy2(str(DB_PATH), str(backup_path))
    except Exception:
        logger.exception("Failed to create backup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create backup",
        )

    logger.info("Backup created by %s: %s", current_user, backup_path.name)
    return ApiResponse(success=True, data={"filename": backup_path.name})


# ---------------------------------------------------------------------------
# GET /backup/latest - Download latest backup
# ---------------------------------------------------------------------------
@router.get("/backup/latest")
def download_latest_backup(
    current_user: str = Depends(require_auth),
):
    """Download the most recent database backup."""
    from fastapi.responses import FileResponse

    backup_dir = DB_PATH.parent / "backups"
    if not backup_dir.exists():
        raise HTTPException(status_code=404, detail="No backups found")

    backups = sorted(backup_dir.glob("attendance_*.db"), reverse=True)
    if not backups:
        raise HTTPException(status_code=404, detail="No backups found")

    return FileResponse(
        path=str(backups[0]),
        media_type="application/octet-stream",
        filename=backups[0].name,
    )
