"""
认证相关路由 - 登录、注册、登出、忘记密码
"""
from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from models.database import register_user, verify_user, get_db_connection, update_password
from utils.email_utils import (
    generate_verification_code, 
    is_valid_email, 
    send_verification_email,
    verify_code
)
import hashlib

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
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

                # 将用户设置保存到session中
                user_settings_data = {
                    "gender": user_data['gender'],
                    "name": user_data['name'],
                    "age": user_data['age'],
                    "voice_speed": user_data['voice_speed'],
                    "voice_volume": user_data['voice_volume'],
                    "user_mode": user_data['user_mode'],
                    "encourage": user_data['encourage']
                }
                session['user_settings'] = user_settings_data
                
                # 同时更新全局 user_settings（供视频流等非请求上下文使用）
                from routes.main import update_current_user_settings, set_current_active_user_id
                update_current_user_settings(user_settings_data)
                set_current_active_user_id(user_data['id'])

                return redirect(url_for('main.index'))
            else:
                error = message

    return render_template('login.html', error=error, success=success)


@auth_bp.route('/register', methods=['GET', 'POST'])
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
                return redirect(url_for('auth.login', success="注册成功，请登录"))
            else:
                error = message

    return render_template('register.html', error=error)


@auth_bp.route('/logout')
def logout():
    """用户登出"""
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/forget_password', methods=['GET', 'POST'])
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
                success_update, message = update_password(email, new_password)
                if success_update:
                    success = "密码重置成功，请登录"
                else:
                    error = message

    return render_template('forget_password.html', error=error, success=success)


@auth_bp.route('/send_verification_code', methods=['POST'])
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

