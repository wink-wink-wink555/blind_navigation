"""
邮件和验证码工具模块
"""
import random
import string
import smtplib
import time
import re
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
from config import EMAIL_CONFIG

# 验证码存储
verification_codes = {}  # 格式: {email: {'code': '123456', 'expires': timestamp}}


def generate_verification_code(length=6):
    """生成指定长度的数字验证码"""
    return ''.join(random.choices(string.digits, k=length))


def is_valid_email(email):
    """简单验证邮箱格式"""
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


FAMILY_EMAIL_TEMPLATES = {
    'greeting': {
        'subject': '【盲道导航】来自{sender_name}的问候',
        'html': '''
        <html>
        <head><meta charset="utf-8"></head>
        <body style="margin:0; padding:0; background:#f4f7fa; font-family:'PingFang SC','Helvetica Neue',Arial,sans-serif;">
            <div style="max-width:520px; margin:30px auto; background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 4px 24px rgba(0,0,0,0.08);">
                <div style="background:linear-gradient(135deg,#43e97b 0%,#38f9d7 100%); padding:28px 32px;">
                    <h1 style="margin:0; color:#fff; font-size:22px;">💚 来自{sender_name}的问候</h1>
                    <p style="margin:6px 0 0; color:rgba(255,255,255,0.9); font-size:14px;">通过盲道导航助手发送</p>
                </div>
                <div style="padding:28px 32px;">
                    <div style="background:#f0fdf4; border-left:4px solid #22c55e; padding:16px 20px; border-radius:0 10px 10px 0; margin-bottom:20px;">
                        <p style="margin:0; font-size:16px; color:#333; line-height:1.8;">{message_content}</p>
                    </div>
                    <p style="font-size:13px; color:#999; margin:16px 0 0; text-align:center;">此消息由「盲道导航助手」AI助手代为发送</p>
                </div>
            </div>
        </body>
        </html>'''
    },
    'help': {
        'subject': '【盲道导航·紧急】{sender_name}发来了一条消息',
        'html': '''
        <html>
        <head><meta charset="utf-8"></head>
        <body style="margin:0; padding:0; background:#f4f7fa; font-family:'PingFang SC','Helvetica Neue',Arial,sans-serif;">
            <div style="max-width:520px; margin:30px auto; background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 4px 24px rgba(0,0,0,0.08);">
                <div style="background:linear-gradient(135deg,#f5576c 0%,#ff6b6b 100%); padding:28px 32px;">
                    <h1 style="margin:0; color:#fff; font-size:22px;">🚨 {sender_name}发来了一条消息</h1>
                    <p style="margin:6px 0 0; color:rgba(255,255,255,0.9); font-size:14px;">请尽快查看</p>
                </div>
                <div style="padding:28px 32px;">
                    <div style="background:#fef2f2; border-left:4px solid #ef4444; padding:16px 20px; border-radius:0 10px 10px 0; margin-bottom:20px;">
                        <p style="margin:0; font-size:16px; color:#333; line-height:1.8; font-weight:500;">{message_content}</p>
                    </div>
                    <p style="font-size:14px; color:#e74c3c; text-align:center; font-weight:500;">请及时回复或联系{sender_name}</p>
                    <p style="font-size:13px; color:#999; margin:16px 0 0; text-align:center;">此消息由「盲道导航助手」AI助手代为发送</p>
                </div>
            </div>
        </body>
        </html>'''
    },
    'location': {
        'subject': '【盲道导航】{sender_name}分享了位置信息',
        'html': '''
        <html>
        <head><meta charset="utf-8"></head>
        <body style="margin:0; padding:0; background:#f4f7fa; font-family:'PingFang SC','Helvetica Neue',Arial,sans-serif;">
            <div style="max-width:520px; margin:30px auto; background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 4px 24px rgba(0,0,0,0.08);">
                <div style="background:linear-gradient(135deg,#4facfe 0%,#00f2fe 100%); padding:28px 32px;">
                    <h1 style="margin:0; color:#fff; font-size:22px;">📍 {sender_name}的位置动态</h1>
                    <p style="margin:6px 0 0; color:rgba(255,255,255,0.9); font-size:14px;">通过盲道导航助手发送</p>
                </div>
                <div style="padding:28px 32px;">
                    <div style="background:#eff6ff; border-left:4px solid #3b82f6; padding:16px 20px; border-radius:0 10px 10px 0; margin-bottom:20px;">
                        <p style="margin:0; font-size:16px; color:#333; line-height:1.8;">{message_content}</p>
                    </div>
                    <p style="font-size:13px; color:#999; margin:16px 0 0; text-align:center;">此消息由「盲道导航助手」AI助手代为发送</p>
                </div>
            </div>
        </body>
        </html>'''
    },
    'general': {
        'subject': '【盲道导航】{sender_name}给您发了一条消息',
        'html': '''
        <html>
        <head><meta charset="utf-8"></head>
        <body style="margin:0; padding:0; background:#f4f7fa; font-family:'PingFang SC','Helvetica Neue',Arial,sans-serif;">
            <div style="max-width:520px; margin:30px auto; background:#fff; border-radius:16px; overflow:hidden; box-shadow:0 4px 24px rgba(0,0,0,0.08);">
                <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); padding:28px 32px;">
                    <h1 style="margin:0; color:#fff; font-size:22px;">✉️ 来自{sender_name}的消息</h1>
                    <p style="margin:6px 0 0; color:rgba(255,255,255,0.9); font-size:14px;">通过盲道导航助手发送</p>
                </div>
                <div style="padding:28px 32px;">
                    <div style="background:#f5f3ff; border-left:4px solid #7c3aed; padding:16px 20px; border-radius:0 10px 10px 0; margin-bottom:20px;">
                        <p style="margin:0; font-size:16px; color:#333; line-height:1.8;">{message_content}</p>
                    </div>
                    <p style="font-size:13px; color:#999; margin:16px 0 0; text-align:center;">此消息由「盲道导航助手」AI助手代为发送</p>
                </div>
            </div>
        </body>
        </html>'''
    }
}


