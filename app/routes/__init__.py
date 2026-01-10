from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os
import sys

# 获取项目根目录路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 将项目根目录添加到 Python 路径
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'  # 设置登录视图
login_manager.login_message = '请先登录以访问此页面。'
login_manager.login_message_category = 'warning'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 确保上传目录存在
    os.makedirs(app.config['AVATAR_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['LOGO_UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['DISH_UPLOAD_FOLDER'], exist_ok=True)
    
    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    
    # 延迟导入，避免循环导入
    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # 注册蓝图
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.restaurant import restaurant_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(restaurant_bp, url_prefix='/restaurant')
    
    # 创建数据库表
    with app.app_context():
        db.create_all()
    
    return app