"""
PiFace Attendance System - Backup & Restore Routes

Provides database backup download and restore upload endpoints.
"""

import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from piface.backend.database import DB_PATH, get_db, init_db
from piface.backend.schemas import ApiResponse
from piface.backend.security import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

_BACKUP_DIR = Path("/opt/piface/backups")


@router.get("/download")
def download_backup(current_user: str = Depends(require_auth)):
    """Download a copy of the current database file."""
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Database file not found",
        )

    # Create backup directory if needed
    backup_dir = _BACKUP_DIR if _BACKUP_DIR.exists() else Path(tempfile.gettempdir())
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"piface_backup_{timestamp}.db"

    # Copy with WAL checkpoint first
    try:
        from piface.backend.database import engine
        from sqlalchemy import text

        with engine.connect() as conn:
            conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
        shutil.copy2(DB_PATH, backup_path)
    except Exception as exc:
        logger.exception("Failed to create backup")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Backup failed: {exc}",
        ) from exc

    return FileResponse(
        path=str(backup_path),
        filename=backup_path.name,
        media_type="application/octet-stream",
    )


@router.post("/restore", response_model=ApiResponse)
async def restore_backup(
    file: UploadFile,
    current_user: str = Depends(require_auth),
):
    """Restore the database from an uploaded backup file.

    Validates the uploaded file is a valid SQLite database before replacing.
    """
    if not file.filename or not file.filename.endswith(".db"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a .db SQLite database",
        )

    # Read uploaded file
    content = await file.read()
    if len(content) < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is too small to be a valid database",
        )

    # Validate SQLite magic bytes
    if content[:16] != b"SQLite format 3\x00":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a valid SQLite database",
        )

    # Save current DB as rollback copy
    rollback_path = DB_PATH.with_suffix(".db.rollback")
    try:
        if DB_PATH.exists():
            shutil.copy2(DB_PATH, rollback_path)

        # Write new database
        DB_PATH.write_bytes(content)

        # Reinitialize to verify
        init_db()

        logger.info("Database restored from uploaded backup by %s", current_user)
        return ApiResponse(success=True, data={"message": "Database restored successfully"})

    except Exception as exc:
        # Rollback on failure
        logger.exception("Restore failed, attempting rollback")
        if rollback_path.exists():
            shutil.copy2(rollback_path, DB_PATH)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restore failed: {exc}",
        ) from exc