def classify_message_template(message_content):
    """根据消息内容自动选择邮件模板类型"""
    help_keywords = ['帮忙', '帮助', '救', '急', '摔', '迷路', '找不到', '危险', '受伤', '紧急', '不舒服', 'SOS']
    location_keywords = ['到了', '在这', '到达', '位置', '地点', '这里是', '我在', '出发', '回来了', '到家']
    greeting_keywords = ['想你', '挂念', '放心', '安好', '平安', '好的', '没事', '很好', '吃饭', '晚安', '早安', '想念', '爱你']

    lower_msg = message_content.lower()
    for kw in help_keywords:
        if kw in lower_msg:
            return 'help'
    for kw in location_keywords:
        if kw in lower_msg:
            return 'location'
    for kw in greeting_keywords:
        if kw in lower_msg:
            return 'greeting'
    return 'general'


def send_family_email(to_email, sender_name, message_content, template_type=None):
    """发送家属邮件，使用预设HTML模板"""
    try:
        if not template_type:
            template_type = classify_message_template(message_content)

        template = FAMILY_EMAIL_TEMPLATES.get(template_type, FAMILY_EMAIL_TEMPLATES['general'])

        subject = template['subject'].format(sender_name=sender_name)
        html_content = template['html'].format(
            sender_name=sender_name,
            message_content=message_content
        )

        message = MIMEText(html_content, 'html', 'utf-8')
        message['From'] = formataddr(("盲道导航助手", EMAIL_CONFIG['sender']))
        message['To'] = Header(to_email)
        message['Subject'] = Header(subject, 'utf-8')

        server = smtplib.SMTP_SSL(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
        server.sendmail(EMAIL_CONFIG['sender'], [to_email], message.as_string())
        server.quit()

        print(f"[邮件] 成功发送给 {to_email}，模板={template_type}")
        return True, "邮件发送成功"
    except Exception as e:
        print(f"[邮件] 发送失败: {e}")
        return False, f"邮件发送失败: {str(e)}"


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

