"""PiFace Preprocessing - CLAHE, blur detection, enrollment quality gates."""

import logging
from dataclasses import dataclass, field

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Image enhancement
# ---------------------------------------------------------------------------


def apply_clahe(
    frame: np.ndarray,
    clip_limit: float = 2.0,
    grid_size: tuple[int, int] = (8, 8),
) -> np.ndarray:
    """Apply Contrast Limited Adaptive Histogram Equalisation (CLAHE).

    Converts the input BGR image to the LAB colour space, equalises the L
    channel, and converts back to BGR.

    Args:
        frame: Input image in BGR format.
        clip_limit: CLAHE contrast clipping limit.
        grid_size: Size of the grid for histogram equalisation.

    Returns:
        Enhanced BGR image.
    """
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
    l_enhanced = clahe.apply(l_channel)

    lab_enhanced = cv2.merge([l_enhanced, a_channel, b_channel])
    return cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)


# ---------------------------------------------------------------------------
# Blur detection
# ---------------------------------------------------------------------------


def detect_blur(frame: np.ndarray) -> float:
    """Compute a sharpness score using the variance of the Laplacian.

    Args:
        frame: Input image (BGR or grayscale).

    Returns:
        Laplacian variance -- higher values indicate a sharper image.
    """
    if len(frame.shape) == 3:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    else:
        gray = frame
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


# ---------------------------------------------------------------------------
# Enrollment quality
# ---------------------------------------------------------------------------

# Minimum thresholds for enrollment validation.
_MIN_BLUR_SCORE: float = 100.0
_MIN_FACE_SIZE: int = 112  # pixels (width and height)
_MIN_DETECTION_CONFIDENCE: float = 0.5
_MAX_GOOD_FRAMES: int = 10


@dataclass
class EnrollmentQuality:
    """Result of an enrollment quality check."""

    is_valid: bool
    score: float
    issues: list[str] = field(default_factory=list)


def validate_enrollment_photo(
    frame: np.ndarray,
    faces: list,
) -> EnrollmentQuality:
    """Validate a single photo for enrollment quality.

    Checks:
      - Blur score >= 100 (Laplacian variance).
      - Exactly one face detected.
      - Face bounding box >= 112x112 pixels.
      - Detection confidence >= 0.5.

    Args:
        frame: BGR image to validate.
        faces: List of detected faces.  Each face is expected to expose
            ``bbox`` (sequence of ``[x1, y1, x2, y2]``) and ``det_score``
            (float) attributes, matching the InsightFace convention.

    Returns:
        An ``EnrollmentQuality`` report.
    """
    issues: list[str] = []
    score: float = 0.0

    # --- blur check ---
    blur_score = detect_blur(frame)
    if blur_score < _MIN_BLUR_SCORE:
        issues.append(
            f"Image too blurry (score {blur_score:.1f}, need >= {_MIN_BLUR_SCORE})"
        )
    score += min(blur_score / _MIN_BLUR_SCORE, 1.0) * 0.4  # 40 % weight

    # --- face count ---
    if len(faces) == 0:
        issues.append("No face detected")
    elif len(faces) > 1:
        issues.append(f"Multiple faces detected ({len(faces)}), need exactly 1")

    if len(faces) == 1:
        score += 0.2  # 20 % weight for single face
        face = faces[0]

        # --- face size ---
        bbox = face.bbox  # [x1, y1, x2, y2]
        face_w = int(bbox[2] - bbox[0])
        face_h = int(bbox[3] - bbox[1])
        if face_w < _MIN_FACE_SIZE or face_h < _MIN_FACE_SIZE:
            issues.append(
                f"Face too small ({face_w}x{face_h}px, need >= "
                f"{_MIN_FACE_SIZE}x{_MIN_FACE_SIZE}px)"
            )
        else:
            score += 0.2  # 20 % weight

        # --- detection confidence ---
        confidence = float(face.det_score)
        if confidence < _MIN_DETECTION_CONFIDENCE:
            issues.append(
                f"Low detection confidence ({confidence:.2f}, need >= "
                f"{_MIN_DETECTION_CONFIDENCE})"
            )
        else:
            score += 0.2 * min(confidence, 1.0)  # 20 % weight

    is_valid = len(issues) == 0
    return EnrollmentQuality(is_valid=is_valid, score=round(score, 3), issues=issues)


