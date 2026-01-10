# config.py
import os
from datetime import timedelta
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 获取项目根目录
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    # ================= 基础配置 =================
    # 安全密钥 - 从环境变量获取，如果没有则使用默认值
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'production-secret-key-change-this-in-production'
    
    # 生产环境关闭调试模式
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    # ================= 数据库配置 =================
    # 使用绝对路径的SQLite数据库
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{os.path.join(basedir, "app.db")}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ================= 上传配置 =================
    # 上传文件总目录
    UPLOAD_FOLDER = os.path.join(basedir, 'app', 'static', 'uploads')
    
    # 各类上传子目录
    AVATAR_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'avatars')
    LOGO_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'logos')
    DISH_UPLOAD_FOLDER = os.path.join(UPLOAD_FOLDER, 'dishes')
    
    # 文件上传限制
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'jfif'}
    
    # 默认文件名
    DEFAULT_AVATAR = 'default_avatar.png'
    DEFAULT_LOGO = 'default_logo.png'
    DEFAULT_DISH_IMAGE = 'default_dish.png'
    
    # ================= 会话配置 =================
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    
    # 生产环境会话安全
    SESSION_COOKIE_SECURE = False  # 如果没有HTTPS，设为False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # ================= 登录配置 =================
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    SESSION_PROTECTION = 'strong'
    
    # 登录相关
    LOGIN_VIEW = 'auth.login'
    LOGIN_MESSAGE = '请先登录以访问此页面。'
    LOGIN_MESSAGE_CATEGORY = 'info'
    
    # ================= AI服务配置 =================
    # DeepSeek API配置
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
    DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions'
    DEEPSEEK_MODEL = 'deepseek-chat'
    
    # 本地AI配置（可选）
    ANYTHINGLLM_API_KEY = os.environ.get('ANYTHINGLLM_API_KEY', '')
    ANYTHINGLLM_WORKSPACE_SLUG = os.environ.get('ANYTHINGLLM_WORKSPACE_SLUG', '')
    ANYTHINGLLM_API_URL = 'http://localhost:3001/api/v1'
    
    # ================= 分页配置 =================
    DISHES_PER_PAGE = 12
    ORDERS_PER_PAGE = 15
    CUSTOMERS_PER_PAGE = 20
    
    # ================= 生产服务器配置 =================
    # 设置服务器名称
    SERVER_NAME = os.environ.get('SERVER_NAME', None)
    
    # 应用上下文
    APPLICATION_ROOT = '/'
    PREFERRED_URL_SCHEME = 'http'
    
    # ================= 邮件配置（如果需要） =================
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')

# 创建必要的上传目录
def create_upload_directories():
    """创建上传目录"""
    directories = [
        Config.UPLOAD_FOLDER,
        Config.AVATAR_UPLOAD_FOLDER,
        Config.LOGO_UPLOAD_FOLDER,
        Config.DISH_UPLOAD_FOLDER
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            print(f"✅ 创建目录: {directory}")
        else:
            print(f"📁 目录已存在: {directory}")