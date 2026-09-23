"""Conservative navigation state for the browser demonstration.

Map steps are intentions. Detection boxes cannot certify an accessible branch,
so this module never issues an unconditional instruction to turn.
"""

from copy import deepcopy
from math import asin, cos, radians, sin, sqrt
from threading import RLock
import time
import uuid

from services.baidu_navigation import require_bd09, validate_point


def meters(a, b):
    lat1, lon1 = radians(a["lat"]), radians(a["lng"])
    lat2, lon2 = radians(b["lat"]), radians(b["lng"])
    x = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 12742000 * asin(min(1, sqrt(x)))


def _segment_distance(position, a, b):
    # Local meter coordinates are sufficient for a single pedestrian segment.
    scale = cos(radians(position["lat"]))
    ax, ay = (a["lng"] - position["lng"]) * 111320 * scale, (a["lat"] - position["lat"]) * 111320
    bx, by = (b["lng"] - position["lng"]) * 111320 * scale, (b["lat"] - position["lat"]) * 111320
    length2 = (bx - ax) ** 2 + (by - ay) ** 2
    t = max(0, min(1, -(ax * (bx - ax) + ay * (by - ay)) / length2)) if length2 else 0
    return sqrt((ax + t * (bx - ax)) ** 2 + (ay + t * (by - ay)) ** 2)


def distance_to_step(position, step):
    points = [step["start"]]
    for pair in (step.get("path") or "").split(";"):
        try:
            lng, lat = pair.split(",")[:2]
            lat, lng = validate_point(lat, lng)
            points.append({"lat": lat, "lng": lng})
        except (ValueError, TypeError):
            continue
    points.append(step["end"])
    return min(_segment_distance(position, a, b) for a, b in zip(points, points[1:]))


def planned_turn(step):
    turn = step.get("turn_type_id")
    try:
        turn = int(turn)
    except (ValueError, TypeError):
        turn = None
    if turn in (2, 3, 4, 15, 23, 27, 29, 31):
        return "右"
    if turn in (5, 6, 7, 17, 21, 26, 28, 30):
        return "左"
    instruction = step.get("instruction", "")
    if "右转" in instruction:
        return "右"
    if "左转" in instruction:
        return "左"
    return None


def requires_road_crossing(step):
    """Road crossings need abilities this paving detector cannot establish."""
    return str(step.get("turn_type_id")) in ("26", "27") or any(
        term in step.get("instruction", "") for term in ("过马路", "人行横道", "斑马线", "横过道路", "穿越道路"))


