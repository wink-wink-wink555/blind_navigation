"""Authenticated browser navigation, vision observations and event stream."""

import json

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
    return _result(lambda: {"navigation": navigation_manager.start(
        session["user_id"], data.get("destination") or {}, data.get("position") or {})})


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
    return _result(lambda: {"navigation": navigation_manager.replan(
        session["user_id"], data.get("position") or {})})


@guidance_bp.route("/navigation/stop", methods=["POST"])
@login_required
def stop_navigation():
    def action():
        stopped = navigation_manager.stop(session["user_id"])
        return {"stopped": stopped, "context": navigation_manager.context(session["user_id"])}
    return _result(action)


@guidance_bp.route("/navigation/status", methods=["GET"])
@login_required
def navigation_status():
    return jsonify({"status": "success", "navigation": navigation_manager.check_health(session["user_id"]),
                    "context": navigation_manager.context(session["user_id"])})


@guidance_bp.route("/vision/frame", methods=["POST"])
@login_required
def observe_frame():
    if "frame" not in request.files:
        return jsonify({"status": "error", "message": "缺少图像帧"}), 400
    frame = request.files["frame"].read(600001)
    if not frame or len(frame) > 600000:
        return jsonify({"status": "error", "message": "图像帧为空或超过600KB"}), 400
    try:
        observation = vision_observer.analyze(frame)
        navigation = navigation_manager.report_visual(session["user_id"], observation["visible"])
        return jsonify({"status": "success", "observation": observation,
                        "vision_status": navigation["vision_status"] if navigation else "NO_SESSION"})
    except (RuntimeError, ValueError) as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@guidance_bp.route("/vision/unavailable", methods=["POST"])
@login_required
def vision_unavailable():
    navigation = navigation_manager.report_visual(session["user_id"], None)
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
