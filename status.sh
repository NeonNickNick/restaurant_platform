#!/bin/bash
# status.sh - 检查服务器状态

echo "🔍 检查服务器状态..."

# 检查进程
pids=$(ps aux | grep -E "(gunicorn|flask|start_server)" | grep -v grep | awk '{print $2}')

if [ -z "$pids" ]; then
    echo "❌ 服务器未运行"
    exit 1
else
    echo "✅ 服务器正在运行 (PID: $pids)"
    
    # 检查端口
    if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null ; then
        echo "✅ 端口 5000 正在监听"
        
        # 获取服务器IP
        ip=$(hostname -I | awk '{print $1}')
        echo "🌐 访问地址: http://$ip:5000"
        echo "🌐 或 http://$(curl -s ifconfig.me):5000 (公网IP)"
    else
        echo "❌ 端口 5000 未监听"
    fi
fi