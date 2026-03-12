#!/usr/bin/env python3
"""PiFace LED Controller - Independent process for GPIO LED control.
Uses gpiozero (Pi 5 compatible via lgpio backend).
Communicates with face engine via Unix domain socket.
"""

import json
import logging
import os
import signal
import socket
import threading
import time
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("piface.led_controller")

# ---------------------------------------------------------------------------
# GPIO pin assignments
# ---------------------------------------------------------------------------
GREEN_PIN = 17
RED_PIN = 27

# ---------------------------------------------------------------------------
# Socket path (production vs development fallback)
# ---------------------------------------------------------------------------
_PROD_SOCKET = "/run/piface/leds.sock"
_DEV_SOCKET = "/tmp/piface-leds.sock"
SOCKET_PATH = _PROD_SOCKET if os.path.isdir("/run/piface") else _DEV_SOCKET

# ---------------------------------------------------------------------------
# Heartbeat timeout (seconds) — if no message arrives within this window the
# controller assumes the camera / face-engine has disconnected.
# ---------------------------------------------------------------------------
HEARTBEAT_TIMEOUT = 30.0

# ---------------------------------------------------------------------------
# gpiozero import with development fallback
# ---------------------------------------------------------------------------
try:
    from gpiozero import LED as _HwLED  # type: ignore[import-untyped]

    _GPIOZERO_AVAILABLE = True
except (ImportError, Exception):
    _GPIOZERO_AVAILABLE = False
    logger.warning(
        "gpiozero not available — using mock LEDs (development mode)"
    )


# ---------------------------------------------------------------------------
# Mock LED for non-Pi development
# ---------------------------------------------------------------------------
class _MockLED:
    """Drop-in replacement for ``gpiozero.LED`` that just logs."""

    def __init__(self, pin: int) -> None:
        self.pin = pin
        self._value = False
        self._blink_thread: Optional[threading.Thread] = None
        self._blink_stop = threading.Event()

    @property
    def value(self) -> bool:
        return self._value

    def on(self) -> None:
        self._cancel_blink()
        self._value = True
        logger.debug("MockLED pin %d ON", self.pin)

    def off(self) -> None:
        self._cancel_blink()
        self._value = False
        logger.debug("MockLED pin %d OFF", self.pin)

    def blink(
        self,
        on_time: float = 1.0,
        off_time: float = 1.0,
        n: Optional[int] = None,
        background: bool = True,
    ) -> None:
        self._cancel_blink()
        self._blink_stop.clear()
        logger.debug(
            "MockLED pin %d BLINK on=%.2f off=%.2f n=%s",
            self.pin,
            on_time,
            off_time,
            n,
        )

        def _run() -> None:
            count = 0
            while not self._blink_stop.is_set():
                if n is not None and count >= n:
                    break
                self._value = True
                if self._blink_stop.wait(on_time):
                    break
                self._value = False
                if self._blink_stop.wait(off_time):
                    break
                count += 1
            self._value = False

        if background:
            t = threading.Thread(target=_run, daemon=True)
            t.start()
            self._blink_thread = t
        else:
            _run()

    def close(self) -> None:
        self._cancel_blink()
        self._value = False

    def _cancel_blink(self) -> None:
        self._blink_stop.set()
        if self._blink_thread is not None:
            self._blink_thread.join(timeout=2.0)
            self._blink_thread = None
        self._blink_stop.clear()


# ---------------------------------------------------------------------------
# LED factory
# ---------------------------------------------------------------------------
def _make_led(pin: int):
    if _GPIOZERO_AVAILABLE:
        return _HwLED(pin)
    return _MockLED(pin)


