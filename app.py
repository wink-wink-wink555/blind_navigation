"""
Flask 应用主文件 - 精简版
负责应用初始化和路由注册
"""
from flask import Flask
import os

# 导入配置
from config import SECRET_KEY, UPLOAD_FOLDER, MAX_CONTENT_LENGTH

# 导入蓝图
from routes.auth import auth_bp
from routes.main import main_bp
from routes.video import video_bp
from routes.map import map_bp
from routes.chat import chat_bp

# 导入数据库初始化函数
from models.database import init_database


def create_app():
    """创建并配置Flask应用"""
    app = Flask(__name__)
    
    # 应用配置
    app.secret_key = SECRET_KEY
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    
    # 确保上传目录存在
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # 注册蓝图
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(video_bp)
    app.register_blueprint(map_bp)
    app.register_blueprint(chat_bp)
    
    return app


if __name__ == '__main__':
    # 初始化数据库
    print("初始化数据库...")
    init_database()
    
    # 创建应用
    app = create_app()
    # 运行应用
    print("启动Flask应用...")
    app.run(debug=True)
