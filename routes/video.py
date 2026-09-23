"""Authenticated recorded-video detection display.

Recorded frames have no relationship to a user's live location. This route
never publishes navigation or audio events; live observations use /vision/frame.
"""

from threading import RLock
from uuid import uuid4
import os
import time

import cv2
from flask import Blueprint, Response, jsonify, request, session
from werkzeug.utils import secure_filename

from config import UPLOAD_FOLDER
from services.vision_observer import vision_observer
from utils.decorators import login_required
from utils.video_utils import allowed_file, create_error_frame, create_info_frame


video_bp = Blueprint("video", __name__)
_uploads = {}
_uploads_lock = RLock()


def _remove_file(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except OSError:
        # Deletion failure must not roll back a successfully swapped stream.
        pass


def _release(item):
    """Retire uploaded files only after every MJPEG reader closes them."""
    with _uploads_lock:
        item["readers"] -= 1
        if item["retired"] and item["readers"] == 0:
            _remove_file(item["path"])


def _mjpeg(frame):
    ok, buffer = cv2.imencode(".jpg", frame)
    if ok:
        return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"
    return b""


def generate_frames(user_id):
    while True:
        with _uploads_lock:
            item = _uploads.get(user_id)
            claimed = bool(item and item["active"])
            if claimed:
                item["readers"] += 1
        if not claimed:
            yield _mjpeg(create_info_frame("请上传视频文件开始检测展示"))
            time.sleep(1)
            continue

        cap = cv2.VideoCapture(item["path"])
        if not cap.isOpened():
            with _uploads_lock:
                if _uploads.get(user_id) is item:
                    item["active"] = False
                item["retired"] = True
            try:
                yield _mjpeg(create_error_frame("视频无法打开"))
            finally:
                cap.release()
                _release(item)
            continue

        fps = cap.get(cv2.CAP_PROP_FPS) or 10
        interval = 1 / max(1, min(10, fps))
        try:
            while True:
                with _uploads_lock:
                    if _uploads.get(user_id) is not item or not item["active"]:
                        break
                ok, frame = cap.read()
                if not ok:
                    with _uploads_lock:
                        if _uploads.get(user_id) is item:
                            item["active"] = False
                        item["retired"] = True
                    yield _mjpeg(create_info_frame("视频已播放完毕"))
                    break
                try:
                    observation = vision_observer.analyze_frame(frame)
                    for detection in observation["boxes"]:
                        x1, y1, x2, y2 = map(int, detection["box"])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                except Exception:
                    yield _mjpeg(create_error_frame("盲道识别暂时不可用"))
                    break
                yield _mjpeg(frame)
                time.sleep(interval)
        finally:
            cap.release()
            _release(item)


@video_bp.route("/video_feed")
@login_required
def video_feed():
    return Response(generate_frames(session["user_id"]),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@video_bp.route("/stream_speech_text")
@login_required
def stream_speech_text():
    return jsonify({"status": "error", "message": "请订阅 /guidance/events"}), 410


@video_bp.route("/upload_video", methods=["POST"])
@login_required
def upload_video():
    uploaded = request.files.get("video")
    if not uploaded or not uploaded.filename or not allowed_file(uploaded.filename):
        return jsonify({"status": "error", "message": "请选择受支持的视频文件"}), 400
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    safe_name = secure_filename(uploaded.filename) or "video.mp4"
    path = os.path.join(UPLOAD_FOLDER, f"{session['user_id']}_{uuid4().hex}_{safe_name}")
    try:
        uploaded.save(path)
        cap = cv2.VideoCapture(path)
        ok, _ = cap.read() if cap.isOpened() else (False, None)
        cap.release()
        if not ok:
            _remove_file(path)
            return jsonify({"status": "error", "message": "视频无法读取"}), 400
        with _uploads_lock:
            old = _uploads.get(session["user_id"])
            _uploads[session["user_id"]] = {"path": path, "active": True,
                                              "readers": 0, "retired": False}
        # The prior stream checks object identity and closes its file handle.
        # Avoid deleting that file immediately while another stream reads it.
        if old and old.get("path") != path:
            with _uploads_lock:
                old["active"] = False
                old["retired"] = True
                if old["readers"] == 0:
                    _remove_file(old["path"])
        return jsonify({"status": "success", "message": "视频上传成功；仅用于检测展示"})
    except Exception:
        if os.path.exists(path):
            _remove_file(path)
        return jsonify({"status": "error", "message": "视频上传失败"}), 500
