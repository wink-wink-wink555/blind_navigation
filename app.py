from flask import Flask, render_template, Response, request, jsonify, redirect, url_for, session
import cv2
from ultralytics import YOLO
import ollama
import pyttsx3
import threading
import time
import os
import pymysql
import hashlib
import random
import string
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from werkzeug.utils import secure_filename
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
import functools
import geopy.distance  # 添加地理距离计算库

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_blind_navigation_app'  # 用于session加密

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',  # 根据实际情况填写密码
    'db': 'blind_navigation',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

# 邮件发送配置
EMAIL_CONFIG = {
    'sender': 'your_email@example.com',  # 发件人邮箱
    'password': 'your_password',  # 邮箱授权码（需要实际配置）
    'smtp_server': 'smtp.example.com',  # SMTP服务器
    'smtp_port': 465  # SMTP端口
}

# 验证码存储
verification_codes = {}  # 格式: {email: {'code': '123456', 'expires': timestamp}}

# 配置上传文件
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 300 * 1024 * 1024  # 限制上传大小为300MB

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 模型加载
model_weights = "models/weights/best.pt"  # 使用相对路径
model = YOLO(model_weights)

# 全局变量
current_video_path = None
video_active = False
last_call_time = 0
call_interval = 14
current_speech_text = ""
latest_speech_text = "等待视频上传和分析..."
camera = None
voices_cache = None

# 用户设置
user_settings = {
    "gender": "未指定",  # 性别：男/女/未指定
    "name": "用户",  # 用户名称
    "age": "未指定",  # 年龄段：青年/中年/老年/未指定
    "voice_speed": "中等",  # 语音速度：慢/中等/快
    "voice_volume": "中等",  # 语音音量：低/中等/高
    "user_mode": "盲人端"  # 用户模式：盲人端/家属端
}

# 位置数据存储
user_locations = {}  # 格式: {user_id: {'lat': latitude, 'lng': longitude, 'timestamp': timestamp}}


# 数据库操作函数
def get_db_connection():
    """创建数据库连接"""
    try:
        connection = pymysql.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        print(f"数据库连接错误: {e}")
        return None


# 验证码相关函数
def generate_verification_code(length=6):
    """生成指定长度的数字验证码"""
    return ''.join(random.choices(string.digits, k=length))


