"""
视频相关路由 - 视频上传、处理、流式传输
"""
from flask import Blueprint, Response, request, jsonify
import cv2
import numpy as np
import requests
import threading
import time
import os
from werkzeug.utils import secure_filename
from ultralytics import YOLO

from utils.decorators import login_required
from utils.video_utils import allowed_file, create_error_frame, create_info_frame
from utils.voice_utils import speak, get_prompt_template, build_static_turn_text
from services.ai_provider import chat_completion as unified_chat_completion
from config import MODEL_WEIGHTS, UPLOAD_FOLDER, THRESHOLD_SLOPE, CALL_INTERVAL

video_bp = Blueprint('video', __name__)

# 加载YOLO模型
model = YOLO(MODEL_WEIGHTS)

# 全局变量
current_video_path = None
video_active = False
last_call_time = 0
current_speech_text = ""

# 转向提示问题
right_turn_question = "请用亲切且简短的话语告知要往右拐，因为盲道是往右拐的"
left_turn_question = "请用亲切且简短的话语告知要往左拐，因为盲道是往左拐的"


def call_deepseek_api(system_prompt, user_message):
    """
    调用当前激活用户配置的文本模型生成导航语音内容（云端 or 本地 Ollama）
    
    Args:
        system_prompt: 系统提示词
        user_message: 用户消息
        
    Returns:
        tuple: (success, content) - 成功标志和生成的内容
    """
    try:
        # 视频流跑在后台线程，没有 session 上下文，
        # 通过 routes.main 暴露的全局活跃 user_id 取配置
        from routes.main import get_current_active_user_id
        user_id = get_current_active_user_id()

        result = unified_chat_completion(
            user_id,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message}
            ],
            temperature=0.7,
            max_tokens=150,
            timeout=15.0
        )
        if result['success'] and result['content']:
            return True, result['content']
        if not result['success']:
            print(f"[Video LLM] 调用失败: {result.get('error')}")
        return False, ""
    except Exception as e:
        print(f"[Video LLM] 调用异常: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False, ""


def get_user_settings_for_video():
    """
    获取用户设置（从 routes.main 模块）
    注意：这个函数在视频流生成器中调用，无法访问 session
    所以使用全局变量
    """
    from routes.main import user_settings
    return user_settings


def generate_frames():
    """生成视频帧用于流式传输"""
    global last_call_time, current_speech_text, current_video_path, video_active

    # 如果视频未激活，显示等待上传提示
    if not video_active or not current_video_path:
        # 设置默认的提示文本
        current_speech_text = "提示：系统会实时分析盲道方向，当方向发生变化时会自动播报语音提示。"
        while not video_active or not current_video_path:
            wait_frame = create_info_frame("请上传视频文件开始分析")
            ret, buffer = cv2.imencode('.jpg', wait_frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(1)

    # 视频已激活，开始处理
    try:
        cap = cv2.VideoCapture(current_video_path)

        if not cap.isOpened():
            print(f"无法打开视频: {current_video_path}")
            # 尝试使用ffmpeg参数打开
            cap = cv2.VideoCapture(current_video_path, cv2.CAP_FFMPEG)

            if not cap.isOpened():
                # 仍然无法打开，显示错误信息
                error_frame = create_error_frame(f"无法打开视频文件: {os.path.basename(current_video_path)}")
                ret, buffer = cv2.imencode('.jpg', error_frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                video_active = False
                current_speech_text = "视频无法打开，请尝试上传其他格式的视频。"
                return

        frame_count = 0

        while cap.isOpened() and video_active:
            ret, frame = cap.read()
            frame_count += 1

            if not ret:
                if frame_count < 10:  # 如果连前10帧都读不出来
                    print(f"无法读取视频帧: {current_video_path}")
                    error_frame = create_error_frame("视频文件损坏或格式不支持")
                    ret, buffer = cv2.imencode('.jpg', error_frame)
                    frame = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    video_active = False
                    current_speech_text = "视频文件损坏或格式不支持，请尝试其他视频。"
                    break

                # 视频正常结束
                end_frame = create_info_frame("视频已播放完毕，请上传新视频")
                ret, buffer = cv2.imencode('.jpg', end_frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                video_active = False
                current_speech_text = "视频播放完毕，请上传新视频。"
                break

            # 处理视频帧 - YOLO检测
            results = model(frame)
            centers = []  # 存储所有检测框的 (center_x, center_y)

            for result in results:
                boxes = result.boxes
                for box in boxes:
                    x1, y1, x2, y2 = box.xyxy[0]
                    conf = box.conf[0]
                    cls = int(box.cls[0])
                    center_x = (x1 + x2) / 2
                    center_y = (y1 + y2) / 2
                    centers.append((center_x, center_y))

                    class_names = model.names
                    label = f"{class_names[cls]}: {conf:.2f}"
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(frame, label, (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            current_time = time.time()
            if len(centers) >= 2 and current_time - last_call_time >= CALL_INTERVAL:
                ys = np.array([c[1] for c in centers])
                xs = np.array([c[0] for c in centers])
                slope, intercept = np.polyfit(ys, xs, 1)

                print(f"[盲道检测] 斜率: {slope}, 拦截: {intercept}")

                user_settings = get_user_settings_for_video()

                if slope < -THRESHOLD_SLOPE:
                    # 斜率显著为负，提示左转
                    print("[盲道检测] 检测到左转")

                    if user_settings.get("encourage") == "关":
                        # 关闭鼓励 → 硬编码模板，跳过 LLM，响应即时且稳定
                        answer_content = build_static_turn_text("left", user_settings)
                        print(f"[盲道检测] 鼓励已关闭，使用硬编码模板: {answer_content}")
                    else:
                        # 开启鼓励 → LLM 生成，保留温暖、有变化的口吻
                        answer_content = None
                        api_success = False

                        print(f"[DeepSeek API] 调用 DeepSeek API 生成左转提示")
                        print(f"[DeepSeek API] 使用的提示词模板:\n{get_prompt_template(user_settings)}")
                        print(f"[DeepSeek API] 用户问题: {left_turn_question}")

                        api_success, answer_content = call_deepseek_api(
                            get_prompt_template(user_settings),
                            left_turn_question
                        )

                        if api_success and answer_content:
                            print(f"[DeepSeek API] ✓ 成功获取 AI 响应")
                            print(f"[DeepSeek API] AI 生成内容: {answer_content}")
                        else:
                            print(f"[DeepSeek API] ✗ API 调用失败或返回内容为空")
                            print(f"[盲道检测] 使用默认左转提示")
                            answer_content = build_static_turn_text("left", user_settings)

                    # 设置语音文本并播放
                    current_speech_text = answer_content
                    speak(answer_content, user_settings)
                    last_call_time = current_time
                    print(f"[盲道检测] 已发送左转语音提示到播放队列")

                elif slope > THRESHOLD_SLOPE:
                    # 斜率显著为正，提示右转
                    print("[盲道检测] 检测到右转")

                    if user_settings.get("encourage") == "关":
                        # 关闭鼓励 → 硬编码模板，跳过 LLM，响应即时且稳定
                        answer_content = build_static_turn_text("right", user_settings)
                        print(f"[盲道检测] 鼓励已关闭，使用硬编码模板: {answer_content}")
                    else:
                        # 开启鼓励 → LLM 生成，保留温暖、有变化的口吻
                        answer_content = None
                        api_success = False

                        print(f"[DeepSeek API] 调用 DeepSeek API 生成右转提示")
                        print(f"[DeepSeek API] 使用的提示词模板:\n{get_prompt_template(user_settings)}")
                        print(f"[DeepSeek API] 用户问题: {right_turn_question}")

                        api_success, answer_content = call_deepseek_api(
                            get_prompt_template(user_settings),
                            right_turn_question
                        )

                        if api_success and answer_content:
                            print(f"[DeepSeek API] ✓ 成功获取 AI 响应")
                            print(f"[DeepSeek API] AI 生成内容: {answer_content}")
                        else:
                            print(f"[DeepSeek API] ✗ API 调用失败或返回内容为空")
                            print(f"[盲道检测] 使用默认右转提示")
                            answer_content = build_static_turn_text("right", user_settings)

                    # 设置语音文本并播放
                    current_speech_text = answer_content
                    speak(answer_content, user_settings)
                    last_call_time = current_time
                    print(f"[盲道检测] 已发送右转语音提示到播放队列")

            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

        cap.release()

    except Exception as e:
        print(f"视频处理错误: {e}")
        import traceback
        traceback.print_exc()
        error_frame = create_error_frame(f"视频处理错误: {str(e)}")
        ret, buffer = cv2.imencode('.jpg', error_frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        video_active = False
        current_speech_text = "视频处理出错，请尝试上传其他视频。"


@video_bp.route('/video_feed')
def video_feed():
    """视频流式传输端点"""
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@video_bp.route('/stream_speech_text')
def stream_speech_text():
    """流式传输语音文本"""
    def generate():
        global current_speech_text
        last_sent = ""

        # 设置初始默认消息
        if not current_speech_text:
            current_speech_text = "提示：系统会实时分析盲道方向，当方向发生变化时会自动播报语音提示。"

        while True:
            if current_speech_text != last_sent:
                last_sent = current_speech_text
                yield f"{current_speech_text}\n\n"
            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')


@video_bp.route('/upload_video', methods=['POST'])
def upload_video():
    """处理视频上传"""
    global current_video_path, video_active

    if 'video' not in request.files:
        return jsonify({"status": "error", "message": "没有上传文件"}), 400

    file = request.files['video']

    if file.filename == '':
        return jsonify({"status": "error", "message": "未选择文件"}), 400

    if not allowed_file(file.filename):
        from config import ALLOWED_EXTENSIONS
        return jsonify(
            {"status": "error", "message": f"不支持的文件类型，允许的类型: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    try:
        # 创建上传目录（如果不存在）
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)

        # 使用时间戳生成唯一文件名，避免文件名冲突
        timestamp = int(time.time())
        filename = f"{timestamp}_{secure_filename(file.filename)}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)

        # 检查视频是否可以打开
        test_cap = cv2.VideoCapture(file_path)
        if not test_cap.isOpened():
            test_cap.release()
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"status": "error", "message": "无法打开视频文件，请检查文件格式或尝试其他视频"}), 400

        # 读取几帧确认真的可以读取
        read_success = False
        for _ in range(5):  # 尝试读取前5帧
            ret, _ = test_cap.read()
            if ret:
                read_success = True
                break

        test_cap.release()

        if not read_success:
            if os.path.exists(file_path):
                os.remove(file_path)
            return jsonify({"status": "error", "message": "视频文件无法正常读取帧，请尝试其他视频"}), 400

        # 如果之前有视频文件，先删除
        if current_video_path and os.path.exists(current_video_path):
            try:
                os.remove(current_video_path)
            except Exception as e:
                print(f"无法删除旧视频文件: {e}")

        current_video_path = file_path
        video_active = True
        print(f"成功上传视频: {file_path}")

        return jsonify({
            "status": "success",
            "message": "视频上传成功",
            "file_path": file_path
        })
    except Exception as e:
        print(f"视频上传错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"上传失败: {str(e)}"}), 500