class NavigationManager:
    def __init__(self, provider, bus):
        self.provider = provider
        self.bus = bus
        self._lock = RLock()
        self._sessions = {}
        self._generation = {}

    def snapshot(self, user_id):
        with self._lock:
            return deepcopy(self._sessions.get(user_id))

    @staticmethod
    def validate_location(location):
        if not isinstance(location, dict):
            raise ValueError("缺少当前位置")
        lat, lng = validate_point(location.get("lat"), location.get("lng"))
        try:
            accuracy = float(location.get("accuracy", 9999))
            timestamp_ms = int(location.get("timestamp_ms", 0))
        except (TypeError, ValueError) as exc:
            raise ValueError("位置缺少有效的精度或时间") from exc
        now_ms = int(time.time() * 1000)
        if not (0 < accuracy <= 1000) or not (now_ms - 15000 <= timestamp_ms <= now_ms + 5000):
            raise ValueError("位置过期或精度无效，请重新定位")
        coord_type = location.get("coord_type", "wgs84")
        if coord_type != "wgs84":
            raise ValueError("实时定位必须明确标记为 WGS84")
        return {"lat": lat, "lng": lng, "accuracy": accuracy, "timestamp_ms": timestamp_ms}

    def _convert(self, location):
        checked = self.validate_location(location)
        bd_point = self.provider.to_bd09(checked["lat"], checked["lng"], "wgs84")
        return {**bd_point, "accuracy": checked["accuracy"], "timestamp_ms": checked["timestamp_ms"]}

    def start(self, user_id, destination, location):
        destination = require_bd09(destination)
        with self._lock:
            request_version = self._generation.get(user_id, 0) + 1
            self._generation[user_id] = request_version
            # A newly requested route invalidates old turn audio immediately.
            self._sessions.pop(user_id, None)
        self._context(user_id)
        current = self._convert(location)
        if current["accuracy"] > 25:
            raise ValueError("当前位置误差过大，请在开阔处重新定位后开始导航")
        route = self.provider.plan(current, destination)
        with self._lock:
            if self._generation[user_id] != request_version:
                raise ValueError("路线请求已被新的导航操作取代")
            session = {
                "session_id": str(uuid.uuid4()), "route_revision": request_version,
                "state": "PLANNED", "route": route, "step_index": 0,
                "last_position": current, "vision_status": "UNKNOWN", "vision_at_ms": 0,
                "missing_frames": 0, "endpoint_hits": 0, "deviation_hits": 0,
                "recovery_hits": 0, "last_warning_ms": 0, "last_advisory_ms": 0,
                "uncertain_reason": None, "visible_frames": 0, "context_epoch": 0,
            }
            self._sessions[user_id] = session
            result = deepcopy(session)
        self._context(user_id, result)
        self.bus.publish(user_id, "speech", "步行路线已规划。请确认目的地后开始导航。",
                         priority="BACKGROUND", ttl_ms=12000,
                         session_id=result["session_id"], route_revision=result["route_revision"],
                         dedupe_key="route_start")
        return result

    def activate(self, user_id):
        with self._lock:
            session = self._sessions.get(user_id)
            if not session:
                raise ValueError("请先规划步行路线")
            if session["state"] != "PLANNED":
                raise ValueError("导航已开始或需要重新规划")
            if int(time.time() * 1000) - session["last_position"]["timestamp_ms"] > 15000:
                raise ValueError("起点定位已过期，请重新规划路线")
            if meters(session["last_position"], session["route"]["origin"]) > max(20, 2 * session["last_position"]["accuracy"]):
                raise ValueError("当前位置已离开路线起点，请重新规划")
            first_step = session["route"]["steps"][0]
            session["state"] = "UNCERTAIN" if requires_road_crossing(first_step) else "NAVIGATING"
            session["uncertain_reason"] = "CROSSING" if session["state"] == "UNCERTAIN" else None
            session["context_epoch"] += 1
            result = deepcopy(session)
        self._context(user_id, result)
        self.bus.publish(user_id, "speech", ("路线起点需要过街，请停下并通过可靠的行人设施确认后再继续。"
                         if result["state"] == "UNCERTAIN" else
                         "导航已开始。地图提供路线参考，路口请以实际环境确认为准。"),
                         priority="SAFETY" if result["state"] == "UNCERTAIN" else "ROUTE",
                         ttl_ms=12000, session_id=result["session_id"],
                         route_revision=result["route_revision"], dedupe_key="navigation_active")
        return result

    def context(self, user_id):
        with self._lock:
            session = self._sessions.get(user_id)
            return {"session_id": session["session_id"] if session else None,
                    "route_revision": self._generation.get(user_id, 0),
                    "step_id": session["step_index"] if session else None,
                    "nav_state": session["state"] if session else None,
                    "context_epoch": session["context_epoch"] if session else 0}

    def _context(self, user_id, session=None):
        context = ({"session_id": session["session_id"], "route_revision": session["route_revision"],
                    "step_id": session["step_index"], "nav_state": session["state"],
                    "context_epoch": session["context_epoch"]} if session else self.context(user_id))
        self.bus.publish(user_id, "context", priority="SAFETY", ttl_ms=300000,
                         **context)

    def stop(self, user_id):
        with self._lock:
            self._generation[user_id] = self._generation.get(user_id, 0) + 1
            existed = self._sessions.pop(user_id, None) is not None
        self._context(user_id)
        return existed

    def check_health(self, user_id):
        """A quiet browser does not imply a valid position or a working camera."""
        with self._lock:
            session = self._sessions.get(user_id)
            if not session or session["state"] != "NAVIGATING":
                return deepcopy(session)
            now_ms = int(time.time() * 1000)
            camera_stale = session["vision_at_ms"] and now_ms - session["vision_at_ms"] > 6000
            gps_stale = now_ms - session["last_position"]["timestamp_ms"] > 15000
            if not camera_stale and not gps_stale:
                return deepcopy(session)
            session["state"] = "UNCERTAIN"
            session["uncertain_reason"] = "VISION" if camera_stale else "GPS"
            session["recovery_hits"] = 0
            session["context_epoch"] += 1
            result = deepcopy(session)
        self._context(user_id, result)
        message = ("摄像头观察已中断，请停下确认路径。" if camera_stale else
                   "定位已中断，请停下确认当前位置。")
        self.bus.publish(user_id, "speech", message, priority="SAFETY", ttl_ms=8000,
                         session_id=result["session_id"], route_revision=result["route_revision"],
                         dedupe_key="camera_stale" if camera_stale else "gps_stale")
        return result

    def replan(self, user_id, location):
        old = self.snapshot(user_id)
        if not old:
            raise ValueError("尚未开始导航")
        return self.start(user_id, {**old["route"]["destination"], "coord_type": "bd09ll"}, location)

    def update_position(self, user_id, location):
        checked = self.validate_location(location)
        with self._lock:
            old = self._sessions.get(user_id)
            if old and checked["timestamp_ms"] <= old["last_position"]["timestamp_ms"]:
                raise ValueError("收到乱序的定位结果")
        position = self._convert(checked)
        publications = []
        with self._lock:
            session = self._sessions.get(user_id)
            if not session:
                return {"position": position, "navigation": None}
            if position["timestamp_ms"] <= session["last_position"]["timestamp_ms"]:
                raise ValueError("收到乱序的定位结果")
            session["last_position"] = position
            if session["state"] == "PLANNED":
                return {"position": position, "navigation": deepcopy(session)}
            now_ms = position["timestamp_ms"]
            steps = session["route"]["steps"]
            step = steps[session["step_index"]]
            previous_state = session["state"]
            previous_step = session["step_index"]
            if session["vision_at_ms"] and now_ms - session["vision_at_ms"] > 6000:
                session["vision_status"] = "STALE"
                session["state"] = "UNCERTAIN"
                session["uncertain_reason"] = "VISION"
                session["recovery_hits"] = 0
                if now_ms - session["last_warning_ms"] > 12000:
                    session["last_warning_ms"] = now_ms
                    publications.append(("摄像头观察已中断，请停下确认路径。", "SAFETY", "camera_stale", None))
            if position["accuracy"] > 12:
                session["state"] = "UNCERTAIN"
                if session["uncertain_reason"] not in ("VISION", "OFF_ROUTE"):
                    session["uncertain_reason"] = "GPS"
                session["recovery_hits"] = 0
                if now_ms - session["last_warning_ms"] > 12000:
                    session["last_warning_ms"] = now_ms
                    publications.append(("定位误差较大，请停下确认周围环境。", "SAFETY", "poor_gps", None))
            else:
                cross_track = min(distance_to_step(position, s) for s in steps[max(0, session["step_index"] - 1):min(len(steps), session["step_index"] + 2)])
                session["deviation_hits"] = session["deviation_hits"] + 1 if cross_track > max(25, 2 * position["accuracy"]) else 0
                if session["deviation_hits"] >= 3:
                    session["state"] = "UNCERTAIN"
                    session["uncertain_reason"] = "OFF_ROUTE"
                    session["recovery_hits"] = 0
                    if now_ms - session["last_warning_ms"] > 12000:
                        session["last_warning_ms"] = now_ms
                        publications.append(("当前位置与路线不符，请停下确认，必要时重新规划。", "SAFETY", "off_route", None))
                elif session["state"] == "UNCERTAIN" and session["uncertain_reason"] not in ("OFF_ROUTE", "CROSSING"):
                    vision_ok = session["vision_status"] != "NOT_VISIBLE" and (
                        session["uncertain_reason"] != "VISION" or (
                            session["vision_status"] == "VISIBLE" and
                            session["visible_frames"] >= 2 and
                            now_ms - session["vision_at_ms"] <= 5000))
                    session["recovery_hits"] = session["recovery_hits"] + 1 if vision_ok else 0
                    if session["recovery_hits"] >= 2:
                        session["state"] = "NAVIGATING"
                        session["uncertain_reason"] = None
                        session["recovery_hits"] = 0

                if session["state"] == "NAVIGATING" and (
                    not session["vision_at_ms"] or session["vision_status"] == "VISIBLE"):
                    proximity = max(8, min(15, position["accuracy"] * 1.5))
                    distance_to_end = meters(position, step["end"])
                    next_step = steps[session["step_index"] + 1] if session["step_index"] + 1 < len(steps) else None
                    direction = planned_turn(next_step) if next_step else None
                    if next_step and requires_road_crossing(next_step) and distance_to_end <= max(15, 2 * position["accuracy"]):
                        session["state"] = "UNCERTAIN"
                        session["uncertain_reason"] = "CROSSING"
                        publications.append(("步行路线接下来需要过街，请停下并通过可靠的行人设施确认后再继续。",
                                             "SAFETY", "crossing", None))
                    elif direction and distance_to_end <= max(12, 1.5 * position["accuracy"]) and now_ms - session["last_advisory_ms"] > 8000:
                        session["last_advisory_ms"] = now_ms
                        publications.append((f"路线预计前方向{direction}转，请减速并确认该方向的盲道后再前行。", "ROUTE", f"step:{session['step_index']}:advisory", session["step_index"]))
                    if next_step:
                        # Standing by the junction must not advance the step.
                        # Require two fixes showing movement onto the next segment.
                        passed_junction = (distance_to_end <= max(20, 3 * position["accuracy"])
                                           and meters(position, next_step["start"]) >= max(10, 2 * position["accuracy"])
                                           and distance_to_step(position, next_step) <= proximity)
                    else:
                        passed_junction = distance_to_end <= proximity
                    session["endpoint_hits"] = session["endpoint_hits"] + 1 if passed_junction and session["state"] == "NAVIGATING" else 0
                    if next_step and session["endpoint_hits"] >= 2:
                        session["step_index"] += 1
                        session["endpoint_hits"] = 0
                        session["last_advisory_ms"] = 0
                    elif not next_step and session["endpoint_hits"] >= 2:
                        session["state"] = "ARRIVAL_UNCONFIRMED"
                        publications.append(("定位显示已接近目的地，请确认实际入口。", "ROUTE", "arrival", session["step_index"]))
            if session["state"] != previous_state or session["step_index"] != previous_step:
                session["context_epoch"] += 1
            snapshot = deepcopy(session)
        if snapshot["state"] != previous_state or snapshot["step_index"] != previous_step:
            self._context(user_id, snapshot)
        for text, priority, key, event_step in publications:
            self.bus.publish(user_id, "speech", text, priority=priority, ttl_ms=7000 if priority == "SAFETY" else 11000,
                             session_id=snapshot["session_id"], route_revision=snapshot["route_revision"],
                             step_id=event_step,
                             dedupe_key=key)
        return {"position": position, "navigation": snapshot}

    def report_visual(self, user_id, visible):
        publications = []
        with self._lock:
            session = self._sessions.get(user_id)
            if not session:
                return None
            now_ms = int(time.time() * 1000)
            session["vision_at_ms"] = now_ms
            session["missing_frames"] = 0 if visible else (3 if visible is None else session["missing_frames"] + 1)
            session["visible_frames"] = session["visible_frames"] + 1 if visible else 0
            session["vision_status"] = ("VISIBLE" if visible else
                                        "UNAVAILABLE" if visible is None else
                                        "NOT_VISIBLE" if session["missing_frames"] >= 3 else "UNCERTAIN")
            if session["state"] == "NAVIGATING" and session["vision_status"] in ("NOT_VISIBLE", "UNAVAILABLE"):
                session["state"] = "UNCERTAIN"
                session["uncertain_reason"] = "VISION"
                session["recovery_hits"] = 0
                session["context_epoch"] += 1
                if now_ms - session["last_warning_ms"] > 6000:
                    session["last_warning_ms"] = now_ms
                    publications.append("摄像头观察不可用，请停下并确认路径。" if visible is None else
                                        "当前未识别到盲道，请停下并确认脚下路径。")
            result = deepcopy(session)
        if publications:
            self._context(user_id, result)
        for text in publications:
            self.bus.publish(user_id, "speech", text, priority="SAFETY", ttl_ms=4000,
                             session_id=result["session_id"], route_revision=result["route_revision"],
                             dedupe_key="tactile_not_visible")
        return result
