#!/usr/bin/env python3
"""PiFace Face Engine - Main recognition loop.

Runs as independent systemd service.  Processes camera frames,
recognizes faces, detects direction, logs attendance events.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import threading
import time
import uuid
from datetime import date, datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from piface.backend.database import SessionLocal
from piface.backend.models import AttendanceEvent, Person, SystemSetting
from piface.core.camera import Camera
from piface.core.event_bus import EventType, LEDClient
from piface.core.tracker import TrackedPerson, Tracker

logger = logging.getLogger("piface.face_engine")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_LOG_DIR = Path("/var/log/piface")
_SNAPSHOT_DIR_PROD = Path("/opt/piface/snapshots")
_SNAPSHOT_DIR_DEV = Path(__file__).resolve().parent.parent.parent / "snapshots"

_MODEL_PATHS = [
    "/opt/piface/models",
    str(Path.home() / ".insightface" / "models"),
    str(Path(__file__).resolve().parent.parent.parent / "models"),
]

# Frame output path for the video stream route to read.
_FRAME_PATH_PROD = Path("/run/piface/latest_frame.jpg")
_FRAME_PATH_DEV = Path("/tmp/piface-latest-frame.jpg")
_FRAME_PATH = _FRAME_PATH_PROD if _FRAME_PATH_PROD.parent.exists() else _FRAME_PATH_DEV


def _resolve_snapshot_dir() -> Path:
    """Return the first writable snapshot directory."""
    if _SNAPSHOT_DIR_PROD.exists() and os.access(_SNAPSHOT_DIR_PROD, os.W_OK):
        return _SNAPSHOT_DIR_PROD
    _SNAPSHOT_DIR_DEV.mkdir(parents=True, exist_ok=True)
    return _SNAPSHOT_DIR_DEV


def _resolve_model_root() -> str:
    """Return the first model root directory that exists."""
    for p in _MODEL_PATHS:
        if os.path.isdir(p):
            return p
    # Fallback: let InsightFace download into default location.
    return str(Path.home() / ".insightface" / "models")


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
def _configure_logging() -> None:
    """Set up rotating file + console logging for the engine process."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Console
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    # Rotating file
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            _LOG_DIR / "engine.log",
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        logger.warning("Cannot create log file handler: %s", exc)


# ---------------------------------------------------------------------------
# CLAHE preprocessor (reusable instance)
# ---------------------------------------------------------------------------
_CLAHE = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))


def _preprocess_frame(frame: np.ndarray) -> np.ndarray:
    """Apply CLAHE histogram equalisation for improved face detection in
    varying lighting conditions.
    """
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    l_ch = _CLAHE.apply(l_ch)
    enhanced = cv2.merge((l_ch, a_ch, b_ch))
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


