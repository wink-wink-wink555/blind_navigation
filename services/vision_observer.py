"""Tactile paving observation: presence plus near-field lateral geometry.

The existing YOLO weights detect paving objects, not connected junction arms.
On top of presence, each frame is passed through PathGeometryEstimator so the
navigation layer receives a structured alignment observation (status,
normalized lateral offset, confidence) instead of a bare boolean. The
observer still never infers safe turns and never decides what to say.
"""

from threading import Lock
import time

from services.path_alignment import PathGeometryEstimator

# Detections whose bottom edge stays in the top third of the frame are too
# far away to count as "paving under observation" for presence purposes.
PRESENCE_MIN_BOTTOM_FRACTION = 1 / 3


class VisionObserver:
    def __init__(self, geometry_estimator=None):
        self._model = None
        self._lock = Lock()
        # Pluggable: a future segmentation centerline estimator can replace
        # this behind the same estimate(...) contract.
        self._geometry = geometry_estimator or PathGeometryEstimator()

    def analyze(self, image_bytes, frame_seq=None, captured_at_ms=None):
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("视觉识别依赖未安装") from exc
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("无法读取图像帧")
        return self.analyze_frame(image, frame_seq=frame_seq, captured_at_ms=captured_at_ms)

    def analyze_frame(self, image, frame_seq=None, captured_at_ms=None):
        try:
            from ultralytics import YOLO
            from config import MODEL_WEIGHTS
        except ImportError as exc:
            raise RuntimeError("视觉识别依赖未安装") from exc
        with self._lock:
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
                    observations.append({"confidence": round(confidence, 3), "box": [x1, y1, x2, y2]})
        geometry = self._geometry.estimate(width, height, observations)
        return {
            "visible": bool(observations), "detections": len(observations),
            "max_confidence": max((d["confidence"] for d in observations), default=0),
            "boxes": observations,
            "branch_status": "UNKNOWN",  # Object boxes cannot establish path connectivity.
            "geometry": geometry.as_dict(),
            "frame_seq": frame_seq,
            "captured_at_ms": captured_at_ms,
            "processed_at_ms": int(time.time() * 1000),
        }


vision_observer = VisionObserver()
