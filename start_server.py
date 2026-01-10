# start_server.py
import os
import sys
from app import create_app
from config import Config

# 设置环境变量
os.environ['FLASK_DEBUG'] = 'False'
os.environ['DATABASE_URL'] = f'sqlite:///{os.path.join(os.path.dirname(__file__), "app.db")}'

# 获取云主机IP（可以从环境变量获取）
server_host = os.environ.get('SERVER_HOST', '0.0.0.0')
server_port = int(os.environ.get('SERVER_PORT', 5000))

# 创建应用
app = create_app()

if __name__ == '__main__':
    print(f"🚀 启动餐厅点餐平台服务器...")
    print(f"📡 服务器地址: http://{server_host}:{server_port}")
    print(f"🌐 客户端访问地址: http://{server_host}:{server_port}")
    print(f"📁 数据库位置: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"🔧 调试模式: {app.config.get('DEBUG', False)}")
    print("-" * 50)
    
    app.run(
        host=server_host,
        port=server_port,
        debug=app.config.get('DEBUG', False)
    )