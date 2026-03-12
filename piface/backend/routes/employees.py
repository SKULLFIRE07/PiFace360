"""
PiFace Attendance System - Employee Management Routes

CRUD operations for employees, including face enrollment and re-enrollment
with InsightFace embedding extraction.
"""

import io
import json
import logging
import os
import struct
import tempfile
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import (
    AttendanceEvent,
    AuditLog,
    DailySummary,
    Person,
)
from piface.backend.schemas import ApiResponse, PersonResponse
from piface.backend.security import require_auth

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# InsightFace lazy initialization
# ---------------------------------------------------------------------------
_face_app = None
_face_app_init_attempted = False

try:
    import insightface  # noqa: F401
    from insightface.app import FaceAnalysis

    _INSIGHTFACE_AVAILABLE = True
except ImportError:
    _INSIGHTFACE_AVAILABLE = False
    logger.warning(
        "InsightFace not available. Face enrollment will use mock embeddings."
    )

try:
    import cv2  # noqa: F401

    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    logger.warning("OpenCV not available. Image/video processing will be limited.")


def _get_face_app():
    """Lazy-initialize and return the FaceAnalysis application."""
    global _face_app, _face_app_init_attempted

    if _face_app is not None:
        return _face_app

    if _face_app_init_attempted:
        return None

    _face_app_init_attempted = True

    if not _INSIGHTFACE_AVAILABLE:
        return None

    try:
        app = FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )
        app.prepare(ctx_id=0, det_size=(640, 640))
        _face_app = app
        logger.info("InsightFace FaceAnalysis initialized successfully.")
        return _face_app
    except Exception:
        logger.exception("Failed to initialize InsightFace.")
        return None


# ---------------------------------------------------------------------------
# File validation constants
# ---------------------------------------------------------------------------
_ALLOWED_MAGIC_BYTES = {
    # JPEG
    b"\xff\xd8\xff": "image/jpeg",
    # PNG
    b"\x89PNG": "image/png",
    # MP4 (ftyp box)
    b"\x00\x00\x00": "video/mp4",  # checked further below
    # WebM
    b"\x1a\x45\xdf\xa3": "video/webm",
    # QuickTime MOV (also uses ftyp)
}

_IMAGE_MIMES = {"image/jpeg", "image/png"}
_VIDEO_MIMES = {"video/mp4", "video/webm", "video/quicktime"}

# Snapshot storage directory
_SNAPSHOT_DIR = Path("/opt/piface/snapshots")
if not _SNAPSHOT_DIR.exists():
    _SNAPSHOT_DIR = Path(tempfile.gettempdir()) / "piface_snapshots"
_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def _detect_mime(header: bytes) -> Optional[str]:
    """Detect MIME type from magic bytes."""
    if header[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if header[:4] == b"\x89PNG":
        return "image/png"
    if header[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"
    # MP4 / QuickTime: ftyp box at offset 4
    if len(header) >= 12 and header[4:8] == b"ftyp":
        brand = header[8:12]
        if brand in (b"qt  ", b"mqt "):
            return "video/quicktime"
        return "video/mp4"
    return None


def _validate_file_type(content: bytes) -> str:
    """Validate file type via magic bytes. Returns MIME type or raises."""
    header = content[:32]
    mime = _detect_mime(header)
    if mime is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Accepted: JPEG, PNG, MP4, WebM, QuickTime.",
        )
    return mime


# ---------------------------------------------------------------------------
# Image / Video processing helpers
# ---------------------------------------------------------------------------
def _decode_image(content: bytes):
    """Decode image bytes to a numpy array (BGR). Requires OpenCV."""
    if not _CV2_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenCV is not available for image processing.",
        )
    arr = np.frombuffer(content, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to decode image file.",
        )
    return img


def _validate_image_quality(img) -> None:
    """Check image for blur, minimum size."""
    h, w = img.shape[:2]
    if h < 100 or w < 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image too small ({w}x{h}). Minimum 100x100 pixels.",
        )

    # Laplacian variance for blur detection
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < 50.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image is too blurry (score: {laplacian_var:.1f}, minimum: 50.0). "
            "Please provide a sharper image.",
        )


