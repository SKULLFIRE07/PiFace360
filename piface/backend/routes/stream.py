"""
PiFace Attendance System - Video Streaming Routes

Dynamic multi-camera support: detect all connected cameras, assign roles (IN/OUT).

GET  /video?camera=in|out    - MJPEG stream from assigned camera
GET  /snapshot?camera=in|out - Single JPEG frame
GET  /cameras/detect         - Scan for all connected cameras
GET  /cameras                - Get current camera assignments
POST /cameras/assign         - Assign device indices to IN/OUT roles
"""

import asyncio
import json
import logging
import threading
from pathlib import Path

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from piface.backend.database import get_db
from piface.backend.models import SystemSetting
from piface.backend.schemas import ApiResponse
from piface.backend.security import require_auth, verify_token

logger = logging.getLogger(__name__)

router = APIRouter()

# Path where the face engine writes annotated frames (Pi production mode)
_FRAME_PATH_PROD = Path("/run/piface/latest_frame.jpg")
_FRAME_PATH_DEV = Path("/tmp/piface-latest-frame.jpg")
_FRAME_PATH = _FRAME_PATH_PROD if _FRAME_PATH_PROD.parent.exists() else _FRAME_PATH_DEV

# Concurrency limiter
_stream_semaphore = asyncio.Semaphore(8)

# Frame read settings
_FRAME_INTERVAL = 0.1  # ~10 fps

# --- Camera management ---
_cam_lock = threading.Lock()
_cameras: dict[int, object] = {}       # device_index -> cv2.VideoCapture
_last_frames: dict[int, bytes] = {}    # device_index -> last good JPEG
_placeholders: dict[str, bytes] = {}   # label -> placeholder JPEG

# Default assignments (overridden by DB settings)
_assignments: dict[str, int] = {"in": 0, "out": 2}
_assignments_loaded = False


def _load_assignments(db: Session) -> dict[str, int]:
    """Load camera assignments from system_settings."""
    global _assignments, _assignments_loaded
    if _assignments_loaded:
        return _assignments
    try:
        row = db.query(SystemSetting).filter(SystemSetting.key == "camera_assignments").first()
        if row and row.value:
            saved = json.loads(row.value)
            _assignments = {k: int(v) for k, v in saved.items() if k in ("in", "out")}
            logger.info("Loaded camera assignments: %s", _assignments)
    except Exception:
        logger.warning("Failed to load camera assignments, using defaults.")
    _assignments_loaded = True
    return _assignments


def _save_assignments(db: Session, assignments: dict[str, int]) -> None:
    """Save camera assignments to system_settings."""
    global _assignments, _assignments_loaded
    row = db.query(SystemSetting).filter(SystemSetting.key == "camera_assignments").first()
    encoded = json.dumps(assignments)
    if row is None:
        row = SystemSetting(key="camera_assignments", value=encoded)
        db.add(row)
    else:
        row.value = encoded
    _assignments = assignments
    _assignments_loaded = True


def _open_camera(device_index: int) -> bool:
    """Open a camera by device index. Thread-safe."""
    if device_index in _cameras and _cameras[device_index] is not None:
        return True
    with _cam_lock:
        if device_index in _cameras and _cameras[device_index] is not None:
            return True
        try:
            import cv2
            cap = cv2.VideoCapture(device_index)
            if cap.isOpened():
                _cameras[device_index] = cap
                logger.info("Camera device %d opened.", device_index)
                return True
            cap.release()
        except Exception:
            pass
        _cameras[device_index] = None
        return False


def _close_camera(device_index: int) -> None:
    """Release a camera. Thread-safe."""
    with _cam_lock:
        cap = _cameras.pop(device_index, None)
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
        _last_frames.pop(device_index, None)


def _close_all_cameras() -> None:
    """Release all open cameras."""
    with _cam_lock:
        for idx, cap in list(_cameras.items()):
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
        _cameras.clear()
        _last_frames.clear()


def _read_camera_frame(device_index: int) -> bytes | None:
    """Capture a frame from a specific camera."""
    cap = _cameras.get(device_index)
    if cap is None:
        return None
    try:
        import cv2
        with _cam_lock:
            ret, frame = cap.read()
            if ret and frame is not None:
                _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                jpeg = buf.tobytes()
                _last_frames[device_index] = jpeg
                return jpeg
    except Exception:
        pass
    return _last_frames.get(device_index)


def _read_frame(camera: str = "in") -> bytes | None:
    """Read a frame from the camera assigned to the given role."""
    device_index = _assignments.get(camera, 0)

    if _open_camera(device_index):
        frame = _read_camera_frame(device_index)
        if frame:
            return frame

    # Fallback: shared file (Pi mode) for IN camera only
    if camera == "in":
        try:
            if _FRAME_PATH.exists():
                data = _FRAME_PATH.read_bytes()
                if data:
                    return data
        except OSError:
            pass
    return None


