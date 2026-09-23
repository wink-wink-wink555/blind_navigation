"""Per-user, bounded event log for the single-process web demonstration.

The browser owns audio playback. Publishing an event never means it was heard.
"""

from collections import OrderedDict, defaultdict, deque
from threading import Condition, RLock
import time
import uuid


PRIORITIES = {"SAFETY": 0, "ROUTE": 1, "FAMILY": 2, "ASSISTANT": 3, "BACKGROUND": 4}


class GuidanceBus:
    def __init__(self, capacity=256):
        self.capacity = capacity
        self._condition = Condition(RLock())
        self._events = defaultdict(lambda: deque(maxlen=capacity))
        self._sequence = defaultdict(int)
        self._receipts = OrderedDict()

    def publish(self, user_id, kind, text="", *, priority="BACKGROUND", ttl_ms=10000,
                session_id=None, route_revision=None, step_id=None, dedupe_key=None,
                resume_policy="discard", sender_id=None, nav_state=None, context_epoch=None):
        if priority not in PRIORITIES or resume_policy not in ("discard", "restart", "continue"):
            raise ValueError("无效的语音事件策略")
        if kind == "speech" and (not text or len(text) > 400):
            raise ValueError("语音内容必须为1至400字")
        if ttl_ms <= 0 or ttl_ms > 300000:
            raise ValueError("事件有效期超出范围")
        with self._condition:
            self._sequence[user_id] += 1
            event = {
                "id": self._sequence[user_id], "event_id": str(uuid.uuid4()),
                "kind": kind, "text": text, "priority": PRIORITIES[priority],
                "source": priority, "created_at_ms": int(time.time() * 1000),
                "ttl_ms": ttl_ms, "session_id": session_id,
                "route_revision": route_revision, "step_id": step_id,
                "dedupe_key": dedupe_key, "resume_policy": resume_policy,
                "nav_state": nav_state, "context_epoch": context_epoch,
            }
            self._events[user_id].append(event)
            self._receipts[event["event_id"]] = {
                "target_user_id": user_id, "sender_user_id": sender_id,
                "status": "QUEUED", "expires_at_ms": event["created_at_ms"] + ttl_ms,
            }
            if len(self._receipts) > 2048:
                self._receipts.popitem(last=False)
            self._condition.notify_all()
            return dict(event)

    def acknowledge(self, user_id, event_id, status):
        if status not in ("PLAYING", "PAUSED", "FINISHED", "FAILED", "CANCELLED"):
            raise ValueError("无效的播放状态")
        with self._condition:
            receipt = self._receipts.get(event_id)
            if not receipt or receipt["target_user_id"] != user_id:
                raise ValueError("事件不存在或无权确认")
            if receipt["status"] in ("FINISHED", "FAILED", "CANCELLED"):
                return receipt["status"]
            receipt["status"] = status
            return status

    def status(self, user_id, event_id):
        with self._condition:
            receipt = self._receipts.get(event_id)
            if not receipt or user_id not in (receipt["target_user_id"], receipt["sender_user_id"]):
                return None
            if receipt["status"] in ("QUEUED", "PLAYING", "PAUSED") and int(time.time() * 1000) > receipt["expires_at_ms"]:
                return "EXPIRED"
            return receipt["status"]

    def events_since(self, user_id, after=0, timeout=0):
        with self._condition:
            if after > self._sequence[user_id]:
                after = 0  # A browser reconnected after the one-process log restarted.
            if self._sequence[user_id] <= after and timeout:
                self._condition.wait_for(lambda: self._sequence[user_id] > after, timeout)
            now_ms = int(time.time() * 1000)
            return [dict(e) for e in self._events[user_id]
                    if e["id"] > after and now_ms < e["created_at_ms"] + e["ttl_ms"]
                    and self._receipts.get(e["event_id"], {}).get("status") not in
                    ("FINISHED", "FAILED", "CANCELLED")]

    def latest_id(self, user_id):
        with self._condition:
            return self._sequence[user_id]


guidance_bus = GuidanceBus()