def _extract_faces(img):
    """Run face detection on image. Returns list of detected faces."""
    face_app = _get_face_app()
    if face_app is None:
        # Mock fallback for development
        logger.warning("Using mock face embedding (InsightFace unavailable).")
        rng = np.random.default_rng(42)
        mock_embedding = rng.standard_normal(512).astype(np.float32)
        mock_embedding = mock_embedding / np.linalg.norm(mock_embedding)

        class _MockFace:
            embedding = mock_embedding
            bbox = [0, 0, 100, 100]
            det_score = 0.99

        return [_MockFace()]

    faces = face_app.get(img)
    return faces


def _extract_embedding_from_image(content: bytes) -> tuple:
    """Extract face embedding from image bytes.

    Returns (embedding_np, face_snapshot_bytes).
    Raises HTTPException on validation failures.
    """
    img = _decode_image(content)
    _validate_image_quality(img)

    faces = _extract_faces(img)
    if len(faces) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No face detected in the image. Please provide a clear face photo.",
        )
    if len(faces) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Multiple faces ({len(faces)}) detected. "
            "Please provide an image with exactly one face.",
        )

    face = faces[0]
    embedding = face.embedding.astype(np.float32)

    # Extract face crop for snapshot
    bbox = face.bbox.astype(int)
    x1, y1, x2, y2 = bbox
    h, w = img.shape[:2]
    # Add margin
    margin = int(max(x2 - x1, y2 - y1) * 0.2)
    x1 = max(0, x1 - margin)
    y1 = max(0, y1 - margin)
    x2 = min(w, x2 + margin)
    y2 = min(h, y2 + margin)
    face_crop = img[y1:y2, x1:x2]

    if _CV2_AVAILABLE:
        _, snapshot_bytes = cv2.imencode(".jpg", face_crop)
        snapshot_bytes = snapshot_bytes.tobytes()
    else:
        snapshot_bytes = content  # fallback

    return embedding, snapshot_bytes


def _extract_embedding_from_video(content: bytes) -> tuple:
    """Extract face embedding from video bytes by sampling frames.

    Extracts frames, validates them, picks the top 10 best frames by
    detection score, averages their embeddings, and checks consistency.

    Returns (embedding_np, face_snapshot_bytes).
    """
    if not _CV2_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenCV is not available for video processing.",
        )

    # Write video to a temp file for OpenCV to read
    tmp_path = os.path.join(tempfile.gettempdir(), f"piface_enroll_{uuid.uuid4().hex}.tmp")
    try:
        with open(tmp_path, "wb") as f:
            f.write(content)

        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to open video file.",
            )

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

        # Sample up to 30 frames evenly spaced
        max_sample = min(total_frames, 30)
        if max_sample == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video contains no frames.",
            )

        sample_indices = np.linspace(0, total_frames - 1, max_sample, dtype=int)
        frame_results = []  # list of (score, embedding, frame)

        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ret, frame = cap.read()
            if not ret:
                continue

            # Skip blurry frames
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
            if blur_score < 30.0:
                continue

            faces = _extract_faces(frame)
            if len(faces) != 1:
                continue

            face = faces[0]
            det_score = float(face.det_score) if hasattr(face, "det_score") else 0.5
            frame_results.append((det_score, face.embedding.astype(np.float32), frame, face))

        cap.release()

        if len(frame_results) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No suitable face frames found in the video. "
                "Ensure the video shows exactly one face clearly.",
            )

        # Sort by detection score descending; take top 10
        frame_results.sort(key=lambda x: x[0], reverse=True)
        top_results = frame_results[:10]

        embeddings = np.array([r[1] for r in top_results])

        # Check consistency: pairwise cosine similarities
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = embeddings / np.maximum(norms, 1e-10)
        sim_matrix = normalized @ normalized.T
        # Exclude diagonal
        np.fill_diagonal(sim_matrix, 0)
        n = len(top_results)
        if n > 1:
            avg_sim = sim_matrix.sum() / (n * (n - 1))
            if avg_sim < 0.4:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Inconsistent face detections across video frames "
                    f"(similarity: {avg_sim:.2f}). Ensure only one person is visible.",
                )

        # Average embeddings
        embedding = embeddings.mean(axis=0).astype(np.float32)

        # Extract face snapshot from best frame
        best_score, _, best_frame, best_face = top_results[0]
        bbox = best_face.bbox.astype(int)
        x1, y1, x2, y2 = bbox
        h, w = best_frame.shape[:2]
        margin = int(max(x2 - x1, y2 - y1) * 0.2)
        x1 = max(0, x1 - margin)
        y1 = max(0, y1 - margin)
        x2 = min(w, x2 + margin)
        y2 = min(h, y2 + margin)
        face_crop = best_frame[y1:y2, x1:x2]
        _, snapshot_bytes = cv2.imencode(".jpg", face_crop)
        snapshot_bytes = snapshot_bytes.tobytes()

        return embedding, snapshot_bytes

    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def _normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """Normalize embedding to unit vector."""
    norm = np.linalg.norm(embedding)
    if norm < 1e-10:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Face embedding has zero magnitude; cannot normalize.",
        )
    return (embedding / norm).astype(np.float32)


