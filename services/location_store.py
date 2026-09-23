"""Short-lived, authenticated BD09 fixes for the one-process web demo."""

from threading import RLock
import time


_lock = RLock()
_positions = {}


def record(user_id, position):
    if not user_id or not all(k in position for k in ("lat", "lng", "accuracy", "timestamp_ms")):
        raise ValueError("位置数据不完整")
    with _lock:
        _positions[user_id] = {"lat": position["lat"], "lng": position["lng"],
                               "accuracy": position["accuracy"],
                               "timestamp_ms": position["timestamp_ms"],
                               "coord_type": "bd09ll", "received_at": time.time()}


def read(user_id):
    with _lock:
        return dict(_positions[user_id]) if user_id in _positions else None
