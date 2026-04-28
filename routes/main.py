"""
主要路由 - 首页、设置、用户信息等
"""
from flask import Blueprint, render_template, request, session, jsonify
from utils.decorators import login_required
from utils.voice_utils import get_available_voices, speak
from utils.email_utils import is_valid_email
from models.database import (update_user_settings_in_db, get_user_details,
                              get_user_settings, get_family_contacts,
                              add_family_contact, delete_family_contact)
from config import DEFAULT_USER_SETTINGS
import threading
import time

main_bp = Blueprint('main', __name__)

# 默认提示文字
DEFAULT_SPEECH_TEXT = "提示：系统会实时分析盲道方向，当方向发生变化时会自动播报语音提示。"

# 全局用户设置
user_settings = DEFAULT_USER_SETTINGS.copy()


def get_current_user_settings():
    """获取当前用户设置（从session或全局变量）"""
    if 'user_settings' in session:
        return session['user_settings']
    return user_settings


def update_current_user_settings(new_settings):
    """更新当前用户设置"""
    global user_settings
    # 首先更新全局变量
    user_settings.update(new_settings)
    # 如果在请求上下文中，也更新 session
    try:
        if 'user_settings' in session:
            session['user_settings'].update(new_settings)
            session.modified = True
    except RuntimeError:
        # 不在请求上下文中，忽略
        pass


@main_bp.route('/')
@login_required
def index():
    """首页"""
    # 获取当前用户信息
    user = {
        'id': session.get('user_id'),
        'username': session.get('username', '用户')
    }
    
    # 每次访问首页时，从数据库重新加载用户设置到全局变量
    # 这样可以确保视频流等非请求上下文也能使用最新的设置
    user_id = session.get('user_id')
    if user_id:
        user_settings_data, message = get_user_settings(user_id)
        if user_settings_data:
            # 更新 session 和全局变量
            session['user_settings'] = user_settings_data
            update_current_user_settings(user_settings_data)
            print(f"[首页] 已从数据库加载用户设置: {user_settings_data}")
    
    settings = get_current_user_settings()
    return render_template('index.html', settings=settings, current_user=user)


@main_bp.route('/update_settings', methods=['POST'])
@login_required
def update_settings():
    """更新用户设置"""
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "未接收到设置数据"}), 400

    # 获取当前设置
    current_settings = get_current_user_settings()
    
    # 更新设置
    for key in current_settings.keys():
        if key in data:
            current_settings[key] = data[key]

    # 更新到session和全局变量
    update_current_user_settings(current_settings)

    # 保存到数据库
    try:
        user_id = session.get('user_id')
        success, message = update_user_settings_in_db(user_id, current_settings)
        if not success:
            return jsonify({"status": "error", "message": message}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"保存设置失败: {str(e)}"}), 500

    return jsonify({
        "status": "success",
        "message": "设置已更新",
        "settings": current_settings
    })


@main_bp.route('/get_settings', methods=['GET'])
def get_settings():
    """获取当前用户设置"""
    settings = get_current_user_settings()
    return jsonify({
        "status": "success",
        "settings": settings
    })


@main_bp.route('/get_available_voices', methods=['GET'])
def get_voices():
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