def _embedding_to_bytes(embedding: np.ndarray) -> bytes:
    """Convert a 512-d float32 numpy array to raw bytes (2048 bytes)."""
    emb = embedding.astype(np.float32)
    if emb.shape != (512,):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected embedding dimension: {emb.shape}. Expected (512,).",
        )
    return emb.tobytes()


def _save_snapshot(person_id: int, snapshot_bytes: bytes) -> str:
    """Save face snapshot to disk. Returns the file path."""
    filename = f"person_{person_id}_{uuid.uuid4().hex[:8]}.jpg"
    filepath = _SNAPSHOT_DIR / filename
    filepath.write_bytes(snapshot_bytes)
    return str(filepath)


def _send_refresh_cache() -> None:
    """Send REFRESH_CACHE signal to the face engine via event bus."""
    try:
        from piface.core.event_bus import EventType, send_led_event

        send_led_event(EventType.REFRESH_CACHE)
        logger.info("Sent REFRESH_CACHE signal to face engine.")
    except Exception:
        logger.warning("Failed to send REFRESH_CACHE signal.", exc_info=True)


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
# GET / - List all active employees
# ---------------------------------------------------------------------------
@router.get("/", response_model=ApiResponse)
def list_employees(
    department: Optional[str] = Query(default=None, description="Filter by department"),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return all active employees, optionally filtered by department."""
    try:
        query = db.query(Person).filter(
            Person.is_active.is_(True),
            Person.is_unknown.is_(False),
        )
        if department:
            query = query.filter(Person.department == department)

        persons = query.order_by(Person.name).all()
        data = [PersonResponse.model_validate(p).model_dump() for p in persons]
        return ApiResponse(success=True, data=data)
    except Exception:
        logger.exception("Failed to list employees.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve employees.",
        )


# ---------------------------------------------------------------------------
# POST / - Enroll new employee
# ---------------------------------------------------------------------------
@router.post("/", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
async def enroll_employee(
    file: UploadFile = File(..., description="Face photo (JPEG/PNG) or video (MP4/WebM/MOV)"),
    name: str = Form(...),
    employee_id: Optional[str] = Form(default=None),
    department: Optional[str] = Form(default=None),
    job_title: Optional[str] = Form(default=None),
    phone: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Enroll a new employee with face photo or video."""
    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded.",
        )

    # Step 1: Validate file type via magic bytes
    mime = _validate_file_type(content)

    # Step 2: Check for duplicate employee_id
    if employee_id:
        existing = (
            db.query(Person)
            .filter(Person.employee_id == employee_id, Person.is_active.is_(True))
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee with ID '{employee_id}' already exists.",
            )

    # Step 3-4: Process image or video
    try:
        if mime in _IMAGE_MIMES:
            embedding, snapshot_bytes = _extract_embedding_from_image(content)
        elif mime in _VIDEO_MIMES:
            embedding, snapshot_bytes = _extract_embedding_from_video(content)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported MIME type: {mime}",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to process uploaded face media.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process face media. Please try again.",
        )

    # Step 5: Pre-normalize embedding to unit vector
    embedding = _normalize_embedding(embedding)
    embedding_bytes = _embedding_to_bytes(embedding)

    # Step 6: Insert Person record
    try:
        person = Person(
            name=name,
            employee_id=employee_id,
            department=department,
            job_title=job_title,
            phone=phone,
            face_embedding=embedding_bytes,
            face_image=snapshot_bytes,
            is_unknown=False,
            is_active=True,
        )
        db.add(person)
        db.flush()  # Get the ID before committing

        # Step 7: Save face snapshot to disk
        snapshot_path = _save_snapshot(person.id, snapshot_bytes)
        logger.info(
            "Face snapshot saved for person %d at %s", person.id, snapshot_path
        )

        # Step 9: Audit log
        _log_audit(
            db,
            action="ENROLL",
            target_table="persons",
            target_id=person.id,
            performed_by=current_user,
            new_value=json.dumps({"name": name, "employee_id": employee_id}),
        )

        db.commit()
        db.refresh(person)

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to save employee record.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save employee record.",
        )

    # Step 8: Send REFRESH_CACHE signal to face engine
    _send_refresh_cache()

    # Step 10: Return response
    return ApiResponse(
        success=True,
        data=PersonResponse.model_validate(person).model_dump(),
    )


