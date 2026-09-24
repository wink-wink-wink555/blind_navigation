"""Tactile paving observation: presence plus near-field lateral geometry.

The existing YOLO weights detect paving objects, not connected junction arms.
On top of presence, each frame is passed through PathGeometryEstimator so the
navigation layer receives a structured alignment observation (status,
normalized lateral offset, confidence) instead of a bare boolean. The
observer still never infers safe turns and never decides what to say.

Geometry tracking is explicitly stream-scoped. Live users, recorded-video
readers, and unrelated callers must never share PathGeometryEstimator temporal
state, because its previous-center cue is meaningful only within one coherent
camera stream.
"""

from threading import Lock, RLock
import time

from services.path_alignment import PathGeometryEstimator

# Detections whose bottom edge stays in the top third of the frame are too
# far away to count as "paving under observation" for presence purposes.
PRESENCE_MIN_BOTTOM_FRACTION = 1 / 3


class VisionObserver:
    def __init__(self, geometry_estimator=None, geometry_factory=None):
        self._model = None
        self._model_lock = Lock()

        # A caller may inject one estimator for a focused unit test. Normal
        # runtime callers instead identify their stream and receive a private
        # estimator created by the factory below.
        self._fallback_geometry = geometry_estimator
        self._geometry_factory = geometry_factory or PathGeometryEstimator
        self._geometry_lock = RLock()
        self._geometry_streams = {}

    def reset_geometry_stream(self, geometry_stream_id):
        """Forget temporal geometry state for one camera/video stream.

        Live navigation calls this on start/replan/stop/camera loss. Recorded
        video playback uses its own temporary stream id and resets it when the
        reader exits. This prevents one user or one video from influencing the
        candidate scoring of another stream.
        """
        with self._geometry_lock:
            if geometry_stream_id is None:
                estimator = self._fallback_geometry
            else:
                estimator = self._geometry_streams.pop(geometry_stream_id, None)
            if estimator is not None and hasattr(estimator, "reset"):
                estimator.reset()

    def _estimate_geometry(self, width, height, observations, geometry_stream_id):
        # Calls without a stream id are deliberately stateless by default.
        # This makes accidental one-shot/history callers incapable of
        # polluting any live track. Tests may still inject a fallback estimator.
        if geometry_stream_id is None:
            estimator = self._fallback_geometry or self._geometry_factory()
            return estimator.estimate(width, height, observations)

        # The estimator keeps a previous-center cue, so estimate and reset for
        # the same stream must be serialized. Geometry work is tiny compared
        # with YOLO inference, so a small shared lock keeps the contract simple.
        with self._geometry_lock:
            estimator = self._geometry_streams.get(geometry_stream_id)
            if estimator is None:
                estimator = self._geometry_factory()
                self._geometry_streams[geometry_stream_id] = estimator
            return estimator.estimate(width, height, observations)

    def analyze(self, image_bytes, frame_seq=None, captured_at_ms=None,
                geometry_stream_id=None, server_received_at_ms=None):
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("视觉识别依赖未安装") from exc
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("无法读取图像帧")
        return self.analyze_frame(
            image,
            frame_seq=frame_seq,
            captured_at_ms=captured_at_ms,
            geometry_stream_id=geometry_stream_id,
            server_received_at_ms=server_received_at_ms,
        )

    def analyze_frame(self, image, frame_seq=None, captured_at_ms=None,
                      geometry_stream_id=None, server_received_at_ms=None):
        try:
            from ultralytics import YOLO
            from config import MODEL_WEIGHTS
        except ImportError as exc:
            raise RuntimeError("视觉识别依赖未安装") from exc
        with self._model_lock:
            if self._model is None:
                self._model = YOLO(MODEL_WEIGHTS)
            results = self._model.predict(image, conf=0.45, verbose=False)
        height, width = image.shape[0], image.shape[1]
        observations = []
        for result in results:
            for box in result.boxes:
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = (float(n) for n in box.xyxy[0])
                if y2 >= height * PRESENCE_MIN_BOTTOM_FRACTION:
                    observations.append({
                        "confidence": round(confidence, 3),
                        "box": [x1, y1, x2, y2],
                    })
        geometry = self._estimate_geometry(
            width, height, observations, geometry_stream_id
        )
        return {
            "visible": bool(observations),
            "detections": len(observations),
            "max_confidence": max((d["confidence"] for d in observations), default=0),
            "boxes": observations,
            "branch_status": "UNKNOWN",  # Object boxes cannot establish path connectivity.
            "geometry": geometry.as_dict(),
            "frame_seq": frame_seq,
            # Browser wall-clock metadata is retained for diagnostics only.
            "captured_at_ms": captured_at_ms,
            # Freshness decisions use server timestamps so client/server clock
            # skew cannot accidentally suppress every steering observation.
            "server_received_at_ms": server_received_at_ms,
            "processed_at_ms": int(time.time() * 1000),
        }


vision_observer = VisionObserver()
