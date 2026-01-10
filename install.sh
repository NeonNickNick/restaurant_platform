#!/bin/bash
# install.sh - 简易安装脚本

echo "🛠️  安装餐厅点餐平台..."

# 1. 检查Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 请先安装Python3"
    exit 1
fi

echo "✅ Python3 已安装: $(python3 --version)"

# 2. 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 3. 激活虚拟环境
source venv/bin/activate
echo "✅ 激活虚拟环境"

# 4. 安装依赖
echo "📦 安装依赖包..."
pip install --upgrade pip
pip install flask flask-sqlalchemy flask-login flask-wtf flask-migrate pillow werkzeug
pip install requests python-dotenv gunicorn

# 5. 创建必要目录
echo "📁 创建目录结构..."
mkdir -p app/static/uploads/avatars
mkdir -p app/static/uploads/logos
mkdir -p app/static/uploads/dishes
mkdir -p logs

# 6. 初始化数据库
echo "🗃️  初始化数据库..."
cd "$(dirname "$0")"
export FLASK_APP=app
export FLASK_DEBUG=False

# 检查是否有数据库文件
if [ ! -f "app.db" ]; then
    echo "🔧 创建数据库表..."
    python -c "
from app import create_app, db
from app.models import User, Restaurant, Dish, Category, Order, OrderItem, Blacklist
app = create_app()
with app.app_context():
    db.create_all()
    print('✅ 数据库表创建完成')
    "
else
    echo "✅ 数据库已存在"
fi

# 7. 设置权限
chmod +x start.sh stop.sh status.sh

echo "🎉 安装完成！"
echo ""
echo "📋 使用方法:"
echo "  启动服务器: ./start.sh"
echo "  停止服务器: ./stop.sh"
echo "  检查状态: ./status.sh"
echo ""
echo "🔧 首次使用请运行:"
echo "  python add_test_data.py  # 创建测试数据（如果有的话）"