def is_valid_email(email):
    """简单验证邮箱格式"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def send_verification_email(to_email, verification_code):
    """发送验证码邮件"""
    try:
        # 创建HTML邮件内容（关键点：使用HTML格式并添加样式）
        html_content = f"""
        <html>
            <head>
                <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            </head>
            <body>
                <p style="font-size: 16px; color: #333;">您的验证码是：</p>
                <div style="
                    font-size: 24px;
                    color: #ff4444;
                    font-weight: bold;
                    margin: 10px 0;
                    padding: 12px;
                    background: #f8f9fa;
                    border-radius: 8px;
                    display: inline-block;
                ">{verification_code}</div>
                <p style="font-size: 14px; color: #666; margin-top: 10px;">
                    验证码10分钟内有效，请勿告知他人。如果这不是您本人的操作，请忽略此邮件。
                </p>
            </body>
        </html>
        """

        # 使用MIMEText指定HTML类型
        message = MIMEText(html_content, 'html', 'utf-8')

        # 规范发件人格式
        from email.utils import formataddr
        message['From'] = formataddr(("盲道导航助手", EMAIL_CONFIG['sender']))
        message['To'] = Header(to_email)
        message['Subject'] = Header('【盲道导航助手】验证码', 'utf-8')

        # 建立连接并发送邮件
        server = smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
        server.sendmail(EMAIL_CONFIG['sender'], [to_email], message.as_string())
        server.quit()

        # 保存验证码，设置10分钟有效期
        verification_codes[to_email] = {
            'code': verification_code,
            'expires': time.time() + 600  # 10分钟后过期
        }

        return True, "验证码已发送"
    except Exception as e:
        print(f"发送邮件失败: {e}")
        return False, f"发送验证码失败: {str(e)}"

def verify_code(email, code):
    """验证邮箱验证码"""
    if email not in verification_codes:
        return False, "验证码不存在或已过期"

    stored_data = verification_codes[email]
    current_time = time.time()

    # 检查验证码是否过期
    if current_time > stored_data['expires']:
        del verification_codes[email]  # 删除过期验证码
        return False, "验证码已过期"

    # 验证码是否匹配
    if stored_data['code'] != code:
        return False, "验证码错误"

    # 验证通过后删除验证码（一次性使用）
    del verification_codes[email]
    return True, "验证成功"


# 数据库初始化函数
def init_database():
    """初始化数据库，创建必要的表"""
    conn = get_db_connection()
    if not conn:
        print("无法连接到数据库，请检查数据库配置")
        return False

    try:
        with conn.cursor() as cursor:
            # 创建用户表，添加email字段
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    email VARCHAR(100) NOT NULL UNIQUE,
                    phone VARCHAR(20),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_login DATETIME
                )
            ''')

            # 创建用户设置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_settings (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    gender VARCHAR(10) DEFAULT '未指定',
                    name VARCHAR(50) DEFAULT '用户',
                    age VARCHAR(10) DEFAULT '未指定',
                    voice_speed VARCHAR(10) DEFAULT '中等',
                    voice_volume VARCHAR(10) DEFAULT '中等',
                    user_mode VARCHAR(10) DEFAULT '盲人端',
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

        conn.commit()
        print("数据库初始化成功")
        return True
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        return False
    finally:
        conn.close()


# 用户相关函数
def register_user(username, password, email, verification_code, phone=None):
    """注册新用户，增加验证码验证"""
    # 验证邮箱验证码
    code_valid, message = verify_code(email, verification_code)
    if not code_valid:
        return False, message

    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    try:
        # 密码加密
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with conn.cursor() as cursor:
            # 检查用户名是否已存在
            cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                return False, "用户名已存在"

            # 检查邮箱是否已存在
            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cursor.fetchone():
                return False, "该邮箱已被注册"

            # 插入新用户
            cursor.execute(
                "INSERT INTO users (username, password, email, phone) VALUES (%s, %s, %s, %s)",
                (username, password_hash, email, phone)
            )

            # 获取新用户ID
            user_id = cursor.lastrowid

            # 创建用户设置
            cursor.execute(
                "INSERT INTO user_settings (user_id) VALUES (%s)",
                (user_id,)
            )

        conn.commit()
        return True, "注册成功"
    except Exception as e:
        conn.rollback()
        print(f"注册用户失败: {e}")
        return False, f"注册失败: {str(e)}"
    finally:
        conn.close()


def verify_user(username, password):
    """验证用户登录"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败", None

    try:
        # 密码加密
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        with conn.cursor() as cursor:
            # 查询用户
            cursor.execute("SELECT id, username FROM users WHERE username = %s AND password = %s",
                           (username, password_hash))
            user = cursor.fetchone()

            if not user:
                return False, "用户名或密码错误", None

            # 更新最后登录时间
            cursor.execute("UPDATE users SET last_login = NOW() WHERE id = %s", (user['id'],))

            # 获取用户设置
            cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user['id'],))
            settings = cursor.fetchone()

            if not settings:
                # 如果没有设置，创建默认设置
                cursor.execute("INSERT INTO user_settings (user_id) VALUES (%s)", (user['id'],))
                cursor.execute("SELECT * FROM user_settings WHERE user_id = %s", (user['id'],))
                settings = cursor.fetchone()

        conn.commit()

        # 将设置转换为应用中使用的格式
        user_config = {
            "id": user['id'],
            "username": user['username'],
            "gender": settings['gender'],
            "name": settings['name'],
            "age": settings['age'],
            "voice_speed": settings['voice_speed'],
            "voice_volume": settings['voice_volume'],
            "user_mode": settings['user_mode']
        }

        return True, "登录成功", user_config
    except Exception as e:
        print(f"验证用户失败: {e}")
        return False, f"登录失败: {str(e)}", None
    finally:
        conn.close()


