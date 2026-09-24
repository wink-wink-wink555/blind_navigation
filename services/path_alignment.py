"""Near-field lateral geometry estimation from YOLO detection boxes.

This module is the perception layer of the tactile-path alignment subsystem.
It consumes axis-aligned bounding boxes from the existing detection model and
estimates where the candidate paving lies relative to the user, in the
near-field region the user is about to step onto.

It never decides what to say or do. All behavioral decisions (whether to
speak, when to speak, and what state the user is in) belong to
``services.navigation.NavigationManager``. A future segmentation-based
centerline estimator can replace :class:`PathGeometryEstimator` behind the
same ``estimate(...) -> AlignmentObservation`` contract without touching the
navigation layer.

Sign convention (used consistently across the whole project):

* ``normalized_offset > 0`` -- the paving center is to the RIGHT of the
  user's reference center, so the user should move right (``CORRECT_RIGHT``).
* ``normalized_offset < 0`` -- the paving center is to the LEFT of the
  reference center, so the user should move left (``CORRECT_LEFT``).
"""

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Tunable geometry parameters (grouped here on purpose; no magic numbers in
# the logic below). See the project README "Alignment parameters" section.
# ---------------------------------------------------------------------------

# Near-field region of interest, as fractions of the image height. Micro
# correction cares about the paving the user is about to step on, not about
# distant paving near the horizon.
NEAR_FIELD_TOP_RATIO = 0.50
NEAR_FIELD_BOTTOM_RATIO = 0.90

# Row (fraction of image height) at which the fitted path centerline is
# evaluated. It sits in the middle of the near-field ROI.
NEAR_FIELD_EVAL_RATIO = 0.70

# Detections below this confidence never participate in geometry.
GEOMETRY_MIN_CONFIDENCE = 0.35

# A candidate whose vertical span does not overlap the near-field ROI at all
# is "far only" and cannot anchor an estimate by itself.
NEAR_FIELD_MIN_OVERLAP = 0.05

# Two strong near-field candidates whose estimated centers at the evaluation
# row differ by more than this fraction of the image width are in conflict:
# report AMBIGUOUS instead of guessing.
AMBIGUOUS_SEPARATION_RATIO = 0.25

# The runner-up candidate must have at least this fraction of the best
# candidate's score before a horizontal conflict is considered ambiguous.
AMBIGUOUS_SCORE_RATIO = 0.55

# Temporal consistency: a candidate whose center jumps farther than this
# fraction of the image width from the previously selected center is
# penalized (not excluded) when other continuity cues are available.
TEMPORAL_MATCH_DISTANCE_RATIO = 0.20
TEMPORAL_MISMATCH_FACTOR = 0.6

# Score composition weights. The score rewards detections that are confident,
# close to the user's feet, and temporally stable.
WEIGHT_CONFIDENCE = 1.0
NEAR_FIELD_FLOOR = 0.35       # far boxes keep a small share of their score
BOTTOM_PROXIMITY_FLOOR = 0.5  # boxes ending high in the frame keep half

# Geometry confidence is scaled down when the near-field evidence is weak.
MAX_GEOMETRY_CONFIDENCE = 0.95


# Geometry status values. VALID is the only status the navigation layer may
# use for lateral steering; everything else means "do not guess".
STATUS_VALID = "VALID"
STATUS_AMBIGUOUS = "AMBIGUOUS"
STATUS_NO_PATH = "NO_PATH"            # no usable detection at all
STATUS_NO_NEAR_FIELD = "NO_NEAR_FIELD"  # detections exist but all are distant
STATUS_LOW_CONFIDENCE = "LOW_CONFIDENCE"

ALL_STATUSES = (STATUS_VALID, STATUS_AMBIGUOUS, STATUS_NO_PATH,
                STATUS_NO_NEAR_FIELD, STATUS_LOW_CONFIDENCE)


@dataclass
class AlignmentObservation:
    """Geometry result for a single frame. Consumed by NavigationManager."""

    status: str
    path_center_x: float | None
    reference_center_x: float
    normalized_offset: float | None
    confidence: float
    selected_detection_count: int
    candidate_count: int
    selected_box: list | None = None
    candidates: list = field(default_factory=list)

    def as_dict(self):
        return {
            "status": self.status,
            "path_center_x": self.path_center_x,
            "reference_center_x": self.reference_center_x,
            "normalized_offset": self.normalized_offset,
            "confidence": round(self.confidence, 3),
            "selected_detection_count": self.selected_detection_count,
            "candidate_count": self.candidate_count,
            "selected_box": self.selected_box,
            "candidates": self.candidates,
        }


@dataclass
class _Candidate:
    box: list
    confidence: float
    center_x: float          # full-box horizontal center (diagnostic only)
    center_y: float
    near_overlap: float      # fraction of the box height inside the ROI
    bottom_ratio: float      # box bottom as a fraction of image height
    temporal_factor: float
    score: float


class PathGeometryEstimator:
    """Estimates near-field paving center from detection bounding boxes.

    The estimator keeps one piece of temporal state: the previously selected
    near-field center, used only as a soft consistency cue when scoring
    candidates. Call :meth:`reset` when the camera restarts.
    """

    def __init__(self, reference_center_x=None):
        # None means "image width / 2", resolved per frame so resolution
        # changes do not break anything. A future camera-mount calibration
        # flow can inject a measured reference center here.
        self.reference_center_x = reference_center_x
        self._last_center_x = None

    def reset(self):
        self._last_center_x = None

    # ------------------------------------------------------------------
    def estimate(self, image_width, image_height, detections):
        """Return an :class:`AlignmentObservation` for one frame.

        ``detections`` is a list of ``{"confidence": float, "box": [x1, y1,
        x2, y2]}`` in pixel coordinates.
        """
        width, height = float(image_width), float(image_height)
        if width <= 0 or height <= 0:
            raise ValueError("图像尺寸无效")
        x_ref = (float(self.reference_center_x) if self.reference_center_x is not None
                 else width / 2.0)
        detections = [d for d in (detections or []) if self._sane_box(d)]
        if not detections:
            return self._finish(AlignmentObservation(
                STATUS_NO_PATH, None, x_ref, None, 0.0, 0, 0))

        roi_top = NEAR_FIELD_TOP_RATIO * height
        roi_bottom = NEAR_FIELD_BOTTOM_RATIO * height
        eval_y = NEAR_FIELD_EVAL_RATIO * height

        candidates = [self._score(d, width, height, roi_top, roi_bottom)
                      for d in detections]
        usable = [c for c in candidates if c.confidence >= GEOMETRY_MIN_CONFIDENCE]
        if not usable:
            return self._finish(AlignmentObservation(
                STATUS_LOW_CONFIDENCE, None, x_ref, None, 0.0, 0,
                len(candidates), candidates=self._debug(candidates)))
        near = [c for c in usable if c.near_overlap >= NEAR_FIELD_MIN_OVERLAP]
        if not near:
            # Detections exist but all of them are far from the user's feet:
            # never derive steering from distant pavement alone.
            return self._finish(AlignmentObservation(
                STATUS_NO_NEAR_FIELD, None, x_ref, None, 0.0, 0,
                len(candidates), candidates=self._debug(candidates)))

        near.sort(key=lambda c: c.score, reverse=True)
        best = near[0]
        if len(near) > 1:
            # Conflict check compares each candidate's own near-field center
            # (axis-aligned boxes: the horizontal center), not the fitted
            # centerline, which would be identical for every candidate.
            runner_up = near[1]
            separation = abs(runner_up.center_x - best.center_x) / width
            if (separation > AMBIGUOUS_SEPARATION_RATIO and
                    runner_up.score >= AMBIGUOUS_SCORE_RATIO * best.score):
                return self._finish(AlignmentObservation(
                    STATUS_AMBIGUOUS, None, x_ref, None, 0.0, 0,
                    len(candidates), candidates=self._debug(candidates)))

        path_center_x = self._eval_x(best, near, eval_y)
        offset = (path_center_x - x_ref) / width
        confidence = self._geometry_confidence(best, near)
        self._last_center_x = path_center_x
        return AlignmentObservation(
            STATUS_VALID, round(path_center_x, 1), x_ref,
            round(offset, 4), confidence, 1, len(candidates),
            selected_box=[round(v, 1) for v in best.box],
            candidates=self._debug(candidates))

    # ------------------------------------------------------------------
    @staticmethod
    def _sane_box(detection):
        try:
            x1, y1, x2, y2 = (float(v) for v in detection["box"])
            conf = float(detection["confidence"])
        except (KeyError, TypeError, ValueError):
            return False
        return x2 > x1 and y2 > y1 and 0.0 <= conf <= 1.0

    def _score(self, detection, width, height, roi_top, roi_bottom):
        x1, y1, x2, y2 = (float(v) for v in detection["box"])
        conf = float(detection["confidence"])
        box_height = y2 - y1
        overlap = max(0.0, min(y2, roi_bottom) - max(y1, roi_top)) / box_height
        bottom_ratio = min(1.0, max(0.0, y2 / height))
        near_weight = NEAR_FIELD_FLOOR + (1.0 - NEAR_FIELD_FLOOR) * overlap
        bottom_weight = BOTTOM_PROXIMITY_FLOOR + (1.0 - BOTTOM_PROXIMITY_FLOOR) * bottom_ratio
        center_x = (x1 + x2) / 2.0
        if self._last_center_x is None:
            temporal = 1.0
        else:
            jump = abs(center_x - self._last_center_x) / width
            temporal = 1.0 if jump <= TEMPORAL_MATCH_DISTANCE_RATIO else TEMPORAL_MISMATCH_FACTOR
        score = WEIGHT_CONFIDENCE * conf * near_weight * bottom_weight * temporal
        return _Candidate(box=[x1, y1, x2, y2], confidence=conf,
                          center_x=center_x, center_y=(y1 + y2) / 2.0,
                          near_overlap=overlap, bottom_ratio=bottom_ratio,
                          temporal_factor=temporal, score=score)

    @staticmethod
    def _eval_x(best, near, eval_y):
        """Path center x at the near-field evaluation row.

        With a single usable candidate the box is axis aligned, so its
        near-field center is its own horizontal center. With several
        near-field candidates belonging to the same paving strip, fit a
        weighted centerline x = a*y + b through their centers and evaluate it
        at the near-field row. This keeps distant box shape from dragging the
        estimate, which a plain full-box center cannot do.
        """
        if len(near) < 2:
            return best.center_x
        total_w = sum(c.score for c in near)
        if total_w <= 0:
            return best.center_x
        mean_x = sum(c.score * c.center_x for c in near) / total_w
        mean_y = sum(c.score * c.center_y for c in near) / total_w
        var_y = sum(c.score * (c.center_y - mean_y) ** 2 for c in near) / total_w
        if var_y < 1.0:  # candidates stacked at the same height carry no slope
            return mean_x
        cov = sum(c.score * (c.center_x - mean_x) * (c.center_y - mean_y)
                  for c in near) / total_w
        slope = cov / var_y
        slope = max(-3.0, min(3.0, slope))  # reject implausible centerlines
        return mean_x + slope * (eval_y - mean_y)

    @staticmethod
    def _geometry_confidence(best, near):
        """Confidence in the *geometry*, not just in YOLO.

        Strong near-field overlap and temporal continuity raise it; several
        competing near-field candidates lower it.
        """
        conf = best.confidence * (0.5 + 0.5 * min(1.0, best.near_overlap * 1.5))
        conf *= 0.7 + 0.3 * best.temporal_factor
        if len(near) > 1:
            spread = max(c.center_x for c in near) - min(c.center_x for c in near)
            width_scale = max(c.box[2] for c in near)  # rough strip width cue
            if width_scale > 0:
                conf *= max(0.5, 1.0 - 0.5 * spread / (3 * width_scale))
        return max(0.0, min(MAX_GEOMETRY_CONFIDENCE, conf))

    def _finish(self, observation):
        # An inconclusive frame must not anchor temporal consistency.
        if observation.status != STATUS_VALID:
            self._last_center_x = None
        return observation

    @staticmethod
    def _debug(candidates):
        return [{"box": [round(v, 1) for v in c.box],
                 "confidence": round(c.confidence, 3),
                 "score": round(c.score, 3),
                 "near_overlap": round(c.near_overlap, 3),
                 "bottom_ratio": round(c.bottom_ratio, 3),
                 "temporal_factor": c.temporal_factor}
                for c in candidates]
