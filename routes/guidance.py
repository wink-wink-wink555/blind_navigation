"""Authenticated browser navigation, vision observations and event stream."""

import json
import time

from flask import Blueprint, Response, jsonify, request, session

from config import BAIDU_MAP_CONFIG
from services.baidu_navigation import BaiduWalkingProvider, MapServiceError, require_bd09
from services.guidance_bus import guidance_bus
from services.location_store import record as record_location
from services.navigation import NavigationManager
from services.vision_observer import vision_observer
from utils.decorators import login_required


guidance_bp = Blueprint("guidance", __name__)
navigation_manager = NavigationManager(BaiduWalkingProvider(BAIDU_MAP_CONFIG["api_key"]), guidance_bus)


def _live_geometry_stream_id(user_id):
    """Stable per-user key for the current live camera stream.

    Navigation state is already keyed per user. Start/replan/stop and camera
    loss explicitly reset this key, so temporal geometry can never leak across
    navigation sessions while consecutive live frames still retain continuity.
    """
    return ("live", int(user_id))


def _reset_live_geometry(user_id):
    vision_observer.reset_geometry_stream(_live_geometry_stream_id(user_id))


def _result(action):
    try:
        return jsonify({"status": "success", **action()})
    except ValueError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except MapServiceError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 502


@guidance_bp.route("/navigation/start", methods=["POST"])
@login_required
def start_navigation():
    data = request.get_json(silent=True) or {}

    def action():
        user_id = session["user_id"]
        navigation = navigation_manager.start(
            user_id, data.get("destination") or {}, data.get("position") or {})
        # Reset only after a successful route start. A malformed request that
        # never replaces the current navigation session should not disturb the
        # current camera track.
        _reset_live_geometry(user_id)
        return {"navigation": navigation}

    return _result(action)


@guidance_bp.route("/navigation/preview", methods=["POST"])
@login_required
def preview_navigation():
    """A manual map origin previews a route; it cannot start live guidance."""
    data = request.get_json(silent=True) or {}
    return _result(lambda: {"route": navigation_manager.provider.plan(
        require_bd09(data.get("origin")), require_bd09(data.get("destination")))})


@guidance_bp.route("/navigation/position", methods=["POST"])
@login_required
def navigation_position():
    data = request.get_json(silent=True) or {}

    def action():
        result = navigation_manager.update_position(session["user_id"], data.get("position"))
        record_location(session["user_id"], result["position"])
        return result

    return _result(action)


@guidance_bp.route("/navigation/activate", methods=["POST"])
@login_required
def activate_navigation():
    return _result(lambda: {"navigation": navigation_manager.activate(session["user_id"])})


@guidance_bp.route("/navigation/replan", methods=["POST"])
@login_required
def replan_navigation():
    data = request.get_json(silent=True) or {}

    def action():
        user_id = session["user_id"]
        navigation = navigation_manager.replan(user_id, data.get("position") or {})
        _reset_live_geometry(user_id)
        return {"navigation": navigation}

    return _result(action)


@guidance_bp.route("/navigation/stop", methods=["POST"])
@login_required
def stop_navigation():
    def action():
        user_id = session["user_id"]
        stopped = navigation_manager.stop(user_id)
        _reset_live_geometry(user_id)
        return {"stopped": stopped, "context": navigation_manager.context(user_id)}

    return _result(action)


@guidance_bp.route("/navigation/status", methods=["GET"])
@login_required
def navigation_status():
    return jsonify({"status": "success", "navigation": navigation_manager.check_health(session["user_id"]),
                    "context": navigation_manager.context(session["user_id"])})


@guidance_bp.route("/vision/frame", methods=["POST"])
@login_required
def observe_frame():
    # This timestamp comes from the Flask host, not from browser Date.now().
    # It is the freshness anchor used by NavigationManager, so client/server
    # wall-clock skew cannot invalidate otherwise fresh visual observations.
    server_received_at_ms = int(time.time() * 1000)

    if "frame" not in request.files:
        return jsonify({"status": "error", "message": "缺少图像帧"}), 400
    frame = request.files["frame"].read(600001)
    if not frame or len(frame) > 600000:
        return jsonify({"status": "error", "message": "图像帧为空或超过600KB"}), 400
    try:
        frame_seq = request.form.get("frame_seq")
        captured_at_ms = request.form.get("captured_at_ms")
        frame_seq = int(frame_seq) if frame_seq not in (None, "") else None
        captured_at_ms = int(captured_at_ms) if captured_at_ms not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"status": "error", "message": "无效的帧序号或采集时间"}), 400
    try:
        user_id = session["user_id"]
        observation = vision_observer.analyze(
            frame,
            frame_seq=frame_seq,
            captured_at_ms=captured_at_ms,
            geometry_stream_id=_live_geometry_stream_id(user_id),
            server_received_at_ms=server_received_at_ms,
        )
        navigation = navigation_manager.report_visual(user_id, observation)
        return jsonify({"status": "success", "observation": observation,
                        "vision_status": navigation["vision_status"] if navigation else "NO_SESSION",
                        "alignment": ({"state": navigation["alignment_state"],
                                       "epoch": navigation["alignment_epoch"],
                                       "offset": (navigation["alignment_history"][-1]
                                                  if navigation["alignment_history"] else None)}
                                      if navigation else None)})
    except (RuntimeError, ValueError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@guidance_bp.route("/vision/unavailable", methods=["POST"])
@login_required
def vision_unavailable():
    user_id = session["user_id"]
    # Reconnecting a camera starts a fresh geometry track; do not compare its
    # first frame against a center remembered before the interruption.
    _reset_live_geometry(user_id)
    navigation = navigation_manager.report_visual(user_id, None)
    return jsonify({"status": "success", "navigation": navigation})


@guidance_bp.route("/guidance/events", methods=["GET"])
@login_required
def event_stream():
    user_id = session["user_id"]
    cursor = request.headers.get("Last-Event-ID") or request.args.get("after", "0")
    try:
        cursor = max(0, int(cursor))
    except ValueError:
        cursor = 0

    def events():
        last = cursor
        while True:
            batch = guidance_bus.events_since(user_id, last, timeout=15)
            if not batch:
                # Move past expired events as well; otherwise an empty expired
                # batch can cause the stream to spin on the same cursor.
                last = max(last, guidance_bus.latest_id(user_id))
                yield ": heartbeat\n\n"
                continue
            for event in batch:
                last = event["id"]
                yield (f"id: {event['id']}\nevent: guidance\n"
                       f"data: {json.dumps(event, ensure_ascii=False)}\n\n")

    return Response(events(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"
    })


@guidance_bp.route("/guidance/ack", methods=["POST"])
@login_required
def acknowledge_event():
    data = request.get_json(silent=True) or {}
    return _result(lambda: {"delivery_status": guidance_bus.acknowledge(
        session["user_id"], data.get("event_id"), data.get("delivery_status"))})