# ---------------------------------------------------------------------------
# LED Controller
# ---------------------------------------------------------------------------
class LEDController:
    """Manages the green and red indicator LEDs and listens for events on a
    Unix domain socket.
    """

    def __init__(self, socket_path: str = SOCKET_PATH) -> None:
        self._socket_path = socket_path
        self._green = _make_led(GREEN_PIN)
        self._red = _make_led(RED_PIN)
        self._shutdown = threading.Event()
        self._last_message_time: float = time.monotonic()
        self._ongoing_pattern_thread: Optional[threading.Thread] = None
        self._ongoing_cancel = threading.Event()
        self._server_sock: Optional[socket.socket] = None
        self._sd_notifier = None

        # Event name -> handler mapping
        self._dispatch = {
            "boot_sequence": self.boot_sequence,
            "entry_confirmed": self.entry_confirmed,
            "exit_confirmed": self.exit_confirmed,
            "unknown_detected": self.unknown_detected,
            "camera_disconnected": self.camera_disconnected,
            "camera_reconnected": self.camera_reconnected,
            "system_error": self.system_error,
            "unknown_throttle": self.unknown_throttle,
            "low_disk_warning": self.low_disk_warning,
            "engine_starting": self.engine_starting,
            "all_off": self.all_off,
        }

    # -- LED pattern helpers -------------------------------------------------

    def _cancel_ongoing(self) -> None:
        """Stop any continuous background pattern."""
        self._ongoing_cancel.set()
        if self._ongoing_pattern_thread is not None:
            self._ongoing_pattern_thread.join(timeout=5.0)
            self._ongoing_pattern_thread = None
        self._ongoing_cancel.clear()

    def _start_ongoing(self, target, name: str = "ongoing") -> None:
        """Start a new continuous background pattern, cancelling any previous."""
        self._cancel_ongoing()
        self._ongoing_cancel.clear()
        t = threading.Thread(target=target, daemon=True, name=name)
        t.start()
        self._ongoing_pattern_thread = t

    # -- LED patterns --------------------------------------------------------

    def boot_sequence(self) -> None:
        """5 rapid green blinks (0.2 s on / 0.2 s off)."""
        self._cancel_ongoing()
        logger.info("Pattern: boot_sequence")
        self._green.blink(on_time=0.2, off_time=0.2, n=5, background=True)

    def entry_confirmed(self) -> None:
        """Green solid for 3 seconds."""
        self._cancel_ongoing()
        logger.info("Pattern: entry_confirmed")
        self._red.off()
        self._green.on()
        threading.Timer(3.0, self._green.off).start()

    def exit_confirmed(self) -> None:
        """Red solid for 3 seconds."""
        self._cancel_ongoing()
        logger.info("Pattern: exit_confirmed")
        self._green.off()
        self._red.on()
        threading.Timer(3.0, self._red.off).start()

    def unknown_detected(self) -> None:
        """Alternating green-red blink for 2 seconds."""
        self._cancel_ongoing()
        logger.info("Pattern: unknown_detected")

        def _pattern() -> None:
            end = time.monotonic() + 2.0
            toggle = True
            while time.monotonic() < end:
                if toggle:
                    self._green.on()
                    self._red.off()
                else:
                    self._green.off()
                    self._red.on()
                toggle = not toggle
                time.sleep(0.2)
            self._green.off()
            self._red.off()

        threading.Thread(target=_pattern, daemon=True).start()

    def camera_disconnected(self) -> None:
        """Red slow blink every 2 s — continuous until cancelled."""
        logger.info("Pattern: camera_disconnected (continuous)")

        def _pattern() -> None:
            while not self._ongoing_cancel.is_set():
                self._red.on()
                if self._ongoing_cancel.wait(1.0):
                    break
                self._red.off()
                if self._ongoing_cancel.wait(1.0):
                    break
            self._red.off()

        self._start_ongoing(_pattern, name="camera_disconnected")

    def camera_reconnected(self) -> None:
        """3 green blinks."""
        self._cancel_ongoing()
        logger.info("Pattern: camera_reconnected")
        self._red.off()
        self._green.blink(on_time=0.3, off_time=0.3, n=3, background=True)

    def system_error(self) -> None:
        """Red double blink every 3 s — continuous until cancelled."""
        logger.info("Pattern: system_error (continuous)")

        def _pattern() -> None:
            while not self._ongoing_cancel.is_set():
                # Double blink
                self._red.on()
                if self._ongoing_cancel.wait(0.15):
                    break
                self._red.off()
                if self._ongoing_cancel.wait(0.15):
                    break
                self._red.on()
                if self._ongoing_cancel.wait(0.15):
                    break
                self._red.off()
                # Pause until next cycle
                if self._ongoing_cancel.wait(2.55):
                    break
            self._red.off()

        self._start_ongoing(_pattern, name="system_error")

    def unknown_throttle(self) -> None:
        """Rapid red blinks for 5 seconds."""
        self._cancel_ongoing()
        logger.info("Pattern: unknown_throttle")
        self._green.off()

        def _pattern() -> None:
            end = time.monotonic() + 5.0
            while time.monotonic() < end:
                self._red.on()
                time.sleep(0.1)
                self._red.off()
                time.sleep(0.1)
            self._red.off()

        threading.Thread(target=_pattern, daemon=True).start()

    def low_disk_warning(self) -> None:
        """Slow red-green alternate for 5 seconds."""
        self._cancel_ongoing()
        logger.info("Pattern: low_disk_warning")

        def _pattern() -> None:
            end = time.monotonic() + 5.0
            toggle = True
            while time.monotonic() < end:
                if toggle:
                    self._red.on()
                    self._green.off()
                else:
                    self._red.off()
                    self._green.on()
                toggle = not toggle
                time.sleep(0.5)
            self._red.off()
            self._green.off()

        threading.Thread(target=_pattern, daemon=True).start()

    def engine_starting(self) -> None:
        """Both LEDs on steady."""
        self._cancel_ongoing()
        logger.info("Pattern: engine_starting")
        self._green.on()
        self._red.on()

    def all_off(self) -> None:
        """Turn off both LEDs and cancel any ongoing pattern."""
        self._cancel_ongoing()
        self._green.off()
        self._red.off()
        logger.info("All LEDs off")

    # -- Heartbeat monitoring ------------------------------------------------

    def _heartbeat_monitor(self) -> None:
        """Background thread that checks for stale connections."""
        while not self._shutdown.is_set():
            elapsed = time.monotonic() - self._last_message_time
            if elapsed > HEARTBEAT_TIMEOUT:
                logger.warning(
                    "No message from face engine for %.0f s — "
                    "triggering camera_disconnected",
                    elapsed,
                )
                self.camera_disconnected()
                # Avoid repeated triggers: reset the timer so we only fire
                # again after another full timeout period with no messages.
                self._last_message_time = time.monotonic()
            self._shutdown.wait(5.0)

    # -- Watchdog (systemd sd_notify) ----------------------------------------

    def _init_watchdog(self) -> None:
        try:
            import sdnotify  # type: ignore[import-untyped]

            self._sd_notifier = sdnotify.SystemdNotifier()
            self._sd_notifier.notify("READY=1")
            logger.info("systemd watchdog: READY=1 sent")
        except ImportError:
            logger.debug(
                "sdnotify not available — watchdog notifications disabled"
            )

    def _watchdog_loop(self) -> None:
        """Send WATCHDOG=1 every 10 seconds until shutdown."""
        while not self._shutdown.is_set():
            if self._sd_notifier is not None:
                try:
                    self._sd_notifier.notify("WATCHDOG=1")
                except Exception:
                    logger.debug("Watchdog ping failed", exc_info=True)
            self._shutdown.wait(10.0)

    # -- Socket listener -----------------------------------------------------

    def _handle_client(self, conn: socket.socket) -> None:
        """Read newline-delimited JSON messages from a single client."""
        buffer = b""
        try:
            while not self._shutdown.is_set():
                try:
                    data = conn.recv(4096)
                except OSError:
                    break
                if not data:
                    break
                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError as exc:
                        logger.warning("Invalid JSON: %s — %s", line, exc)
                        continue

                    self._last_message_time = time.monotonic()
                    event_name = msg.get("event")
                    if event_name is None:
                        logger.warning("Message missing 'event' key: %s", msg)
                        continue

                    handler = self._dispatch.get(event_name)
                    if handler is None:
                        logger.warning("Unknown event: %s", event_name)
                        continue

                    logger.info("Received event: %s", event_name)
                    try:
                        handler()
                    except Exception:
                        logger.exception(
                            "Error handling event %s", event_name
                        )
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _serve(self) -> None:
        """Bind the Unix domain socket and accept connections."""
        # Clean up stale socket file
        if os.path.exists(self._socket_path):
            try:
                os.unlink(self._socket_path)
            except OSError as exc:
                logger.error(
                    "Cannot remove stale socket %s: %s",
                    self._socket_path,
                    exc,
                )
                return

        # Ensure parent directory exists (for dev /tmp path this is a no-op)
        parent = os.path.dirname(self._socket_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.settimeout(1.0)  # allow periodic shutdown checks
        try:
            self._server_sock.bind(self._socket_path)
        except OSError as exc:
            logger.error("Cannot bind socket %s: %s", self._socket_path, exc)
            return

        self._server_sock.listen(5)
        logger.info("Listening on %s", self._socket_path)

        while not self._shutdown.is_set():
            try:
                conn, _ = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                if not self._shutdown.is_set():
                    logger.exception("Error accepting connection")
                break
            logger.info("Client connected")
            t = threading.Thread(
                target=self._handle_client, args=(conn,), daemon=True
            )
            t.start()

    # -- Signal handling ------------------------------------------------------

    def _install_signals(self) -> None:
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame) -> None:  # noqa: ANN001
        sig_name = signal.Signals(signum).name
        logger.info("Received %s — shutting down", sig_name)
        self.shutdown()

    # -- Lifecycle ------------------------------------------------------------

    def shutdown(self) -> None:
        """Gracefully stop the controller."""
        self._shutdown.set()
        self.all_off()

        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except OSError:
                pass

        # Remove socket file
        if os.path.exists(self._socket_path):
            try:
                os.unlink(self._socket_path)
            except OSError:
                pass

        # Close gpiozero LED resources
        try:
            self._green.close()
        except Exception:
            pass
        try:
            self._red.close()
        except Exception:
            pass

        logger.info("LED controller shut down cleanly")

    def run(self) -> None:
        """Main entry point — initialise LEDs, run boot sequence, listen."""
        logger.info("PiFace LED Controller starting")
        self._install_signals()
        self._init_watchdog()

        # Boot sequence
        self.boot_sequence()

        # Background threads
        threading.Thread(
            target=self._watchdog_loop, daemon=True, name="watchdog"
        ).start()
        threading.Thread(
            target=self._heartbeat_monitor, daemon=True, name="heartbeat"
        ).start()

        # Block on socket listener (main thread)
        self._serve()

        # If _serve returns (shutdown or error) ensure cleanup
        if not self._shutdown.is_set():
            self.shutdown()


# ---------------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------------
def main() -> None:
    controller = LEDController()
    controller.run()


if __name__ == "__main__":
    main()