def validate_enrollment_video(
    frames: list[np.ndarray],
    min_good_frames: int = 5,
) -> tuple[list[np.ndarray], EnrollmentQuality]:
    """Validate a sequence of frames captured during video enrollment.

    Each frame is individually scored for blur, and only frames that pass
    basic quality gates are retained.  The best frames (sorted by sharpness)
    are returned.

    Args:
        frames: List of BGR images.
        min_good_frames: Minimum number of frames that must pass quality
            checks for the enrollment to be considered valid.

    Returns:
        A tuple ``(good_frames, quality_report)``.  ``good_frames`` contains
        up to 10 of the best frames sorted by descending sharpness.
    """
    scored: list[tuple[float, np.ndarray]] = []
    total_issues: list[str] = []

    for idx, frame in enumerate(frames):
        blur_score = detect_blur(frame)
        if blur_score < _MIN_BLUR_SCORE:
            total_issues.append(f"Frame {idx}: blurry ({blur_score:.1f})")
            continue
        scored.append((blur_score, frame))

    # Sort by blur score descending (sharpest first).
    scored.sort(key=lambda t: t[0], reverse=True)
    good_frames = [frame for _, frame in scored[:_MAX_GOOD_FRAMES]]

    is_valid = len(good_frames) >= min_good_frames
    if not is_valid:
        total_issues.insert(
            0,
            f"Only {len(good_frames)} good frame(s), need >= {min_good_frames}",
        )

    avg_score = (
        sum(s for s, _ in scored[:_MAX_GOOD_FRAMES]) / len(good_frames)
        if good_frames
        else 0.0
    )

    quality = EnrollmentQuality(
        is_valid=is_valid,
        score=round(avg_score, 3),
        issues=total_issues,
    )
    return good_frames, quality


# ---------------------------------------------------------------------------
# Embedding utilities
# ---------------------------------------------------------------------------


def compute_cosine_similarity(
    embedding1: np.ndarray,
    embedding2: np.ndarray,
) -> float:
    """Cosine similarity between two 1-D embedding vectors.

    Args:
        embedding1: First embedding (1-D array).
        embedding2: Second embedding (1-D array).

    Returns:
        Cosine similarity in ``[-1, 1]``.
    """
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(np.dot(embedding1, embedding2) / (norm1 * norm2))


def batch_cosine_similarity(
    query: np.ndarray,
    matrix: np.ndarray,
) -> np.ndarray:
    """Vectorised cosine similarity of *query* against every row in *matrix*.

    Args:
        query: 1-D embedding vector.
        matrix: 2-D array where each row is an embedding.

    Returns:
        1-D array of cosine similarities, one per row in *matrix*.
    """
    query_norm = np.linalg.norm(query)
    if query_norm == 0.0:
        return np.zeros(matrix.shape[0], dtype=np.float64)

    row_norms = np.linalg.norm(matrix, axis=1)
    # Avoid division by zero for any zero-norm rows.
    row_norms = np.where(row_norms == 0.0, 1.0, row_norms)

    similarities = matrix @ query / (row_norms * query_norm)
    return similarities


def check_embedding_consistency(
    embeddings: list[np.ndarray],
    min_similarity: float = 0.7,
) -> tuple[bool, float]:
    """Check that a set of embeddings are mutually consistent.

    Computes the average pairwise cosine similarity and checks it against
    *min_similarity*.

    Args:
        embeddings: List of 1-D embedding vectors (at least 2).
        min_similarity: Minimum average similarity to be considered
            consistent.

    Returns:
        ``(is_consistent, avg_similarity)``
    """
    n = len(embeddings)
    if n < 2:
        logger.warning("Need at least 2 embeddings to check consistency")
        return True, 1.0

    total_sim = 0.0
    pair_count = 0
    for i in range(n):
        for j in range(i + 1, n):
            total_sim += compute_cosine_similarity(embeddings[i], embeddings[j])
            pair_count += 1

    avg_similarity = total_sim / pair_count
    is_consistent = avg_similarity >= min_similarity

    logger.debug(
        "Embedding consistency: avg_sim=%.4f, threshold=%.2f, consistent=%s",
        avg_similarity,
        min_similarity,
        is_consistent,
    )
    return is_consistent, round(avg_similarity, 4)
