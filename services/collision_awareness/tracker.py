import time
import numpy as np
from collections import deque
from typing import Dict, List, Optional, Tuple

class Track:
    _id_counter = 0

    def __init__(self, box, label, timestamp):
        Track._id_counter += 1
        self.track_id = Track._id_counter
        self.label = label
        self.age = 0
        self.history = deque(maxlen=10)
        self.history.append((box, timestamp))

    def predict(self):
        self.age += 1

    def update(self, box, timestamp):
        self.age = 0
        self.history.append((box, timestamp))

    @property
    def is_stale(self) -> bool:
        return self.age > 5  # Evict after 5 frames of no detection

class LightweightTracker:
    def __init__(self, iou_threshold=0.3):
        self._tracks: Dict[int, Track] = {}
        self.iou_threshold = iou_threshold

    def update(self, detections: List[dict]) -> List[dict]:
        """
        Expects detections as list of dicts: [{'box': (x1, y1, x2, y2), 'label': 'person'}]
        Updates tracks and adds 'track_id' to each detection.
        """
        timestamp = time.time()
        
        # 1. Predict (age increment)
        for t in self._tracks.values():
            t.predict()

        # 2. Associate
        active_tracks = list(self._tracks.values())
        if not detections:
            self._evict()
            return []

        if not active_tracks:
            matched, unmatched_d = [], list(range(len(detections)))
        else:
            matched, unmatched_d, _ = self._associate(detections, active_tracks)

        # 3. Update matched tracks
        for d_idx, t_idx in matched:
            active_tracks[t_idx].update(detections[d_idx]['box'], timestamp)
            detections[d_idx]['track_id'] = active_tracks[t_idx].track_id

        # 4. Create new tracks for unmatched detections
        for d_idx in unmatched_d:
            t = Track(detections[d_idx]['box'], detections[d_idx]['label'], timestamp)
            self._tracks[t.track_id] = t
            detections[d_idx]['track_id'] = t.track_id

        self._evict()
        return detections

    def _associate(self, detections, tracks):
        n, m = len(detections), len(tracks)
        iou_mat = np.zeros((n, m), dtype=np.float32)
        for i, det in enumerate(detections):
            for j, trk in enumerate(tracks):
                if trk.history:
                    iou_mat[i, j] = self._iou(det['box'], trk.history[-1][0])

        matched, unmatched_d, unmatched_t = [], list(range(n)), list(range(m))
        while iou_mat.size and np.any(iou_mat > -1):
            idx = np.argmax(iou_mat)
            i, j = divmod(int(idx), m)
            if iou_mat[i, j] < self.iou_threshold:
                break
            matched.append((i, j))
            iou_mat[i, :] = -1
            iou_mat[:, j] = -1
            if i in unmatched_d: unmatched_d.remove(i)
            if j in unmatched_t: unmatched_t.remove(j)
        return matched, unmatched_d, unmatched_t

    def _iou(self, a, b) -> float:
        ax1, ay1, ax2, ay2 = a
        bx1, by1, bx2, by2 = b
        ix1, iy1 = max(ax1, bx1), max(ay1, by1)
        ix2, iy2 = min(ax2, bx2), min(ay2, by2)
        inter = max(0, ix2 - ix1) * max(0, iy2 - ay1)
        if inter == 0: return 0.0
        ua = (ax2 - ax1) * (ay2 - ay1)
        ub = (bx2 - bx1) * (by2 - by1)
        union = ua + ub - inter
        return inter / union if union > 0 else 0.0

    def _evict(self):
        stale_ids = [tid for tid, t in self._tracks.items() if t.is_stale]
        for tid in stale_ids:
            del self._tracks[tid]

    @property
    def tracks(self):
        return self._tracks