def _get_placeholder(label: str = "IN Camera") -> bytes:
    """Generate a placeholder JPEG with label text."""
    if label in _placeholders:
        return _placeholders[label]
    try:
        import cv2
        import numpy as np
        img = np.zeros((240, 320, 3), dtype=np.uint8)
        if "OUT" in label.upper():
            img[:] = (40, 30, 50)
        else:
            img[:] = (50, 40, 30)
        cv2.putText(img, label, (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)
        cv2.putText(img, "No Signal", (90, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (150, 150, 150), 1)
        _, buf = cv2.imencode('.jpg', img)
        _placeholders[label] = buf.tobytes()
        return _placeholders[label]
    except Exception:
        pass
    # Minimal JFIF fallback
    fb = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10,
        0x4A, 0x46, 0x49, 0x46, 0x00, 0x01, 0x01, 0x00,
        0x00, 0x01, 0x00, 0x01, 0x00, 0x00,
        0xFF, 0xDB, 0x00, 0x43, 0x00, *([0x01] * 64),
        0xFF, 0xC0, 0x00, 0x0B, 0x08,
        0x00, 0x01, 0x00, 0x01, 0x01, 0x01, 0x11, 0x00,
        0xFF, 0xC4, 0x00, 0x1F, 0x00,
        0x00, 0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01,
        0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0A, 0x0B,
        0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00,
        0x3F, 0x00, 0x7B, 0x40,
        0xFF, 0xD9,
    ])
    _placeholders[label] = fb
    return fb


# ---------------------------------------------------------------------------
# GET /cameras/detect - Scan for all connected cameras
# ---------------------------------------------------------------------------
@router.get("/cameras/detect", response_model=ApiResponse)
def detect_cameras(
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Probe device indices 0-9 to find all connected cameras."""
    try:
        import cv2
    except ImportError:
        return ApiResponse(success=False, error="OpenCV not available")

    found = []
    for idx in range(10):
        cap = cv2.VideoCapture(idx)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            # Try to get a test frame
            ret, frame = cap.read()
            has_frame = ret and frame is not None
            cap.release()
            found.append({
                "device_index": idx,
                "resolution": f"{w}x{h}",
                "fps": round(fps, 1) if fps else 0,
                "working": has_frame,
            })
        # else: not available, skip
    return ApiResponse(success=True, data={"cameras": found, "total": len(found)})


# ---------------------------------------------------------------------------
# GET /cameras - Current camera assignments
# ---------------------------------------------------------------------------
@router.get("/cameras", response_model=ApiResponse)
def get_camera_assignments(
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Return the current IN/OUT camera assignments."""
    assignments = _load_assignments(db)
    return ApiResponse(success=True, data={
        "assignments": assignments,
        "in_device": assignments.get("in", 0),
        "out_device": assignments.get("out", 2),
    })


# ---------------------------------------------------------------------------
# POST /cameras/assign - Save camera role assignments
# ---------------------------------------------------------------------------
@router.post("/cameras/assign", response_model=ApiResponse)
def assign_cameras(
    body: dict,
    db: Session = Depends(get_db),
    current_user: str = Depends(require_auth),
) -> ApiResponse:
    """Assign device indices to IN and OUT roles.

    Body: {"in": <device_index>, "out": <device_index>}
    """
    in_dev = body.get("in")
    out_dev = body.get("out")

    if in_dev is None and out_dev is None:
        raise HTTPException(status_code=400, detail="Provide at least 'in' or 'out' device index.")

    assignments = _load_assignments(db)
    if in_dev is not None:
        assignments["in"] = int(in_dev)
    if out_dev is not None:
        assignments["out"] = int(out_dev)

    # Close all cameras so they reopen with new assignments
    _close_all_cameras()

    _save_assignments(db, assignments)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save camera assignments.")

    logger.info("User %s updated camera assignments: %s", current_user, assignments)
    return ApiResponse(success=True, data={"assignments": assignments})


# ---------------------------------------------------------------------------
# GET /video - MJPEG stream
# ---------------------------------------------------------------------------
@router.get("/video")
async def video_stream(
    camera: str = Query(default="in", regex="^(in|out)$"),
    access_token: str | None = Cookie(default=None),
):
    """Stream MJPEG video from the IN or OUT camera."""
    if access_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    verify_token(access_token)

    if _stream_semaphore._value <= 0:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Max concurrent streams reached")

    cam_label = "IN Camera" if camera == "in" else "OUT Camera"

    async def _generate():
        await _stream_semaphore.acquire()
        try:
            while True:
                frame = await asyncio.get_event_loop().run_in_executor(None, _read_frame, camera)
                if frame is None:
                    frame = _get_placeholder(cam_label)
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n"
                    b"Content-Length: " + str(len(frame)).encode() + b"\r\n"
                    b"\r\n" + frame + b"\r\n"
                )
                await asyncio.sleep(_FRAME_INTERVAL)
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            _stream_semaphore.release()

    return StreamingResponse(_generate(), media_type="multipart/x-mixed-replace; boundary=frame")


# ---------------------------------------------------------------------------
# GET /snapshot - Single JPEG frame
# ---------------------------------------------------------------------------
@router.get("/snapshot")
def snapshot(
    camera: str = Query(default="in", regex="^(in|out)$"),
    current_user: str = Depends(require_auth),
):
    """Return a single JPEG frame from the IN or OUT camera."""
    frame = _read_frame(camera)
    cam_label = "IN Camera" if camera == "in" else "OUT Camera"
    if frame is None:
        frame = _get_placeholder(cam_label)
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )
