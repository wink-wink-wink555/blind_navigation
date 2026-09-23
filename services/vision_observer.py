"""Tactile paving visibility observation, without inferring safe turns.

The existing YOLO weights detect paving objects, not connected junction arms.
"""

from threading import Lock


class VisionObserver:
    def __init__(self):
        self._model = None
        self._lock = Lock()

    def analyze(self, image_bytes):
        try:
            import cv2
            import numpy as np
        except ImportError as exc:
            raise RuntimeError("视觉识别依赖未安装") from exc
        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("无法读取图像帧")
        return self.analyze_frame(image)

    def analyze_frame(self, image):
        try:
            from ultralytics import YOLO
            from config import MODEL_WEIGHTS
        except ImportError as exc:
            raise RuntimeError("视觉识别依赖未安装") from exc
        with self._lock:
            if self._model is None:
                self._model = YOLO(MODEL_WEIGHTS)
            results = self._model.predict(image, conf=0.45, verbose=False)
        height = image.shape[0]
        observations = []
        for result in results:
            for box in result.boxes:
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = (float(n) for n in box.xyxy[0])
                if y2 >= height / 3:
                    observations.append({"confidence": round(confidence, 3), "box": [x1, y1, x2, y2]})
        return {
            "visible": bool(observations), "detections": len(observations),
            "max_confidence": max((d["confidence"] for d in observations), default=0),
            "boxes": observations,
            "branch_status": "UNKNOWN",  # Object boxes cannot establish path connectivity.
        }


vision_observer = VisionObserver()
