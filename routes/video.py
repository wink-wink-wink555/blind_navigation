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
from utils.voice_utils import speak, get_prompt_template
from config import MODEL_WEIGHTS, UPLOAD_FOLDER, THRESHOLD_SLOPE, CALL_INTERVAL, DEEPSEEK_CONFIG, COLLISION_AWARENESS_CONFIG
from services.collision_awareness import CollisionAwarenessManager

video_bp = Blueprint('video', __name__)

# 加载YOLO模型
model = YOLO(MODEL_WEIGHTS)

# 初始化碰撞预警管理器
collision_manager = CollisionAwarenessManager(
    ttc_threshold=COLLISION_AWARENESS_CONFIG.get("ttc_threshold", 3.0),
    alert_cooldown=COLLISION_AWARENESS_CONFIG.get("alert_cooldown", 5.0)
)

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
    调用 DeepSeek API 生成导航语音内容
    
    Args:
        system_prompt: 系统提示词
        user_message: 用户消息
        
    Returns:
        tuple: (success, content) - 成功标志和生成的内容
    """
    try:
        headers = {
            'Authorization': f'Bearer {DEEPSEEK_CONFIG["api_key"]}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'model': DEEPSEEK_CONFIG['model'],
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_message}
            ],
            'temperature': 0.7,
            'max_tokens': 150
        }
        
        response = requests.post(DEEPSEEK_CONFIG['base_url'], headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content'].strip()
            if content:
                return True, content
            else:
                return False, ""
        else:
            print(f"[DeepSeek API] 请求失败，状态码: {response.status_code}")
            return False, ""
            
    except Exception as e:
        print(f"[DeepSeek API] 调用异常: {type(e).__name__}: {e}")
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
                    label_name = class_names[cls]
                    label = f"{label_name}: {conf:.2f}"
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
                    cv2.putText(frame, label, (int(x1), int(y1) - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # --- Collision Awareness Integration ---
            if COLLISION_AWARENESS_CONFIG.get("enable", False):
                # Prepare detections for collision manager
                collision_dets = []
                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        cls = int(box.cls[0])
                        collision_dets.append({
                            'box': (x1, y1, x2, y2),
                            'label': model.names[cls]
                        })
                
                # Process detections
                collision_result = collision_manager.process_frame(collision_dets)
                
                # Handle alerts
                if collision_result["trigger_alert"] and collision_result["alert_message"]:
                    from utils.voice_utils import SpeechPriority
                    current_speech_text = collision_result["alert_message"]
                    speak(current_speech_text, get_user_settings_for_video(), priority=SpeechPriority.URGENT)
                    print(f"[碰撞预警] 触发紧急语音提示: {current_speech_text}")

                # Optional: Overlay threat scores on frame
                for det in collision_result["detections"]:
                    if det.get('threat_score', 0) > 50:
                        x1, y1, x2, y2 = det['box']
                        score = det['threat_score']
                        cv2.putText(frame, f"THREAT: {score}", (int(x1), int(y2) + 20), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            # ----------------------------------------

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
                        answer_content = f"请注意，盲道向左转了，请往左走。"

                    # 设置语音文本并播放
                    current_speech_text = answer_content
                    speak(answer_content, user_settings)
                    last_call_time = current_time
                    print(f"[盲道检测] 已发送左转语音提示到播放队列")

                elif slope > THRESHOLD_SLOPE:
                    # 斜率显著为正，提示右转
                    print("[盲道检测] 检测到右转")
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
                        answer_content = f"请注意，盲道向右转了，请往右走。"

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

