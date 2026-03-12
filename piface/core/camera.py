"""PiFace Camera Module - Auto-detects USB webcam or Pi Camera Module 3.

Handles frame capture, buffering, MJPEG encoding, and auto-reconnection.
"""

import enum
import logging
import threading
import time
from typing import Generator, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraType(enum.Enum):
    """Supported camera backends."""

    USB = "usb"
    PICAMERA = "picamera"
    NONE = "none"


class Camera:
    """Thread-safe camera wrapper with auto-detection and reconnection.

    Supports USB webcams (via V4L2) and the Raspberry Pi Camera Module 3
    (via picamera2).  A background thread continuously grabs frames so that
    ``get_frame`` always returns the most recent image without blocking on
    I/O.

    Example::

        cam = Camera(width=640, height=480, fps=30)
        cam.start()
        ok, frame = cam.get_frame()
        cam.release()
    """

    _RECONNECT_INTERVAL: float = 5.0  # seconds between reconnection attempts

    def __init__(
        self,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
    ) -> None:
        self._width = width
        self._height = height
        self._fps = fps

        self._cap: Optional[cv2.VideoCapture] = None
        self._picam: object = None  # Picamera2 instance when applicable
        self._lock = threading.Lock()
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_count: int = 0
        self._running: bool = False
        self._camera_type: CameraType = CameraType.NONE
        self._connected: bool = False
        self._grab_thread: Optional[threading.Thread] = None

    # -- properties -----------------------------------------------------------

    @property
    def frame_count(self) -> int:
        """Total number of frames captured since the camera was started."""
        return self._frame_count

    @property
    def camera_type(self) -> CameraType:
        """The detected camera backend currently in use."""
        return self._camera_type

    @property
    def connected(self) -> bool:
        """Whether the camera is currently connected and delivering frames."""
        return self._connected

    # -- detection ------------------------------------------------------------

    def detect_camera(self) -> CameraType:
        """Probe for available camera hardware.

        Tries USB (V4L2) first, then falls back to picamera2.  Returns
        ``CameraType.NONE`` if nothing is found.
        """
        # --- USB webcam via V4L2 ---
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret and frame is not None:
                    logger.info("Detected USB webcam via V4L2")
                    return CameraType.USB
            else:
                cap.release()
        except Exception as exc:  # noqa: BLE001
            logger.debug("USB camera probe failed: %s", exc)

        # --- Pi Camera Module 3 via picamera2 ---
        try:
            from picamera2 import Picamera2  # type: ignore[import-untyped]

            picam = Picamera2()
            picam.close()
            logger.info("Detected Pi Camera Module via picamera2")
            return CameraType.PICAMERA
        except Exception as exc:  # noqa: BLE001
            logger.debug("picamera2 probe failed: %s", exc)

        logger.warning("No camera detected")
        return CameraType.NONE

    # -- lifecycle ------------------------------------------------------------

    def start(self) -> None:
        """Detect the camera, initialise capture, and begin the grab loop."""
        if self._running:
            logger.warning("Camera already running")
            return

        self._camera_type = self.detect_camera()
        if self._camera_type == CameraType.NONE:
            raise RuntimeError("No camera detected -- cannot start capture")

        self._open_capture()

        self._running = True
        self._grab_thread = threading.Thread(
            target=self._grab_loop, name="piface-cam-grab", daemon=True
        )
        self._grab_thread.start()
        logger.info(
            "Camera started (type=%s, %dx%d @ %d fps)",
            self._camera_type.value,
            self._width,
            self._height,
            self._fps,
        )

    def _open_capture(self) -> None:
        """Initialise the underlying capture object based on camera type."""
        if self._camera_type == CameraType.USB:
            self._cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            if not self._cap.isOpened():
                raise RuntimeError("Failed to open USB camera")
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
            self._cap.set(cv2.CAP_PROP_FPS, self._fps)
            self._connected = True

        elif self._camera_type == CameraType.PICAMERA:
            from picamera2 import Picamera2  # type: ignore[import-untyped]

            self._picam = Picamera2()
            config = self._picam.create_preview_configuration(  # type: ignore[union-attr]
                main={"size": (self._width, self._height), "format": "BGR888"}
            )
            self._picam.configure(config)  # type: ignore[union-attr]
            self._picam.start()  # type: ignore[union-attr]
            self._connected = True

    # -- frame grab loop ------------------------------------------------------

    def _grab_loop(self) -> None:
        """Continuously grab frames in a background thread.

        Always overwrites ``_latest_frame`` so that consumers get the most
        recent image.  On failure, triggers automatic reconnection.
        """
        while self._running:
            try:
                frame = self._read_one_frame()
                if frame is not None:
                    with self._lock:
                        self._latest_frame = frame
                    self._frame_count += 1
                    if not self._connected:
                        self._connected = True
                        logger.info("Camera feed restored")
                else:
                    self._handle_grab_failure()
            except Exception as exc:  # noqa: BLE001
                logger.error("Unexpected grab error: %s", exc)
                self._handle_grab_failure()

    def _read_one_frame(self) -> Optional[np.ndarray]:
        """Read a single frame from the active capture backend."""
        if self._camera_type == CameraType.USB:
            if self._cap is None or not self._cap.isOpened():
                return None
            ret, frame = self._cap.read()
            return frame if ret else None

        if self._camera_type == CameraType.PICAMERA:
            if self._picam is None:
                return None
            frame: np.ndarray = self._picam.capture_array()  # type: ignore[union-attr]
            return frame

        return None

    def _handle_grab_failure(self) -> None:
        """Mark camera as disconnected and attempt reconnection."""
        if self._connected:
            self._connected = False
            logger.warning("Camera disconnected -- starting reconnection")
        self.reconnect(max_attempts=1)

    # -- reconnection ---------------------------------------------------------

    def reconnect(self, max_attempts: Optional[int] = None) -> bool:
        """Release the current capture and try to reopen the camera.

        Args:
            max_attempts: Maximum number of reconnection attempts.  ``None``
                means retry indefinitely (until ``_running`` is ``False``).

        Returns:
            ``True`` if the camera was successfully reopened.
        """
        self._release_capture()

        attempt = 0
        while self._running:
            attempt += 1
            logger.info("Reconnection attempt %d ...", attempt)
            try:
                self._open_capture()
                # Verify with a test read.
                frame = self._read_one_frame()
                if frame is not None:
                    self._connected = True
                    logger.info("Reconnection succeeded on attempt %d", attempt)
                    return True
                self._release_capture()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Reconnection attempt %d failed: %s", attempt, exc)
                self._release_capture()

            if max_attempts is not None and attempt >= max_attempts:
                logger.warning(
                    "Reconnection failed after %d attempt(s)", attempt
                )
                return False

            time.sleep(self._RECONNECT_INTERVAL)

        return False

    # -- public frame access --------------------------------------------------

    def get_frame(self) -> tuple[bool, Optional[np.ndarray]]:
        """Return the most recent frame.

        Returns:
            A ``(success, frame)`` tuple.  ``frame`` is a copy of the
            internal buffer (safe to mutate).  Returns ``(False, None)``
            when no frame is available.
        """
        with self._lock:
            if self._latest_frame is None:
                return False, None
            return True, self._latest_frame.copy()

    def get_jpeg(self, quality: int = 70) -> Optional[bytes]:
        """Capture the latest frame and encode it as a JPEG byte string.

        Args:
            quality: JPEG quality (0--100).

        Returns:
            JPEG bytes, or ``None`` if no frame is available.
        """
        ok, frame = self.get_frame()
        if not ok or frame is None:
            return None
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        ret, buf = cv2.imencode(".jpg", frame, encode_params)
        if not ret:
            return None
        return buf.tobytes()

    def mjpeg_generator(self, fps: int = 10) -> Generator[bytes, None, None]:
        """Yield MJPEG-encoded frames suitable for an HTTP multipart stream.

        Args:
            fps: Target frame rate for the stream.

        Yields:
            Bytes containing a single MJPEG boundary + JPEG payload.
        """
        interval = 1.0 / max(fps, 1)
        boundary = b"--frame\r\n"
        while self._running:
            t0 = time.monotonic()
            jpeg = self.get_jpeg()
            if jpeg is not None:
                yield (
                    boundary
                    + b"Content-Type: image/jpeg\r\n"
                    + b"Content-Length: "
                    + str(len(jpeg)).encode()
                    + b"\r\n\r\n"
                    + jpeg
                    + b"\r\n"
                )
            elapsed = time.monotonic() - t0
            sleep_time = interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def is_connected(self) -> bool:
        """Whether the camera is currently delivering frames."""
        return self._connected

    # -- teardown -------------------------------------------------------------

    def _release_capture(self) -> None:
        """Release the underlying capture object without stopping the loop."""
        self._connected = False
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:  # noqa: BLE001
                pass
            self._cap = None
        if self._picam is not None:
            try:
                self._picam.close()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
            self._picam = None

    def release(self) -> None:
        """Stop the grab loop and release all camera resources."""
        self._running = False
        if self._grab_thread is not None:
            self._grab_thread.join(timeout=5.0)
            self._grab_thread = None
        self._release_capture()
        logger.info("Camera released")