# ---------------------------------------------------------------------------
# GET /{id} - Get single employee with stats
# ---------------------------------------------------------------------------
@router.get("/{person_id}", response_model=ApiResponse)
def get_employee(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Get a single employee with attendance statistics."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {person_id} not found.",
        )

    person_data = PersonResponse.model_validate(person).model_dump()

    # Compute stats
    try:
        # Total distinct days with attendance events
        total_days = (
            db.query(func.count(func.distinct(AttendanceEvent.date)))
            .filter(AttendanceEvent.person_id == person_id)
            .scalar()
        ) or 0

        # Average hours worked from daily summaries
        avg_hours = (
            db.query(func.avg(DailySummary.total_hours_worked))
            .filter(
                DailySummary.person_id == person_id,
                DailySummary.total_hours_worked.isnot(None),
            )
            .scalar()
        )
        avg_hours = round(float(avg_hours), 2) if avg_hours else 0.0

        # Last seen (most recent attendance event)
        last_event = (
            db.query(AttendanceEvent.timestamp)
            .filter(AttendanceEvent.person_id == person_id)
            .order_by(AttendanceEvent.timestamp.desc())
            .first()
        )
        last_seen = last_event[0].isoformat() if last_event else None

        person_data["stats"] = {
            "total_days": total_days,
            "avg_hours": avg_hours,
            "last_seen": last_seen,
        }
    except Exception:
        logger.warning(
            "Failed to compute stats for person %d", person_id, exc_info=True
        )
        person_data["stats"] = {
            "total_days": 0,
            "avg_hours": 0.0,
            "last_seen": None,
        }

    return ApiResponse(success=True, data=person_data)


# ---------------------------------------------------------------------------
# PUT /{id} - Update employee details
# ---------------------------------------------------------------------------
@router.put("/{person_id}", response_model=ApiResponse)
def update_employee(
    person_id: int,
    name: Optional[str] = Form(default=None),
    employee_id: Optional[str] = Form(default=None),
    department: Optional[str] = Form(default=None),
    job_title: Optional[str] = Form(default=None),
    phone: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Update employee details (name, department, etc.)."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {person_id} not found.",
        )

    old_values = {
        "name": person.name,
        "employee_id": person.employee_id,
        "department": person.department,
        "job_title": person.job_title,
        "phone": person.phone,
    }

    # Check for duplicate employee_id if changing
    if employee_id is not None and employee_id != person.employee_id:
        dup = (
            db.query(Person)
            .filter(
                Person.employee_id == employee_id,
                Person.id != person_id,
                Person.is_active.is_(True),
            )
            .first()
        )
        if dup:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Employee with ID '{employee_id}' already exists.",
            )

    # Apply updates (only non-None values)
    updated_fields = {}
    if name is not None:
        person.name = name
        updated_fields["name"] = name
    if employee_id is not None:
        person.employee_id = employee_id
        updated_fields["employee_id"] = employee_id
    if department is not None:
        person.department = department
        updated_fields["department"] = department
    if job_title is not None:
        person.job_title = job_title
        updated_fields["job_title"] = job_title
    if phone is not None:
        person.phone = phone
        updated_fields["phone"] = phone

    if not updated_fields:
        return ApiResponse(
            success=True,
            data=PersonResponse.model_validate(person).model_dump(),
        )

    try:
        _log_audit(
            db,
            action="UPDATE",
            target_table="persons",
            target_id=person_id,
            performed_by=current_user,
            old_value=json.dumps(old_values),
            new_value=json.dumps(updated_fields),
        )
        db.commit()
        db.refresh(person)
    except Exception:
        db.rollback()
        logger.exception("Failed to update employee %d.", person_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update employee.",
        )

    return ApiResponse(
        success=True,
        data=PersonResponse.model_validate(person).model_dump(),
    )


# ---------------------------------------------------------------------------
# DELETE /{id} - Soft delete employee
# ---------------------------------------------------------------------------
@router.delete("/{person_id}", response_model=ApiResponse)
def delete_employee(
    person_id: int,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Soft-delete an employee (set is_active=False)."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {person_id} not found.",
        )

    if not person.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee is already deactivated.",
        )

    try:
        person.is_active = False

        _log_audit(
            db,
            action="DELETE",
            target_table="persons",
            target_id=person_id,
            performed_by=current_user,
            old_value=json.dumps({"is_active": True}),
            new_value=json.dumps({"is_active": False}),
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to deactivate employee %d.", person_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to deactivate employee.",
        )

    # Refresh cache so face engine stops recognizing this person
    _send_refresh_cache()

    return ApiResponse(success=True, data={"id": person_id, "is_active": False})


# ---------------------------------------------------------------------------
# GET /{id}/history - Paginated attendance history
# ---------------------------------------------------------------------------
@router.get("/{person_id}/history", response_model=ApiResponse)
def get_employee_history(
    person_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return paginated attendance history for an employee."""
    # Verify person exists
    person = db.query(Person).filter(Person.id == person_id).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {person_id} not found.",
        )

    try:
        total = (
            db.query(func.count(AttendanceEvent.id))
            .filter(AttendanceEvent.person_id == person_id)
            .scalar()
        ) or 0

        offset = (page - 1) * per_page
        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.person_id == person_id)
            .order_by(AttendanceEvent.timestamp.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

        events_data = []
        for ev in events:
            events_data.append({
                "id": ev.id,
                "person_id": ev.person_id,
                "event_type": ev.event_type,
                "timestamp": ev.timestamp.isoformat() if ev.timestamp else None,
                "confidence": ev.confidence,
                "date": ev.date.isoformat() if ev.date else None,
                "is_manual": ev.is_manual,
                "corrected_by": ev.corrected_by,
            })

        return ApiResponse(
            success=True,
            data={
                "events": events_data,
                "records": events_data,  # alias for frontend
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": max(1, (total + per_page - 1) // per_page),
            },
        )
    except Exception:
        logger.exception("Failed to retrieve history for person %d.", person_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve attendance history.",
        )


# ---------------------------------------------------------------------------
# POST /{id}/reenroll - Re-enroll face with new photo/video
# ---------------------------------------------------------------------------
@router.post("/{person_id}/reenroll", response_model=ApiResponse)
async def reenroll_employee(
    person_id: int,
    file: UploadFile = File(..., description="New face photo or video"),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Re-enroll an employee's face with a new photo or video."""
    person = db.query(Person).filter(Person.id == person_id).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Employee with id {person_id} not found.",
        )

    if not person.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot re-enroll a deactivated employee.",
        )

    # Read and validate file
    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded.",
        )

    mime = _validate_file_type(content)

    # Process image or video
    try:
        if mime in _IMAGE_MIMES:
            embedding, snapshot_bytes = _extract_embedding_from_image(content)
        elif mime in _VIDEO_MIMES:
            embedding, snapshot_bytes = _extract_embedding_from_video(content)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported MIME type: {mime}",
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to process re-enrollment media for person %d.", person_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process face media. Please try again.",
        )

    # Normalize and update
    embedding = _normalize_embedding(embedding)
    embedding_bytes = _embedding_to_bytes(embedding)

    try:
        person.face_embedding = embedding_bytes
        person.face_image = snapshot_bytes

        snapshot_path = _save_snapshot(person.id, snapshot_bytes)
        logger.info(
            "Re-enrollment snapshot saved for person %d at %s",
            person.id,
            snapshot_path,
        )

        _log_audit(
            db,
            action="REENROLL",
            target_table="persons",
            target_id=person_id,
            performed_by=current_user,
            new_value=json.dumps({"action": "face_re_enrolled"}),
        )

        db.commit()
        db.refresh(person)
    except Exception:
        db.rollback()
        logger.exception("Failed to update face data for person %d.", person_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save re-enrollment data.",
        )

    # Refresh face engine cache
    _send_refresh_cache()

    return ApiResponse(
        success=True,
        data=PersonResponse.model_validate(person).model_dump(),
    )


# ---------------------------------------------------------------------------
# GET /{id}/attendance - Alias for /{id}/history (frontend compatibility)
# ---------------------------------------------------------------------------
@router.get("/{person_id}/attendance", response_model=ApiResponse)
def get_employee_attendance_alias(
    person_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Alias for GET /{person_id}/history."""
    return get_employee_history(
        person_id=person_id, page=page, per_page=per_page, db=db, current_user=current_user,
    )
