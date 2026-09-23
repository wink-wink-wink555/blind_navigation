"""
主要路由 - 首页、设置、用户信息等
"""
from flask import Blueprint, render_template, request, session, jsonify
from utils.decorators import login_required
from services.guidance_bus import guidance_bus
from utils.email_utils import is_valid_email
from models.database import (update_user_settings_in_db, get_user_details,
                              get_user_settings, get_family_contacts,
                              add_family_contact, delete_family_contact,
                              resolve_caregiver_recipient)
from config import DEFAULT_USER_SETTINGS, BAIDU_MAP_CONFIG

main_bp = Blueprint('main', __name__)

def get_current_user_settings():
    """Return settings only from the current user's session."""
    return dict(session.get('user_settings') or DEFAULT_USER_SETTINGS)


def update_current_user_settings(new_settings):
    """Update this browser session without crossing into another account."""
    session['user_settings'] = {**DEFAULT_USER_SETTINGS, **new_settings}


@main_bp.route('/')
@login_required
def index():
    """首页"""
    # 获取当前用户信息
    user = {
        'id': session.get('user_id'),
        'username': session.get('username', '用户')
    }
    
    # Each request resolves its own user's settings.
    user_id = session.get('user_id')
    if user_id:
        user_settings_data, message = get_user_settings(user_id)
        if user_settings_data:
            update_current_user_settings(user_settings_data)
            print(f"[首页] 已从数据库加载用户设置: {user_settings_data}")
    
    settings = get_current_user_settings()
    return render_template('index.html', settings=settings, current_user=user,
                           baidu_map_browser_ak=BAIDU_MAP_CONFIG.get('browser_api_key', ''))


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
@login_required
def get_settings():
    """获取当前用户设置"""
    settings = get_current_user_settings()
    return jsonify({
        "status": "success",
        "settings": settings
    })


@main_bp.route('/get_available_voices', methods=['GET'])
def get_voices():
    """Browser speech voices are local to the client, not the Flask host."""
    return jsonify({"status": "success", "voices": [], "source": "browser"})


@main_bp.route('/test_voice', methods=['POST'])
@login_required
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

        guidance_bus.publish(session['user_id'], "speech", str(test_text)[:180],
                             priority="BACKGROUND", ttl_ms=10000,
                             dedupe_key="voice_test")
        return jsonify({"status": "success", "message": "语音测试已提交至当前浏览器"})
    except Exception as e:
        print(f"[测试语音] 错误: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"语音测试失败: {str(e)}"})


@main_bp.route('/send_message', methods=['POST'])
@login_required
def send_message():
    """Send to a specifically authorized recipient's browser event stream."""
    data = request.get_json(silent=True) or {}
    message = str(data.get('message') or '').strip()
    recipient_name = str(data.get('recipient_username') or '').strip()
    if not message or len(message) > 200 or not recipient_name:
        return jsonify({"status": "error", "message": "填写接收者用户名及1至200字消息"}), 400
    user_id = session['user_id']
    # Read stored account settings; a client-side mode switch is not proof of a link.
    settings, _ = get_user_settings(user_id)
    if not settings or settings.get('user_mode') != '家属端':
        return jsonify({"status": "error", "message": "仅家属账号可以发送"}), 403
    recipient_id = resolve_caregiver_recipient(user_id, recipient_name)
    if not recipient_id:
        return jsonify({"status": "error", "message": "接收者未登记您账号的邮箱"}), 403
    event = guidance_bus.publish(recipient_id, "speech", f"家属消息：{message}",
                                 priority="FAMILY", ttl_ms=300000,
                                 resume_policy="continue", sender_id=user_id)
    return jsonify({"status": "success", "message": "消息已入接收者队列；请通过状态查询确认是否播放",
                    "event_id": event['event_id']})


@main_bp.route('/family_message_status/<event_id>')
@login_required
def family_message_status(event_id):
    status = guidance_bus.status(session['user_id'], event_id)
    if status is None:
        return jsonify({"status": "error", "message": "消息不存在或无权限查看"}), 404
    return jsonify({"status": "success", "delivery_status": status})


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