@main_bp.route('/test_voice', methods=['POST'])
def voice_test():
    """测试语音设置"""
    try:
        data = request.get_json()
        print(f"[测试语音] 收到请求数据: {data}")

        # 获取当前设置
        current_settings = get_current_user_settings()
        
        # 构建测试用的设置（不修改全局设置）
        test_settings = {
            "voice_speed": data.get("voice_speed", current_settings["voice_speed"]),
            "voice_volume": data.get("voice_volume", current_settings["voice_volume"])
        }

        print(f"[测试语音] 当前设置: voice_speed={current_settings['voice_speed']}, voice_volume={current_settings['voice_volume']}")
        print(f"[测试语音] 测试设置: voice_speed={test_settings['voice_speed']}, voice_volume={test_settings['voice_volume']}")

        # 获取自定义测试文本
        test_text = data.get("test_text")

        if not test_text:
            # 如果前端没有发送测试文本，生成默认文本
            encourage_status = "开启" if current_settings.get("encourage") == "开" else "关闭"
            test_text = f"这是一条测试语音，用于测试当前语音设置效果。您已{encourage_status}鼓励功能。"

        print(f"[测试语音] 将播放文本: {test_text}")

        # 直接使用 speak 函数，它内部已经有队列机制
        # 不需要额外的线程包装
        speak(test_text, test_settings)

        print("[测试语音] 已添加到语音队列")
        return jsonify({"status": "success", "message": "语音测试已开始"})
    except Exception as e:
        print(f"[测试语音] 错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"语音测试失败: {str(e)}"})


@main_bp.route('/send_message', methods=['POST'])
def send_message():
    """接收来自前端的家属消息，添加前缀后调用语音播报"""
    current_settings = get_current_user_settings()
    
    # 检查是否为盲人端模式，如果是则拒绝发送消息
    if current_settings["user_mode"] == "盲人端":
        return jsonify({"status": "error", "message": "盲人端模式不能发送消息"}), 403

    data = request.get_json()
    message = data.get('message', '').strip()

    if not message:
        return jsonify({"status": "error", "message": "消息为空"}), 400

    try:
        full_text = f"您有一条来自家属的消息：{message}"
        print(f"[消息] 收到家属消息: {message}")

        # 更新页面显示的文字为家属消息
        from routes.video import current_speech_text
        import routes.video as video_module
        video_module.current_speech_text = full_text
        print(f"[消息] 已更新页面显示文字")

        # 直接调用 speak 函数，它内部已经有队列机制
        speak(full_text, current_settings)
        print(f"[消息] 已添加到语音队列")

        # 根据文字长度估算播放时间（每个字约0.3秒，加上前缀）
        # 考虑语速设置
        speed_multiplier = {
            "慢": 1.5,
            "中等": 1.0,
            "快": 0.7
        }
        base_duration = len(full_text) * 0.3
        duration = base_duration * speed_multiplier.get(current_settings.get("voice_speed", "中等"), 1.0)
        # 增加2秒的缓冲时间
        duration += 2.0
        
        print(f"[消息] 预计播放时长: {duration:.1f}秒")

        # 定时恢复默认文字
        def restore_default_text():
            time.sleep(duration)
            video_module.current_speech_text = DEFAULT_SPEECH_TEXT
            print(f"[消息] 已恢复默认提示文字")
        
        threading.Thread(target=restore_default_text, daemon=True).start()

        return jsonify({"status": "success", "message": "消息发送成功"})
    except Exception as e:
        print(f"[消息] 发送消息出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"发送失败: {str(e)}"}), 500


@main_bp.route('/family_contacts', methods=['GET'])
@login_required
def list_family_contacts():
    """获取当前用户的家属联系人列表"""
    user_id = session.get('user_id')
    contacts, msg = get_family_contacts(user_id)
    return jsonify({"status": "success", "contacts": contacts})


@main_bp.route('/family_contacts', methods=['POST'])
@login_required
def create_family_contact():
    """添加家属联系人"""
    user_id = session.get('user_id')
    data = request.get_json()
    if not data:
        return jsonify({"status": "error", "message": "请求数据为空"}), 400

    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip()

    if not name or not email:
        return jsonify({"status": "error", "message": "称呼和邮箱不能为空"}), 400

    if len(name) > 50:
        return jsonify({"status": "error", "message": "称呼不能超过50个字符"}), 400

    if not is_valid_email(email):
        return jsonify({"status": "error", "message": "邮箱格式不正确"}), 400

    success, msg = add_family_contact(user_id, name, email)
    if success:
        contacts, _ = get_family_contacts(user_id)
        return jsonify({"status": "success", "message": msg, "contacts": contacts})
    return jsonify({"status": "error", "message": msg}), 400


@main_bp.route('/family_contacts/<int:contact_id>', methods=['DELETE'])
@login_required
def remove_family_contact(contact_id):
    """删除家属联系人"""
    user_id = session.get('user_id')
    success, msg = delete_family_contact(user_id, contact_id)
    if success:
        contacts, _ = get_family_contacts(user_id)
        return jsonify({"status": "success", "message": msg, "contacts": contacts})
    return jsonify({"status": "error", "message": msg}), 400


@main_bp.route('/get_user_details', methods=['GET'])
@login_required
def get_user_info():
    """获取当前用户的详细信息"""
    user_id = session.get('user_id')
    user_info, message = get_user_details(user_id)
    
    if user_info:
        return jsonify({
            "status": "success",
            "user_info": user_info
        })
    else:
        return jsonify({"status": "error", "message": message}), 500

