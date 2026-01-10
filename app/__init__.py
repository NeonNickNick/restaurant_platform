from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
import os
import sys
import logging
from datetime import timedelta

# 获取项目根目录路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 将项目根目录添加到 Python 路径
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config

# 初始化扩展
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()

# 配置登录管理器
login_manager.login_view = 'auth.login'  # 设置登录视图
login_manager.login_message = '请先登录以访问此页面。'
login_manager.login_message_category = 'warning'

def create_app(config_class=Config):
    """应用工厂函数"""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 生产环境日志配置
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # 文件日志处理器
        file_handler = logging.FileHandler('logs/app.log')
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('餐厅点餐平台启动')
    
    # 确保上传目录存在
    upload_dirs = [
        app.config.get('AVATAR_UPLOAD_FOLDER'),
        app.config.get('LOGO_UPLOAD_FOLDER'),
        app.config.get('DISH_UPLOAD_FOLDER')
    ]
    
    for upload_dir in upload_dirs:
        if upload_dir and not os.path.exists(upload_dir):
            try:
                os.makedirs(upload_dir, exist_ok=True)
                app.logger.info(f"创建上传目录: {upload_dir}")
            except Exception as e:
                app.logger.error(f"创建目录失败 {upload_dir}: {e}")
    
    # 初始化扩展
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # 用户加载器
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        """用户加载器"""
        try:
            return User.query.get(int(user_id))
        except Exception as e:
            app.logger.error(f"加载用户时出错: {e}")
            return None
    
    # 注册蓝图
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.restaurant import restaurant_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(restaurant_bp, url_prefix='/restaurant')
    
    # 创建数据库表
    with app.app_context():
        try:
            db.create_all()
            app.logger.info("数据库表创建/验证完成")
            
            # 检查表是否存在
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            app.logger.info(f"数据库表: {tables}")
        except Exception as e:
            app.logger.error(f"数据库创建时出错: {e}")
    
    return app