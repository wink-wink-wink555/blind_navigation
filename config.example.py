"""
配置文件示例 - 请复制此文件为 config.py 并填入您的实际配置
"""

# Flask应用配置
SECRET_KEY = 'your_secret_key_here'  # 请更改为随机字符串，用于session加密

# 数据库配置
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'your_mysql_password',  # 填写您的MySQL密码
    'db': 'blind_navigation',
    'charset': 'utf8mb4',
}

# 邮件发送配置
EMAIL_CONFIG = {
    'sender': 'your_email@qq.com',  # 填写您的QQ邮箱
    'password': 'your_smtp_auth_code',  # 填写QQ邮箱授权码（不是QQ密码）
    'smtp_server': 'smtp.qq.com',
    'smtp_port': 465
}

# 文件上传配置
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
MAX_CONTENT_LENGTH = 300 * 1024 * 1024  # 限制上传大小为300MB

# YOLO模型配置
MODEL_WEIGHTS = 'yolo/best.pt'  # 使用项目包含的预训练YOLOv8盲道检测模型

# 百度地图MCP配置
BAIDU_MAP_CONFIG = {
    'api_key': 'your_baidu_map_api_key',  # 填写您的百度地图API密钥
    'base_url': 'https://api.map.baidu.com',
    'web_service_url': 'https://api.map.baidu.com/geocoding/v3/',
    'direction_url': 'https://api.map.baidu.com/direction/v2/',
    'place_search_url': 'https://api.map.baidu.com/place/v2/search'
}

# DeepSeek AI配置
DEEPSEEK_CONFIG = {
    'api_key': 'your_deepseek_api_key',  # 填写您的DeepSeek API密钥
    'base_url': 'https://api.deepseek.com/chat/completions',
    'model': 'deepseek-chat'
}

# 阿里云百炼（DashScope）语音识别配置
DASHSCOPE_CONFIG = {
    'api_key': 'your_dashscope_api_key',  # 填写您的阿里云百炼API密钥
    'stt_model': 'paraformer-realtime-v2',  # 语音识别模型
}

# 视频检测配置
THRESHOLD_SLOPE = 0.41  # 盲道方向检测斜率阈值
CALL_INTERVAL = 14  # 语音提示间隔（秒）

# 用户默认设置
DEFAULT_USER_SETTINGS = {
    "gender": "未指定",  # 性别：男/女/未指定
    "name": "用户",  # 用户名称
    "age": "未指定",  # 年龄段：青年/中年/老年/未指定
    "voice_speed": "中等",  # 语音速度：慢/中等/快
    "voice_volume": "中等",  # 语音音量：低/中等/高
    "user_mode": "盲人端",  # 用户模式：盲人端/家属端
    "encourage": "开"  # 适当时给予鼓励：开/关
}

