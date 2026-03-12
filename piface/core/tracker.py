"""PiFace Tracker - IoU-based multi-object tracking with direction detection."""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from scipy.optimize import linear_sum_assignment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TrackedPerson
# ---------------------------------------------------------------------------
@dataclass
class TrackedPerson:
    """State of a single tracked individual across frames."""

    track_id: int
    bbox: tuple[int, int, int, int]  # (x1, y1, x2, y2)
    confidence: float

    person_id: Optional[int] = None
    person_name: Optional[str] = None
    is_unknown: bool = False

    centroid_history: deque = field(
        default_factory=lambda: deque(maxlen=45)  # ~1.5 s at 30 fps
    )
    last_seen_frame: int = 0
    last_event_time: float = 0.0
    last_event_direction: Optional[str] = None
    frames_since_detection: int = 0

    # Cached velocity estimate (pixels / frame) for lightweight prediction.
    _velocity: Optional[tuple[float, float]] = field(
        default=None, repr=False
    )

    # -- helpers -------------------------------------------------------------

    @property
    def centroid(self) -> tuple[float, float]:
        """Centre point of the current bounding box."""
        x1, y1, x2, y2 = self.bbox
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @property
    def bbox_width(self) -> float:
        return float(self.bbox[2] - self.bbox[0])


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------
class Tracker:
    """IoU-based multi-object tracker with calibrated direction detection.

    Parameters
    ----------
    cooldown_seconds:
        Minimum seconds between two attendance events for the same track.
    direction_threshold:
        Cosine-similarity threshold to declare a direction (IN / OUT).
    min_movement_ratio:
        Movement magnitude must exceed ``min_movement_ratio * bbox_width``
        before direction is evaluated (avoids noise on stationary faces).
    """

    _MAX_UNSEEN_FRAMES: int = 15  # remove tracks unseen for this many frames

    def __init__(
        self,
        cooldown_seconds: float = 45.0,
        direction_threshold: float = 0.7,
        min_movement_ratio: float = 0.3,
    ) -> None:
        self.tracks: dict[int, TrackedPerson] = {}
        self._next_track_id: int = 0

        # Calibrated direction unit vectors (set via set_calibration).
        self.in_vector: Optional[np.ndarray] = None
        self.out_vector: Optional[np.ndarray] = None

        # Config
        self.cooldown_seconds = cooldown_seconds
        self.direction_threshold = direction_threshold
        self.min_movement_ratio = min_movement_ratio

    # -- calibration ---------------------------------------------------------

    def set_calibration(
        self,
        in_vector: list[float],
        out_vector: list[float],
    ) -> None:
        """Store normalised IN / OUT direction vectors from calibration data.

        Parameters
        ----------
        in_vector:
            Raw 2-D direction vector for the "entry" direction.
        out_vector:
            Raw 2-D direction vector for the "exit" direction.
        """
        iv = np.asarray(in_vector, dtype=np.float64)
        ov = np.asarray(out_vector, dtype=np.float64)

        iv_norm = np.linalg.norm(iv)
        ov_norm = np.linalg.norm(ov)

        if iv_norm < 1e-9 or ov_norm < 1e-9:
            logger.error(
                "Calibration vectors must be non-zero; ignoring calibration"
            )
            return

        self.in_vector = iv / iv_norm
        self.out_vector = ov / ov_norm
        logger.info(
            "Calibration set: in_vector=%s, out_vector=%s",
            self.in_vector.tolist(),
            self.out_vector.tolist(),
        )

    # -- IoU -----------------------------------------------------------------

    @staticmethod
    def compute_iou(
        box1: tuple[int, int, int, int],
        box2: tuple[int, int, int, int],
    ) -> float:
        """Compute Intersection-over-Union between two axis-aligned boxes.

        Each box is ``(x1, y1, x2, y2)``.
        """
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        inter_w = max(0, x2 - x1)
        inter_h = max(0, y2 - y1)
        inter_area = inter_w * inter_h

        if inter_area == 0:
            return 0.0

        area1 = max(0, box1[2] - box1[0]) * max(0, box1[3] - box1[1])
        area2 = max(0, box2[2] - box2[0]) * max(0, box2[3] - box2[1])
        union_area = area1 + area2 - inter_area

        if union_area == 0:
            return 0.0

        return inter_area / union_area

    # -- track lifecycle helpers ---------------------------------------------

    def _create_track(
        self,
        bbox: tuple[int, int, int, int],
        confidence: float,
        frame_number: int,
    ) -> TrackedPerson:
        """Allocate a new track and register it."""
        track = TrackedPerson(
            track_id=self._next_track_id,
            bbox=bbox,
            confidence=confidence,
            last_seen_frame=frame_number,
        )
        track.centroid_history.append(track.centroid)
        self.tracks[track.track_id] = track
        self._next_track_id += 1
        return track

    def _predict_bbox(self, track: TrackedPerson) -> tuple[int, int, int, int]:
        """Predict the next bounding-box position using cached velocity."""
        if track._velocity is None or len(track.centroid_history) < 2:
            return track.bbox

        vx, vy = track._velocity
        x1, y1, x2, y2 = track.bbox
        return (
            int(x1 + vx),
            int(y1 + vy),
            int(x2 + vx),
            int(y2 + vy),
        )

    def _update_velocity(self, track: TrackedPerson) -> None:
        """Recompute velocity from the two most recent centroids."""
        if len(track.centroid_history) >= 2:
            prev = track.centroid_history[-2]
            curr = track.centroid_history[-1]
            track._velocity = (curr[0] - prev[0], curr[1] - prev[1])

    # -- main update ---------------------------------------------------------

    def update(
        self,
        detections: list[dict],
        frame_number: int,
    ) -> list[TrackedPerson]:
        """Assign new detections to existing tracks via the Hungarian method.

        Parameters
        ----------
        detections:
            Each dict has keys ``"bbox"`` *(x1, y1, x2, y2)*,
            ``"embedding"`` *(np.ndarray)*, and ``"confidence"`` *(float)*.
        frame_number:
            Monotonically increasing frame counter.

        Returns
        -------
        list[TrackedPerson]
            All currently active tracks after the update.
        """
        # -- bootstrap: no existing tracks -----------------------------------
        if not self.tracks:
            for det in detections:
                self._create_track(det["bbox"], det["confidence"], frame_number)
            return self.get_active_tracks()

        if not detections:
            # No detections this frame — just age existing tracks.
            self._age_tracks(frame_number)
            return self.get_active_tracks()

        # -- build cost matrix (negative IoU → minimise) ---------------------
        track_ids = list(self.tracks.keys())
        n_tracks = len(track_ids)
        n_dets = len(detections)

        cost = np.zeros((n_tracks, n_dets), dtype=np.float64)
        for ti, tid in enumerate(track_ids):
            predicted = self._predict_bbox(self.tracks[tid])
            for di, det in enumerate(detections):
                iou = self.compute_iou(predicted, det["bbox"])
                cost[ti, di] = 1.0 - iou  # lower is better

        # Hungarian assignment
        row_indices, col_indices = linear_sum_assignment(cost)

        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()

        for ri, ci in zip(row_indices, col_indices):
            iou = 1.0 - cost[ri, ci]
            if iou < 0.1:
                # Too low — treat as unmatched on both sides.
                continue

            tid = track_ids[ri]
            track = self.tracks[tid]
            det = detections[ci]

            track.bbox = det["bbox"]
            track.confidence = det["confidence"]
            track.last_seen_frame = frame_number
            track.frames_since_detection = 0
            track.centroid_history.append(track.centroid)
            self._update_velocity(track)

            matched_tracks.add(tid)
            matched_dets.add(ci)

        # -- unmatched detections → new tracks -------------------------------
        for di, det in enumerate(detections):
            if di not in matched_dets:
                self._create_track(det["bbox"], det["confidence"], frame_number)

        # -- unmatched tracks → age / remove ---------------------------------
        for tid in track_ids:
            if tid not in matched_tracks:
                track = self.tracks[tid]
                track.frames_since_detection += 1
                if track.frames_since_detection > self._MAX_UNSEEN_FRAMES:
                    del self.tracks[tid]
                    logger.debug("Track %d removed (unseen)", tid)

        return self.get_active_tracks()

    # -- lightweight inter-detection update ----------------------------------

    def update_centroids_only(self, frame_number: int) -> None:
        """Predict positions between detection frames using cached velocity.

        Designed to run on frames where full detection is skipped to keep
        centroid histories current at minimal cost.
        """
        stale_ids: list[int] = []
        for tid, track in self.tracks.items():
            if track._velocity is not None:
                predicted = self._predict_bbox(track)
                track.bbox = predicted
                track.centroid_history.append(track.centroid)

            track.frames_since_detection += 1
            if track.frames_since_detection > self._MAX_UNSEEN_FRAMES:
                stale_ids.append(tid)

        for tid in stale_ids:
            del self.tracks[tid]
            logger.debug("Track %d removed during centroid-only update", tid)

    # -- identity assignment -------------------------------------------------

    def assign_identity(
        self,
        track_id: int,
        person_id: int,
        person_name: str,
        confidence: float,
        is_unknown: bool,
    ) -> None:
        """Bind a face-recognition result to an existing track."""
        track = self.tracks.get(track_id)
        if track is None:
            logger.warning(
                "assign_identity: track %d does not exist", track_id
            )
            return

        track.person_id = person_id
        track.person_name = person_name
        track.confidence = confidence
        track.is_unknown = is_unknown

    # -- direction detection -------------------------------------------------

    def check_direction(self, track: TrackedPerson) -> Optional[str]:
        """Determine whether *track* is moving IN, OUT, or neither.

        Returns ``"IN"``, ``"OUT"``, or ``None`` (stationary / ambiguous /
        uncalibrated).
        """
        if self.in_vector is None or self.out_vector is None:
            return None

        if len(track.centroid_history) < 10:
            return None

        earliest = track.centroid_history[0]
        latest = track.centroid_history[-1]

        movement = np.array(
            [latest[0] - earliest[0], latest[1] - earliest[1]],
            dtype=np.float64,
        )
        magnitude = np.linalg.norm(movement)

        # Minimum movement check — must exceed a fraction of the face width
        # to guard against jitter on stationary subjects.
        min_movement = self.min_movement_ratio * track.bbox_width
        if magnitude < min_movement:
            return None

        # Unit movement vector
        unit_movement = movement / magnitude

        in_score = float(np.dot(unit_movement, self.in_vector))
        out_score = float(np.dot(unit_movement, self.out_vector))

        if in_score > self.direction_threshold:
            return "IN"
        if out_score > self.direction_threshold:
            return "OUT"

        return None

    # -- cooldown check ------------------------------------------------------

    def check_cooldown(self, track: TrackedPerson, direction: str) -> bool:
        """Return ``True`` if the track is eligible for a new attendance event.

        A new event is allowed when:
        * The cooldown period has elapsed since the last event, **or**
        * The direction differs from the last recorded event direction (to
          allow quick IN-then-OUT or vice-versa).
        """
        if track.last_event_time == 0.0:
            return True

        # Different direction always allowed (e.g. OUT shortly after IN).
        if direction != track.last_event_direction:
            return True

        elapsed = time.time() - track.last_event_time
        return elapsed >= self.cooldown_seconds

    # -- housekeeping --------------------------------------------------------

    def _age_tracks(self, frame_number: int) -> None:
        """Increment unseen counters and prune stale tracks."""
        stale: list[int] = []
        for tid, track in self.tracks.items():
            track.frames_since_detection += 1
            if track.frames_since_detection > self._MAX_UNSEEN_FRAMES:
                stale.append(tid)
        for tid in stale:
            del self.tracks[tid]

    def get_active_tracks(self) -> list[TrackedPerson]:
        """Return all tracks that are still being actively tracked."""
        return list(self.tracks.values())

    def clear_all(self) -> None:
        """Remove every track and reset the ID counter."""
        self.tracks.clear()
        self._next_track_id = 0
        logger.info("All tracks cleared")
