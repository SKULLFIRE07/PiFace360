"""PiFace Event Bus - Unix domain socket IPC between face engine and LED controller."""

import enum
import json
import logging
import os
import socket
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Socket path: prefer /run/piface for production, fall back to /tmp for dev.
_PROD_SOCKET = "/run/piface/leds.sock"
_DEV_SOCKET = "/tmp/piface-leds.sock"
SOCKET_PATH = _PROD_SOCKET if os.path.isdir("/run/piface") else _DEV_SOCKET


class EventType(enum.Enum):
    """All recognised IPC events between face engine and LED controller."""

    ENTRY_CONFIRMED = "entry_confirmed"
    EXIT_CONFIRMED = "exit_confirmed"
    UNKNOWN_DETECTED = "unknown_detected"
    CAMERA_DISCONNECTED = "camera_disconnected"
    CAMERA_RECONNECTED = "camera_reconnected"
    SYSTEM_ERROR = "system_error"
    UNKNOWN_THROTTLE = "unknown_throttle"
    LOW_DISK = "low_disk_warning"
    ENGINE_STARTING = "engine_starting"
    REFRESH_CACHE = "refresh_cache"


class LEDClient:
    """Persistent client for sending events to the LED controller over a Unix
    domain socket.  Supports automatic reconnection and context-manager usage.

    Example::

        with LEDClient() as client:
            client.send_event(EventType.ENTRY_CONFIRMED)
    """

    DEFAULT_RETRY_ATTEMPTS = 5
    DEFAULT_RETRY_BACKOFF = 2.0  # seconds

    def __init__(
        self,
        socket_path: str = SOCKET_PATH,
        retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
        retry_backoff: float = DEFAULT_RETRY_BACKOFF,
    ) -> None:
        self._socket_path = socket_path
        self._retry_attempts = retry_attempts
        self._retry_backoff = retry_backoff
        self._sock: Optional[socket.socket] = None
        self._connected = False

    # -- connection management ------------------------------------------------

    def connect(self) -> bool:
        """Attempt to connect to the LED controller socket.

        Retries up to *retry_attempts* times with *retry_backoff* seconds
        between each attempt.  Returns ``True`` on success, ``False`` if all
        attempts fail (never raises).
        """
        for attempt in range(1, self._retry_attempts + 1):
            try:
                self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self._sock.settimeout(5.0)
                self._sock.connect(self._socket_path)
                self._connected = True
                logger.info(
                    "Connected to LED controller at %s (attempt %d)",
                    self._socket_path,
                    attempt,
                )
                return True
            except OSError as exc:
                logger.warning(
                    "Connection attempt %d/%d to %s failed: %s",
                    attempt,
                    self._retry_attempts,
                    self._socket_path,
                    exc,
                )
                self._cleanup_socket()
                if attempt < self._retry_attempts:
                    time.sleep(self._retry_backoff)

        logger.error(
            "Failed to connect to LED controller after %d attempts",
            self._retry_attempts,
        )
        return False

    def close(self) -> None:
        """Close the socket connection."""
        self._cleanup_socket()
        logger.debug("LEDClient connection closed")

    def _cleanup_socket(self) -> None:
        self._connected = False
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    # -- event sending --------------------------------------------------------

    def send_event(
        self, event_type: EventType, data: Optional[dict] = None
    ) -> bool:
        """Serialize *event_type* (and optional *data*) to JSON and send it to
        the LED controller.  Automatically reconnects once on failure.

        Returns ``True`` if the message was sent successfully.
        """
        message: dict = {"event": event_type.value}
        if data is not None:
            message["data"] = data

        payload = json.dumps(message).encode("utf-8") + b"\n"

        # First attempt
        if self._send_raw(payload):
            return True

        # Connection may have dropped -- try to reconnect once.
        logger.info("Reconnecting to LED controller for retry...")
        self._cleanup_socket()
        if not self.connect():
            return False

        return self._send_raw(payload)

    def _send_raw(self, payload: bytes) -> bool:
        if not self._connected or self._sock is None:
            return False
        try:
            self._sock.sendall(payload)
            return True
        except OSError as exc:
            logger.warning("Send failed: %s", exc)
            self._connected = False
            return False

    # -- context manager ------------------------------------------------------

    def __enter__(self) -> "LEDClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        self.close()


# ---------------------------------------------------------------------------
# Convenience helper
# ---------------------------------------------------------------------------

def send_led_event(
    event_type: EventType,
    data: Optional[dict] = None,
    socket_path: str = SOCKET_PATH,
) -> bool:
    """Fire-and-forget helper: open a temporary connection, send one event,
    and close.  Returns ``True`` on success.
    """
    with LEDClient(socket_path=socket_path, retry_attempts=1) as client:
        if not client._connected:
            return False
        return client.send_event(event_type, data)
