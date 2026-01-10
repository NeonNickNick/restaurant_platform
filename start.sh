#!/bin/bash
# start.sh - 启动服务器

echo "🚀 启动餐厅点餐平台服务器..."

# 进入项目目录
cd "$(dirname "$0")"

# 激活虚拟环境
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ 激活虚拟环境"
else
    echo "❌ 虚拟环境不存在，请先运行: python3 -m venv venv"
    exit 1
fi

# 安装依赖
echo "📦 检查依赖..."
pip install -r requirements.txt 2>/dev/null || echo "⚠️  requirements.txt不存在，跳过"

# 设置环境变量
export FLASK_DEBUG=False
export SERVER_HOST=0.0.0.0
export SERVER_PORT=5000

# 创建必要目录
mkdir -p app/static/uploads/avatars
mkdir -p app/static/uploads/logos
mkdir -p app/static/uploads/dishes
mkdir -p logs

echo "📁 创建上传目录完成"

# 启动服务器
echo "📡 服务器启动在: http://0.0.0.0:5000"
echo "🌐 客户端可通过IP地址访问"
echo "-" * 50

# 使用Gunicorn启动（生产环境）
if command -v gunicorn &> /dev/null; then
    echo "🔧 使用Gunicorn启动..."
    gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()" --access-logfile logs/access.log --error-logfile logs/error.log
else
    echo "🔧 使用Flask开发服务器启动..."
    python start_server.py
fi