def update_user_settings_in_db(user_id, settings):
    """更新数据库中的用户设置"""
    conn = get_db_connection()
    if not conn:
        return False, "数据库连接失败"

    try:
        with conn.cursor() as cursor:
            # 更新用户设置
            cursor.execute("""
                UPDATE user_settings 
                SET gender = %s, name = %s, age = %s, 
                    voice_speed = %s, voice_volume = %s, user_mode = %s
                WHERE user_id = %s
                """,
                           (settings["gender"], settings["name"], settings["age"],
                            settings["voice_speed"], settings["voice_volume"], settings["user_mode"],
                            user_id)
                           )

        conn.commit()
        return True, "设置更新成功"
    except Exception as e:
        conn.rollback()
        print(f"更新用户设置失败: {e}")
        return False, f"设置更新失败: {str(e)}"
    finally:
        conn.close()


# 验证登录的装饰器
def login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# 路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    """用户登录页面"""
    error = None
    success = None

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not username or not password:
            error = "请输入用户名和密码"
        else:
            success_login, message, user_data = verify_user(username, password)
            if success_login:
                session['user_id'] = user_data['id']
                session['username'] = user_data['username']

                # 更新全局设置
                global user_settings
                user_settings = {
                    "gender": user_data['gender'],
                    "name": user_data['name'],
                    "age": user_data['age'],
                    "voice_speed": user_data['voice_speed'],
                    "voice_volume": user_data['voice_volume'],
                    "user_mode": user_data['user_mode']
                }

                return redirect(url_for('index'))
            else:
                error = message

    return render_template('login.html', error=error, success=success)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """用户注册页面"""
    error = None

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        email = request.form.get('email')
        verification_code = request.form.get('verification_code')
        phone = request.form.get('phone')

        if not username or not password or not email:
            error = "用户名、密码和邮箱不能为空"
        elif password != confirm_password:
            error = "两次输入的密码不一致"
        elif not verification_code:
            error = "请输入验证码"
        else:
            success, message = register_user(username, password, email, verification_code, phone)
            if success:
                return redirect(url_for('login', success="注册成功，请登录"))
            else:
                error = message

    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    # 获取当前用户信息
    user = {
        'id': session.get('user_id'),
        'username': session.get('username', '用户')
    }
    return render_template('index.html', settings=user_settings, current_user=user)


# 修改更新设置接口以支持数据库
@app.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    """更新用户设置"""
    global user_settings

    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "未接收到设置数据"}), 400

    # 更新设置
    for key in user_settings.keys():
        if key in data:
            user_settings[key] = data[key]

    # 保存设置
    try:
        user_id = session.get('user_id')
        # 只更新数据库，移除save_settings调用
        success, message = update_user_settings_in_db(user_id, user_settings)
        if not success:
            return jsonify({"status": "error", "message": message}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"保存设置失败: {str(e)}"}), 500

    return jsonify({
        "status": "success",
        "message": "设置已更新",
        "settings": user_settings
    })


# AI提示模板
def get_prompt_template():
    gender_term = ""
    age_term = ""

    if user_settings["gender"] == "男":
        gender_term = "先生"
    elif user_settings["gender"] == "女":
        gender_term = "女士"

    if user_settings["age"] == "老年":
        age_term = "年长的"
    elif user_settings["age"] == "青年":
        age_term = "年轻的"

    prompt = f'''
你是一个服务于盲人行走的语音导航小助手。
你的用户是{age_term}{user_settings["name"]}{gender_term}。
你通过告知盲人盲道的转向，注意一定要说清楚盲道转向方位（左？右？），确保盲人一直行走在盲道上，并适时给予一些关怀。
注意，盲人因为看不见路面情况，所以才需要你的语音行走提示。
你的语气要温柔且元气。
'''
    return prompt


right_turn_question = "请用亲切且简短的话语告知要往右拐，因为盲道是往右拐的"
left_turn_question = "请用亲切且简短的话语告知要往左拐，因为盲道是往左拐的"