# ---------------------------------------------------------------------------
# FaceEngine
# ---------------------------------------------------------------------------
class FaceEngine:
    """Core face-recognition loop.

    Lifecycle:  ``__init__`` -> ``run()`` (blocking) -> ``shutdown()``.
    """

    def __init__(self) -> None:
        _configure_logging()
        logger.info("Initialising FaceEngine")

        # ---- components ----
        self._camera = Camera(width=640, height=480, fps=30)
        self._tracker = Tracker()
        self._led: Optional[LEDClient] = None
        self._insightface_app: object = None  # FaceAnalysis instance

        # ---- embedding cache ----
        self.embeddings_matrix: Optional[np.ndarray] = None  # (N, 512)
        self.person_ids: list[int] = []
        self.person_names: list[str] = []

        # ---- runtime state ----
        self._running = True
        self._shutdown = threading.Event()
        self._frame_skip: int = 3
        self._last_watchdog: float = 0.0

        # ---- thresholds (overridden by DB settings) ----
        self.face_threshold: float = 0.6
        self.unknown_threshold: float = 0.55
        self.margin_threshold: float = 0.08

        # ---- snapshot dir ----
        self._snapshot_dir = _resolve_snapshot_dir()

        # ---- sd_notify helper ----
        self._sd_notifier: object = None

    # ===================================================================
    # Initialisation helpers
    # ===================================================================

    def _init_insightface(self) -> None:
        """Load InsightFace buffalo_s model."""
        try:
            import insightface  # type: ignore[import-untyped]
            from insightface.app import FaceAnalysis  # type: ignore[import-untyped]

            model_root = _resolve_model_root()
            logger.info("Loading InsightFace model from %s", model_root)

            self._insightface_app = FaceAnalysis(
                name="buffalo_s",
                root=model_root,
                providers=["CPUExecutionProvider"],
            )
            self._insightface_app.prepare(ctx_id=0, det_size=(640, 480))  # type: ignore[union-attr]
            logger.info("InsightFace model loaded successfully")

        except Exception:
            logger.exception(
                "Failed to load InsightFace model — face detection disabled"
            )
            self._insightface_app = None

    def _init_led_client(self) -> None:
        """Open persistent connection to LED controller."""
        self._led = LEDClient()
        if not self._led.connect():
            logger.warning(
                "LED controller not available — events will be retried"
            )

    def _init_watchdog(self) -> None:
        """Initialise systemd sd_notify helper."""
        try:
            import sdnotify  # type: ignore[import-untyped]

            self._sd_notifier = sdnotify.SystemdNotifier()
            logger.info("systemd notifier initialised")
        except ImportError:
            logger.debug(
                "sdnotify not available — watchdog notifications disabled"
            )

    # ===================================================================
    # Embedding cache
    # ===================================================================

    def load_embeddings(self) -> None:
        """Load all active person embeddings from DB into a NumPy matrix."""
        try:
            db = SessionLocal()
            try:
                persons = (
                    db.query(Person)
                    .filter(Person.is_active.is_(True))
                    .all()
                )

                if not persons:
                    self.embeddings_matrix = None
                    self.person_ids = []
                    self.person_names = []
                    logger.info("No enrolled persons found")
                    return

                ids: list[int] = []
                names: list[str] = []
                embeddings: list[np.ndarray] = []

                for p in persons:
                    if p.face_embedding is None:
                        continue
                    emb = np.frombuffer(p.face_embedding, dtype=np.float32)
                    if emb.shape[0] != 512:
                        logger.warning(
                            "Person %d has embedding of length %d, skipping",
                            p.id,
                            emb.shape[0],
                        )
                        continue
                    # Pre-normalise to unit vector for cosine similarity.
                    norm = np.linalg.norm(emb)
                    if norm > 1e-9:
                        emb = emb / norm
                    ids.append(p.id)
                    names.append(p.name)
                    embeddings.append(emb)

                if embeddings:
                    self.embeddings_matrix = np.stack(embeddings)  # (N, 512)
                    self.person_ids = ids
                    self.person_names = names
                    logger.info(
                        "Loaded %d person embedding(s)", len(embeddings)
                    )
                else:
                    self.embeddings_matrix = None
                    self.person_ids = []
                    self.person_names = []
            finally:
                db.close()

        except Exception:
            logger.exception("Failed to load embeddings from database")

    # ===================================================================
    # Calibration
    # ===================================================================

    def load_calibration(self) -> None:
        """Read IN / OUT direction vectors from system_settings and apply."""
        try:
            db = SessionLocal()
            try:
                in_row = (
                    db.query(SystemSetting)
                    .filter(SystemSetting.key == "in_vector")
                    .first()
                )
                out_row = (
                    db.query(SystemSetting)
                    .filter(SystemSetting.key == "out_vector")
                    .first()
                )

                if in_row and in_row.value and out_row and out_row.value:
                    in_vec = json.loads(in_row.value)
                    out_vec = json.loads(out_row.value)
                    self._tracker.set_calibration(in_vec, out_vec)
                else:
                    logger.warning(
                        "Calibration vectors not found in database — "
                        "direction detection disabled"
                    )
            finally:
                db.close()

        except Exception:
            logger.exception("Failed to load calibration from database")

    # ===================================================================
    # Config reload
    # ===================================================================

    def _load_config(self) -> None:
        """Reload engine thresholds from system_settings."""
        try:
            db = SessionLocal()
            try:
                keys = {
                    "face_threshold": self.face_threshold,
                    "unknown_threshold": self.unknown_threshold,
                    "margin_threshold": self.margin_threshold,
                    "frame_skip": float(self._frame_skip),
                    "cooldown_seconds": self._tracker.cooldown_seconds,
                }
                for key, default in keys.items():
                    row = (
                        db.query(SystemSetting)
                        .filter(SystemSetting.key == key)
                        .first()
                    )
                    if row and row.value is not None:
                        try:
                            val = float(row.value)
                        except ValueError:
                            continue
                        if key == "face_threshold":
                            self.face_threshold = val
                        elif key == "unknown_threshold":
                            self.unknown_threshold = val
                        elif key == "margin_threshold":
                            self.margin_threshold = val
                        elif key == "frame_skip":
                            self._frame_skip = max(1, int(val))
                        elif key == "cooldown_seconds":
                            self._tracker.cooldown_seconds = val
            finally:
                db.close()
        except Exception:
            logger.exception("Failed to reload config")

    # ===================================================================
    # State reconstruction
    # ===================================================================

    def reconstruct_state(self) -> None:
        """Pre-populate tracker cooldown info from today's events.

        On restart the engine needs to know which persons have recent events
        so that the cooldown logic does not immediately re-fire.
        """
        try:
            db = SessionLocal()
            try:
                today = date.today()
                events = (
                    db.query(AttendanceEvent)
                    .filter(AttendanceEvent.date == today)
                    .order_by(AttendanceEvent.timestamp.desc())
                    .all()
                )

                # Build a dict: person_id -> most recent event
                latest: dict[int, AttendanceEvent] = {}
                for ev in events:
                    if ev.person_id not in latest:
                        latest[ev.person_id] = ev

                logger.info(
                    "Reconstructed state for %d person(s) from today's events",
                    len(latest),
                )
                # State will be applied to tracks as they are created and
                # matched to persons.  Store it for later use.
                self._reconstructed_state = latest

            finally:
                db.close()
        except Exception:
            logger.exception("Failed to reconstruct state")
            self._reconstructed_state = {}

    def _apply_reconstructed_cooldown(self, track: TrackedPerson) -> None:
        """If we have a prior event for this person today, seed cooldown."""
        if not hasattr(self, "_reconstructed_state"):
            return
        if track.person_id is None:
            return

        ev = self._reconstructed_state.get(track.person_id)
        if ev is None:
            return

        if isinstance(ev.timestamp, datetime):
            track.last_event_time = ev.timestamp.timestamp()
            track.last_event_direction = ev.event_type

    # ===================================================================
    # Face matching
    # ===================================================================

    def match_face(
        self, embedding: np.ndarray
    ) -> tuple[Optional[int], Optional[str], float, bool]:
        """Match *embedding* against the enrolled embeddings cache.

        Returns
        -------
        tuple
            ``(person_id, person_name, best_score, is_unknown)``
            * Confident match: ``(id, name, score, False)``
            * Ambiguous (margin too small): ``(None, None, score, False)``
            * Unknown: ``(None, None, score, True)``
        """
        if self.embeddings_matrix is None or len(self.person_ids) == 0:
            return (None, None, 0.0, True)

        # Normalise query embedding
        emb = embedding.astype(np.float32)
        norm = np.linalg.norm(emb)
        if norm > 1e-9:
            emb = emb / norm

        # Batch cosine similarity (embeddings_matrix rows are pre-normalised)
        scores = self.embeddings_matrix @ emb  # (N,)

        # Top-2 indices
        if len(scores) == 1:
            best_idx = 0
            best_score = float(scores[0])
            margin = best_score  # no second candidate
        else:
            top2 = np.argpartition(scores, -2)[-2:]
            top2_sorted = top2[np.argsort(scores[top2])[::-1]]
            best_idx = top2_sorted[0]
            best_score = float(scores[best_idx])
            second_score = float(scores[top2_sorted[1]])
            margin = best_score - second_score

        if best_score > self.face_threshold:
            if margin > self.margin_threshold:
                return (
                    self.person_ids[best_idx],
                    self.person_names[best_idx],
                    best_score,
                    False,
                )
            # Ambiguous — two faces are too close in score.
            logger.debug(
                "Ambiguous match: score=%.3f margin=%.3f", best_score, margin
            )
            return (None, None, best_score, False)

        return (None, None, best_score, True)

    # ===================================================================
    # Unknown handling
    # ===================================================================

    def handle_unknown(
        self, embedding: np.ndarray, frame: np.ndarray
    ) -> tuple[Optional[int], Optional[str]]:
        """Register or match an unknown face.

        If *embedding* is similar to an existing unknown person, reuse that
        identity.  Otherwise create a new ``Unknown N`` person (throttled).

        Returns
        -------
        tuple
            ``(person_id, name)`` or ``(None, None)`` if throttled.
        """
        try:
            db = SessionLocal()
            try:
                # -- check against existing unknowns -------------------------
                unknowns = (
                    db.query(Person)
                    .filter(
                        Person.is_unknown.is_(True),
                        Person.is_active.is_(True),
                    )
                    .all()
                )

                emb = embedding.astype(np.float32)
                norm = np.linalg.norm(emb)
                if norm > 1e-9:
                    emb = emb / norm

                for unk in unknowns:
                    if unk.face_embedding is None:
                        continue
                    u_emb = np.frombuffer(
                        unk.face_embedding, dtype=np.float32
                    )
                    if u_emb.shape[0] != 512:
                        continue
                    u_norm = np.linalg.norm(u_emb)
                    if u_norm > 1e-9:
                        u_emb = u_emb / u_norm
                    sim = float(np.dot(emb, u_emb))
                    if sim > self.unknown_threshold:
                        logger.info(
                            "Matched existing unknown: %s (sim=%.3f)",
                            unk.name,
                            sim,
                        )
                        return (unk.id, unk.name)

                # -- throttle check ------------------------------------------
                one_hour_ago = datetime.utcnow() - timedelta(hours=1)
                recent_count = (
                    db.query(Person)
                    .filter(
                        Person.is_unknown.is_(True),
                        Person.enrolled_at >= one_hour_ago,
                    )
                    .count()
                )
                if recent_count > 20:
                    logger.warning(
                        "Unknown creation throttled: %d unknowns in last hour",
                        recent_count,
                    )
                    self._send_led_event(EventType.UNKNOWN_THROTTLE)
                    return (None, None)

                # -- atomic counter increment --------------------------------
                counter_row = (
                    db.query(SystemSetting)
                    .filter(SystemSetting.key == "unknown_counter")
                    .with_for_update()
                    .first()
                )
                if counter_row and counter_row.value is not None:
                    try:
                        next_idx = int(counter_row.value) + 1
                    except ValueError:
                        next_idx = 1
                    counter_row.value = str(next_idx)
                else:
                    next_idx = 1
                    db.add(
                        SystemSetting(key="unknown_counter", value=str(next_idx))
                    )

                name = f"Unknown {next_idx}"

                # -- save snapshot -------------------------------------------
                snapshot_name = f"{uuid.uuid4().hex}.jpg"
                snapshot_path = str(self._snapshot_dir / snapshot_name)
                try:
                    cv2.imwrite(snapshot_path, frame)
                except Exception:
                    logger.exception("Failed to save unknown snapshot")
                    snapshot_path = ""

                # -- create person -------------------------------------------
                emb_bytes = embedding.astype(np.float32).tobytes()
                person = Person(
                    name=name,
                    face_embedding=emb_bytes,
                    is_unknown=True,
                    unknown_index=next_idx,
                    is_active=True,
                )
                db.add(person)
                db.commit()
                db.refresh(person)

                logger.info("Created new unknown person: %s (id=%d)", name, person.id)
                return (person.id, name)

            finally:
                db.close()

        except Exception:
            logger.exception("Error handling unknown face")
            return (None, None)

    # ===================================================================
    # Attendance event logging
    # ===================================================================

    def log_attendance_event(
        self,
        person_id: int,
        event_type: str,
        confidence: float,
        snapshot_path: str,
        direction_vector: list[float],
    ) -> None:
        """Insert a new attendance event into the database.

        Handles cross-midnight edge case: if an OUT event has no
        corresponding IN today, the system checks yesterday's events.
        """
        try:
            db = SessionLocal()
            try:
                now = datetime.utcnow()
                today = now.date()

                # Cross-midnight handling for OUT events
                event_date = today
                if event_type == "OUT":
                    today_in = (
                        db.query(AttendanceEvent)
                        .filter(
                            AttendanceEvent.person_id == person_id,
                            AttendanceEvent.date == today,
                            AttendanceEvent.event_type == "IN",
                        )
                        .first()
                    )
                    if today_in is None:
                        yesterday = today - timedelta(days=1)
                        yesterday_in = (
                            db.query(AttendanceEvent)
                            .filter(
                                AttendanceEvent.person_id == person_id,
                                AttendanceEvent.date == yesterday,
                                AttendanceEvent.event_type == "IN",
                            )
                            .first()
                        )
                        if yesterday_in is not None:
                            event_date = yesterday
                            logger.info(
                                "Cross-midnight OUT for person %d linked to "
                                "yesterday (%s)",
                                person_id,
                                yesterday,
                            )

                event = AttendanceEvent(
                    person_id=person_id,
                    event_type=event_type,
                    timestamp=now,
                    confidence=confidence,
                    snapshot_path=snapshot_path,
                    direction_vector=json.dumps(direction_vector),
                    date=event_date,
                )
                db.add(event)
                db.commit()
                logger.info(
                    "Logged %s event for person %d (confidence=%.3f)",
                    event_type,
                    person_id,
                    confidence,
                )
            finally:
                db.close()

        except Exception:
            logger.exception(
                "Failed to log attendance event for person %d", person_id
            )

    # ===================================================================
    # LED helper
    # ===================================================================

    def _send_led_event(
        self, event_type: EventType, data: Optional[dict] = None
    ) -> None:
        """Send an event to the LED controller, swallowing errors."""
        if self._led is None:
            return
        try:
            self._led.send_event(event_type, data)
        except Exception:
            logger.debug("LED event send failed", exc_info=True)

    # ===================================================================
    # Snapshot helper
    # ===================================================================

    def _save_snapshot(self, frame: np.ndarray) -> str:
        """Save a JPEG snapshot and return its path."""
        snapshot_name = f"{uuid.uuid4().hex}.jpg"
        path = str(self._snapshot_dir / snapshot_name)
        try:
            cv2.imwrite(path, frame)
        except Exception:
            logger.exception("Failed to save snapshot")
            return ""
        return path

    # ===================================================================
    # Frame processing
    # ===================================================================

    def process_frame(self, frame: np.ndarray, frame_number: int) -> None:
        """Run full face detection + recognition + direction on *frame*."""
        if self._insightface_app is None:
            return

        try:
            enhanced = _preprocess_frame(frame)
        except Exception:
            logger.debug("CLAHE preprocessing failed, using raw frame")
            enhanced = frame

        # -- detect faces ----------------------------------------------------
        try:
            faces = self._insightface_app.get(enhanced)  # type: ignore[union-attr]
        except Exception:
            logger.exception("InsightFace detection failed")
            return

        if not faces:
            # No faces detected this frame — still update tracker age.
            self._tracker.update([], frame_number)
            return

        # -- build detection list --------------------------------------------
        detections: list[dict] = []
        for face in faces:
            try:
                bbox_raw = face.bbox.astype(int)
                bbox = (
                    int(bbox_raw[0]),
                    int(bbox_raw[1]),
                    int(bbox_raw[2]),
                    int(bbox_raw[3]),
                )
                embedding = face.embedding
                det_score = float(face.det_score) if hasattr(face, "det_score") else 0.0
            except Exception:
                logger.debug("Skipping malformed face detection", exc_info=True)
                continue

            if embedding is None:
                continue

            detections.append(
                {
                    "bbox": bbox,
                    "embedding": embedding,
                    "confidence": det_score,
                }
            )

        # -- update tracker --------------------------------------------------
        active_tracks = self._tracker.update(detections, frame_number)

        # -- per-track recognition + direction -------------------------------
        # Build a map from track to its best-matching detection embedding
        # (we matched by IoU, but need embeddings for recognition).
        # Re-use the order: detections aligns with the cost matrix cols.
        det_embeddings: dict[int, np.ndarray] = {}
        for det in detections:
            # Find the track whose current bbox best overlaps this detection.
            best_tid: Optional[int] = None
            best_iou = 0.0
            for track in active_tracks:
                iou = Tracker.compute_iou(track.bbox, det["bbox"])
                if iou > best_iou:
                    best_iou = iou
                    best_tid = track.track_id
            if best_tid is not None and best_iou > 0.5:
                det_embeddings[best_tid] = det["embedding"]

        for track in active_tracks:
            try:
                self._process_track(track, det_embeddings, frame, frame_number)
            except Exception:
                logger.exception(
                    "Error processing track %d", track.track_id
                )

    def _process_track(
        self,
        track: TrackedPerson,
        det_embeddings: dict[int, np.ndarray],
        frame: np.ndarray,
        frame_number: int,
    ) -> None:
        """Handle identity assignment, direction check, and event logging
        for a single track.
        """
        # -- identity assignment ---------------------------------------------
        if track.person_id is None:
            embedding = det_embeddings.get(track.track_id)
            if embedding is not None:
                person_id, person_name, score, is_unknown = self.match_face(
                    embedding
                )

                if person_id is not None:
                    # Known person
                    self._tracker.assign_identity(
                        track.track_id,
                        person_id,
                        person_name or "",
                        score,
                        is_unknown=False,
                    )
                    self._apply_reconstructed_cooldown(track)
                elif is_unknown:
                    # Unknown face
                    unk_id, unk_name = self.handle_unknown(embedding, frame)
                    if unk_id is not None:
                        self._tracker.assign_identity(
                            track.track_id,
                            unk_id,
                            unk_name or "",
                            score,
                            is_unknown=True,
                        )
                        self._send_led_event(EventType.UNKNOWN_DETECTED)
                # else: ambiguous — skip, will retry on next frame

        # -- direction check -------------------------------------------------
        if track.person_id is None:
            return

        direction = self._tracker.check_direction(track)
        if direction is None:
            return

        if not self._tracker.check_cooldown(track, direction):
            return

        # -- log event -------------------------------------------------------
        snapshot_path = self._save_snapshot(frame)

        # Compute raw movement vector for storage
        if len(track.centroid_history) >= 2:
            earliest = track.centroid_history[0]
            latest = track.centroid_history[-1]
            dir_vec = [latest[0] - earliest[0], latest[1] - earliest[1]]
        else:
            dir_vec = [0.0, 0.0]

        self.log_attendance_event(
            person_id=track.person_id,
            event_type=direction,
            confidence=track.confidence,
            snapshot_path=snapshot_path,
            direction_vector=dir_vec,
        )

        # Update cooldown on the track
        track.last_event_time = time.time()
        track.last_event_direction = direction

        # Send LED event
        if direction == "IN":
            self._send_led_event(
                EventType.ENTRY_CONFIRMED,
                {"person": track.person_name, "confidence": track.confidence},
            )
        else:
            self._send_led_event(
                EventType.EXIT_CONFIRMED,
                {"person": track.person_name, "confidence": track.confidence},
            )

        logger.info(
            "%s event: %s (id=%d, conf=%.3f)",
            direction,
            track.person_name,
            track.person_id,
            track.confidence,
        )

    # ===================================================================
    # Background threads
    # ===================================================================

    def _embeddings_refresh_loop(self) -> None:
        """Periodically reload embeddings from the database."""
        while not self._shutdown.wait(30.0):
            try:
                self.load_embeddings()
            except Exception:
                logger.exception("Embeddings refresh failed")

    def _config_refresh_loop(self) -> None:
        """Periodically reload config and calibration from the database."""
        while not self._shutdown.wait(60.0):
            try:
                self._load_config()
                self.load_calibration()
            except Exception:
                logger.exception("Config refresh failed")

    # ===================================================================
    # Stream frame writer
    # ===================================================================

    def _write_stream_frame(self, frame: np.ndarray) -> None:
        """Draw bounding boxes / names on a copy of *frame* and write to disk
        so that the video stream route can serve it."""
        try:
            annotated = frame.copy()
            for track in self._tracker.get_active_tracks():
                x1, y1, x2, y2 = track.bbox
                color = (0, 255, 0) if track.person_id and not track.is_unknown else (0, 0, 255)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                label = track.person_name or "detecting..."
                cv2.putText(
                    annotated, label, (x1, y1 - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
                )
            cv2.imwrite(str(_FRAME_PATH), annotated)
        except Exception:
            # Non-critical — don't crash the engine.
            logger.debug("Failed to write stream frame", exc_info=True)

    # ===================================================================
    # Watchdog
    # ===================================================================

    def _send_watchdog(self) -> None:
        """Send WATCHDOG=1 via sd_notify at most every 10 seconds."""
        now = time.monotonic()
        if now - self._last_watchdog < 10.0:
            return
        self._last_watchdog = now
        if self._sd_notifier is not None:
            try:
                self._sd_notifier.notify("WATCHDOG=1")  # type: ignore[union-attr]
            except Exception:
                logger.debug("Watchdog ping failed", exc_info=True)

    # ===================================================================
    # Main loop
    # ===================================================================

    def run(self) -> None:
        """Blocking main loop — call from the main thread."""
        logger.info("FaceEngine starting")

        # -- initialise components -------------------------------------------
        self._init_led_client()
        self._send_led_event(EventType.ENGINE_STARTING)

        self._init_insightface()
        self._init_watchdog()

        try:
            self._camera.start()
        except RuntimeError:
            logger.exception("Camera failed to start")
            self._send_led_event(EventType.CAMERA_DISCONNECTED)
            # Continue running — camera may reconnect later.

        self.load_embeddings()
        self.load_calibration()
        self._load_config()
        self.reconstruct_state()

        # -- notify systemd READY -------------------------------------------
        if self._sd_notifier is not None:
            try:
                self._sd_notifier.notify("READY=1")  # type: ignore[union-attr]
                logger.info("systemd READY=1 sent")
            except Exception:
                logger.debug("sd_notify READY failed", exc_info=True)

        # -- start background threads ----------------------------------------
        threading.Thread(
            target=self._embeddings_refresh_loop,
            name="emb-refresh",
            daemon=True,
        ).start()

        threading.Thread(
            target=self._config_refresh_loop,
            name="cfg-refresh",
            daemon=True,
        ).start()

        logger.info("Entering main processing loop")

        # -- main loop -------------------------------------------------------
        frame_number = 0
        was_connected = self._camera.connected

        while not self._shutdown.is_set():
            try:
                # Camera health monitoring
                if self._camera.connected and not was_connected:
                    self._send_led_event(EventType.CAMERA_RECONNECTED)
                    was_connected = True
                elif not self._camera.connected and was_connected:
                    self._send_led_event(EventType.CAMERA_DISCONNECTED)
                    was_connected = False

                ok, frame = self._camera.get_frame()
                if not ok or frame is None:
                    time.sleep(0.05)
                    self._send_watchdog()
                    continue

                frame_number += 1

                if frame_number % self._frame_skip == 0:
                    self.process_frame(frame, frame_number)
                else:
                    self._tracker.update_centroids_only(frame_number)

                # Write annotated frame for the stream route.
                self._write_stream_frame(frame)

                self._send_watchdog()

                # Pace the loop to avoid burning CPU when camera is fast.
                # Camera grab thread already controls real frame rate; this
                # just prevents a tight spin if get_frame returns cached data.
                time.sleep(0.001)

            except Exception:
                logger.exception("Error in main loop iteration")
                self._send_led_event(EventType.SYSTEM_ERROR)
                time.sleep(0.5)  # back off on repeated errors

        # -- cleanup ---------------------------------------------------------
        self._cleanup()

    def _cleanup(self) -> None:
        """Release all resources."""
        logger.info("Cleaning up resources")
        try:
            self._camera.release()
        except Exception:
            logger.debug("Camera release error", exc_info=True)

        if self._led is not None:
            try:
                self._led.close()
            except Exception:
                logger.debug("LED client close error", exc_info=True)

        logger.info("FaceEngine stopped")

    # ===================================================================
    # Shutdown
    # ===================================================================

    def shutdown(self) -> None:
        """Signal the main loop to stop."""
        logger.info("Shutdown requested")
        self._running = False
        self._shutdown.set()


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------
_engine: Optional[FaceEngine] = None


def _signal_handler(signum: int, frame: object) -> None:
    sig_name = signal.Signals(signum).name
    logger.info("Received %s — initiating shutdown", sig_name)
    if _engine is not None:
        _engine.shutdown()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    global _engine

    _engine = FaceEngine()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    _engine.run()


if __name__ == "__main__":
    main()