def get_available_voices():
    global voices_cache
    if voices_cache is not None:
        return voices_cache

    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    available_voices = []

    for voice in voices:
        voice_info = {
            'id': voice.id,
            'name': voice.name,
            'gender': '女声' if 'female' in voice.id.lower() or 'Microsoft Huihui' in voice.name else '男声'
        }
        available_voices.append(voice_info)

    voices_cache = available_voices
    return available_voices


def speak(text):
    """每个线程中创建新的 pyttsx3 实例进行语音合成"""
    try:
        print(f"[语音] 开始合成语音: '{text}'")
        local_engine = pyttsx3.init()

        # 获取可用语音列表并打印
        voices = local_engine.getProperty('voices')
        print(f"[语音] 系统可用语音列表:")
        for i, voice in enumerate(voices):
            print(f"  语音{i + 1}: ID={voice.id}, 名称={voice.name}")

        # 优先查找中文语音
        found_chinese_voice = False
        selected_voice = None

        # 首先尝试找中文语音
        for voice in voices:
            voice_name = voice.name.lower()
            # 检查是否包含中文相关关键词
            if "chinese" in voice_name or "huihui" in voice_name or "china" in voice_name or "中文" in voice_name or "zhongwen" in voice_name:
                selected_voice = voice.id
                found_chinese_voice = True
                print(f"[语音] 找到中文语音: {voice.name}")
                break

        # 如果找不到中文语音，使用第一个可用的声音
        if not found_chinese_voice and len(voices) > 0:
            selected_voice = voices[0].id
            print(f"[语音] 未找到中文语音，使用第一个可用语音: {voices[0].name}")

        # 设置选定的声音
        if selected_voice:
            print(f"[语音] 最终使用语音ID: {selected_voice}")
            local_engine.setProperty('voice', selected_voice)
        else:
            print("[语音] 警告: 未找到可用语音")

        # 根据用户设置调整语音速度
        if user_settings["voice_speed"] == "慢":
            local_engine.setProperty('rate', 150)
        elif user_settings["voice_speed"] == "快":
            local_engine.setProperty('rate', 250)
        else:  # 中等
            local_engine.setProperty('rate', 200)

        # 设置音量 (新增功能)
        volume_mapping = {
            "低": 0.5,
            "中等": 0.8,
            "高": 1.0
        }
        volume = volume_mapping.get(user_settings["voice_volume"], 0.8)
        local_engine.setProperty('volume', volume)

        # 实际播放语音
        print(f"[语音] 播放文本: {text}")
        local_engine.say(text)

        print("[语音] 开始runAndWait()...")
        local_engine.runAndWait()
        print("[语音] 播放完成")
        return True
    except Exception as e:
        print(f"[语音] 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_frames():
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

        THRESHOLD_SLOPE = 0.41
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

            # 处理视频帧...（剩余代码不变）
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
            if len(centers) >= 2 and current_time - last_call_time >= call_interval:
                ys = np.array([c[1] for c in centers])
                xs = np.array([c[0] for c in centers])
                slope, intercept = np.polyfit(ys, xs, 1)

                print(f"[盲道检测] 斜率: {slope}, 拦截: {intercept}")

                if slope < -THRESHOLD_SLOPE:
                    # 斜率显著为负，提示左转
                    print("[盲道检测] 检测到左转")
                    response = ollama.chat(model="qwen2.5:3b", messages=[
                        {"role": "system", "content": get_prompt_template()},
                        {"role": "user", "content": left_turn_question}
                    ], stream=True)

                    answer_content = ""
                    for chunk in response:
                        content = chunk.get('message', {}).get('content', '')
                        if content:
                            answer_content += content

                    print(f"[盲道检测] 生成的左转提示: {answer_content}")

                    # 设置语音文本并播放
                    current_speech_text = answer_content
                    threading.Thread(target=speak, args=(answer_content,)).start()
                    last_call_time = current_time
                    print(f"[盲道检测] 启动左转语音提示")

                elif slope > THRESHOLD_SLOPE:
                    # 斜率显著为正，提示右转
                    print("[盲道检测] 检测到右转")
                    response = ollama.chat(model="qwen2.5:3b", messages=[
                        {"role": "system", "content": get_prompt_template()},
                        {"role": "user", "content": right_turn_question}
                    ], stream=True)

                    answer_content = ""
                    for chunk in response:
                        content = chunk.get('message', {}).get('content', '')
                        if content:
                            answer_content += content

                    print(f"[盲道检测] 生成的右转提示: {answer_content}")

                    # 设置语音文本并播放
                    current_speech_text = answer_content
                    threading.Thread(target=speak, args=(answer_content,)).start()
                    last_call_time = current_time
                    print(f"[盲道检测] 启动右转语音提示")

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


def create_error_frame(message):
    """创建错误信息帧 - 使用PIL支持中文"""
    img = Image.new('RGB', (640, 480), color=(0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("simhei.ttf", 30)
    except IOError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), message, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((640 - text_width) // 2, (480 - text_height) // 2)

    draw.text(position, message, font=font, fill=(255, 0, 0))

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def create_info_frame(message):
    """创建信息提示帧 - 使用PIL支持中文"""
    img = Image.new('RGB', (640, 480), color=(41, 128, 185))
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("simhei.ttf", 30)
    except IOError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), message, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    position = ((640 - text_width) // 2, (480 - text_height) // 2)

    draw.text(position, message, font=font, fill=(255, 255, 255))

    try:
        small_font = ImageFont.truetype("simhei.ttf", 20)
    except IOError:
        small_font = ImageFont.load_default()

    help_text = "支持mp4, avi, mov, mkv, webm格式"
    bbox = draw.textbbox((0, 0), help_text, font=small_font)
    help_width = bbox[2] - bbox[0]
    help_height = bbox[3] - bbox[1]
    help_position = ((640 - help_width) // 2, position[1] + text_height + 20)
    draw.text(help_position, help_text, font=small_font, fill=(200, 200, 200))

    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


@app.route('/stream_speech_text')
def stream_speech_text():
    def generate():
        global current_speech_text
        last_sent = ""

        # 设置初始默认消息
        if not current_speech_text:
            current_speech_text = "提示：系统会实时分析盲道方向，当方向发生变化时会自动播报语音提示。"

        while True:
            if current_speech_text != last_sent:
                last_sent = current_speech_text
                # 不要添加data:前缀，保持原始格式
                yield f"{current_speech_text}\n\n"
            time.sleep(0.5)

    return Response(generate(), mimetype='text/event-stream')


@app.route('/send_message', methods=['POST'])
def send_message():
    """接收来自前端的家属消息，添加前缀后调用语音播报"""
    # 检查是否为盲人端模式，如果是则拒绝发送消息
    if user_settings["user_mode"] == "盲人端":
        return jsonify({"status": "error", "message": "盲人端模式不能发送消息"}), 403

    data = request.get_json()
    message = data.get('message', '').strip()

    if not message:
        return jsonify({"status": "error", "message": "消息为空"}), 400

    try:
        full_text = f"您有一条来自家属的消息：{message}"
        print(f"[消息] 收到家属消息: {message}")

        global current_speech_text
        current_speech_text = full_text

        # 使用和旧版本一样的方式启动语音线程
        threading.Thread(target=speak, args=(full_text,)).start()
        print(f"[消息] 启动语音播报")

        return jsonify({"status": "success", "message": "消息发送成功"})
    except Exception as e:
        print(f"[消息] 发送消息出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"发送失败: {str(e)}"}), 500


@app.route('/upload_video', methods=['POST'])
def upload_video():
    """处理视频上传"""
    global current_video_path, video_active

    if 'video' not in request.files:
        return jsonify({"status": "error", "message": "没有上传文件"}), 400

    file = request.files['video']

    if file.filename == '':
        return jsonify({"status": "error", "message": "未选择文件"}), 400

    if not allowed_file(file.filename):
        return jsonify(
            {"status": "error", "message": f"不支持的文件类型，允许的类型: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    try:
        # 创建上传目录（如果不存在）
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

        # 使用时间戳生成唯一文件名，避免文件名冲突
        timestamp = int(time.time())
        filename = f"{timestamp}_{secure_filename(file.filename)}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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


@app.route('/get_settings', methods=['GET'])
def get_settings():
    """获取当前用户设置"""
    return jsonify({
        "status": "success",
        "settings": user_settings
    })


@app.route('/get_available_voices', methods=['GET'])
def get_available_voices():
    """获取系统可用的语音列表"""
    try:
        voices = get_available_voices()

        return jsonify({
            "status": "success",
            "voices": voices
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"获取语音列表失败: {str(e)}"
        }), 500


@app.route('/test_voice', methods=['POST'])
def voice_test():
    """测试语音设置，使用和旧版本相同的线程方式"""
    try:
        data = request.get_json()
        print(f"[测试语音] 收到请求数据: {data}")

        test_settings = {
            "voice_speed": data.get("voice_speed", user_settings["voice_speed"]),
            "voice_volume": data.get("voice_volume", user_settings["voice_volume"])
        }

        # 临时保存当前设置
        temp_settings = {
            "voice_speed": user_settings["voice_speed"],
            "voice_volume": user_settings["voice_volume"]
        }

        print(f"[测试语音] 当前设置: {temp_settings}")
        print(f"[测试语音] 测试设置: {test_settings}")

        # 应用测试设置
        user_settings.update(test_settings)

        # 启动新线程来播放测试语音 - 使用和旧版本一样的方式
        test_text = "这是一条测试语音，用于测试当前语音设置效果。"
        threading.Thread(target=speak, args=(test_text,)).start()

        # 恢复原始设置 - 等待一小段时间后恢复，确保语音播放使用测试设置
        def restore_settings():
            time.sleep(2)  # 等待2秒，确保语音播放已经开始
            user_settings.update(temp_settings)
            print("[测试语音] 已恢复原始设置")

        # 在单独线程中恢复设置，确保响应可以立即返回
        threading.Thread(target=restore_settings).start()

        print("[测试语音] 已启动语音测试")
        return jsonify({"status": "success", "message": "语音测试已开始"})
    except Exception as e:
        print(f"[测试语音] 错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"语音测试失败: {str(e)}"})


@app.route('/send_verification_code', methods=['POST'])
def send_code():
    """发送邮箱验证码"""
    email = request.form.get('email')
    purpose = request.form.get('purpose', 'register')  # 可以是'register'或'reset_password'

    if not email:
        return jsonify({"status": "error", "message": "邮箱不能为空"}), 400

    if not is_valid_email(email):
        return jsonify({"status": "error", "message": "邮箱格式不正确"}), 400

    # 如果是注册目的，检查邮箱是否已被注册
    if purpose == 'register':
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                    if cursor.fetchone():
                        return jsonify({"status": "error", "message": "该邮箱已被注册"}), 400
            finally:
                conn.close()

    # 生成验证码并发送邮件
    verification_code = generate_verification_code()
    success, message = send_verification_email(email, verification_code)

    if success:
        return jsonify({"status": "success", "message": "验证码已发送，请查收邮件"})
    else:
        return jsonify({"status": "error", "message": message}), 500


# 添加忘记密码功能
@app.route('/forget_password', methods=['GET', 'POST'])
def forget_password():
    """忘记密码页面"""
    error = None
    success = None

    if request.method == 'POST':
        email = request.form.get('email')
        verification_code = request.form.get('verification_code')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not email or not verification_code or not new_password:
            error = "所有字段都不能为空"
        elif new_password != confirm_password:
            error = "两次输入的密码不一致"
        else:
            # 验证邮箱验证码
            code_valid, message = verify_code(email, verification_code)
            if not code_valid:
                error = message
            else:
                # 更新密码
                conn = get_db_connection()
                if not conn:
                    error = "数据库连接失败"
                else:
                    try:
                        password_hash = hashlib.sha256(new_password.encode()).hexdigest()
                        with conn.cursor() as cursor:
                            # 查询用户是否存在
                            cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
                            user = cursor.fetchone()

                            if not user:
                                error = "该邮箱未注册"
                            else:
                                # 更新密码
                                cursor.execute(
                                    "UPDATE users SET password = %s WHERE email = %s",
                                    (password_hash, email)
                                )
                                conn.commit()
                                success = "密码重置成功，请登录"
                    except Exception as e:
                        conn.rollback()
                        error = f"密码重置失败: {str(e)}"
                    finally:
                        conn.close()

    return render_template('forget_password.html', error=error, success=success)


# 新增地图相关路由
@app.route('/update_location', methods=['POST'])
@login_required
def update_location():
    """更新用户位置"""
    user_id = session.get('user_id')
    data = request.get_json()
    
    if not data or 'lat' not in data or 'lng' not in data:
        return jsonify({"status": "error", "message": "位置数据不完整"}), 400
    
    # 更新用户位置
    user_locations[user_id] = {
        'lat': data['lat'],
        'lng': data['lng'],
        'timestamp': time.time()
    }
    
    return jsonify({
        "status": "success",
        "message": "位置已更新"
    })

@app.route('/get_location/<int:user_id>', methods=['GET'])
@login_required
def get_location(user_id):
    """获取指定用户的位置"""
    # 检查权限（只允许查看自己或关联的家属/被照顾者的位置）
    current_user_id = session.get('user_id')
    
    # 这里应该有更完善的权限检查逻辑，例如家属关系验证
    # 暂时简化为允许查看所有用户位置
    
    if user_id in user_locations:
        # 检查位置数据是否过期（例如5分钟）
        if time.time() - user_locations[user_id]['timestamp'] > 300:
            return jsonify({
                "status": "warning",
                "message": "位置数据已过期",
                "location": user_locations[user_id]
            })
        
        return jsonify({
            "status": "success",
            "location": user_locations[user_id]
        })
    else:
        return jsonify({
            "status": "error", 
            "message": "未找到用户位置数据"
        }), 404

@app.route('/nearby_blindways', methods=['GET'])
@login_required
def nearby_blindways():
    """获取附近的盲道数据（示例数据）"""
    # 在实际应用中，这里应该连接到盲道数据库或API
    # 现在返回示例数据用于演示
    
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    
    if not lat or not lng:
        return jsonify({"status": "error", "message": "请提供位置参数"}), 400
    
    # 示例盲道数据（在实际应用中应从数据库获取）
    sample_blindways = [
        {
            'id': 1,
            'name': '中心广场盲道',
            'points': [
                {'lat': lat + 0.001, 'lng': lng + 0.001},
                {'lat': lat + 0.002, 'lng': lng + 0.001},
                {'lat': lat + 0.002, 'lng': lng - 0.001}
            ]
        },
        {
            'id': 2,
            'name': '南街盲道',
            'points': [
                {'lat': lat - 0.0005, 'lng': lng - 0.0005},
                {'lat': lat - 0.001, 'lng': lng - 0.001},
                {'lat': lat - 0.002, 'lng': lng - 0.001}
            ]
        }
    ]
    
    # 计算每条盲道到用户的距离
    user_coord = (lat, lng)
    for blindway in sample_blindways:
        min_distance = float('inf')
        for point in blindway['points']:
            point_coord = (point['lat'], point['lng'])
            distance = geopy.distance.distance(user_coord, point_coord).meters
            min_distance = min(min_distance, distance)
        
        blindway['distance'] = round(min_distance, 1)  # 四舍五入到小数点后1位
    
    # 按距离排序
    sample_blindways.sort(key=lambda x: x['distance'])
    
    return jsonify({
        "status": "success",
        "blindways": sample_blindways
    })


if __name__ == '__main__':
    # 初始化数据库
    init_database()
    app.run(debug=True)

