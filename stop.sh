#!/bin/bash
# stop.sh - 停止服务器

echo "🛑 停止餐厅点餐平台服务器..."

# 查找并杀死相关进程
pids=$(ps aux | grep -E "(gunicorn|flask|start_server)" | grep -v grep | awk '{print $2}')

if [ -z "$pids" ]; then
    echo "✅ 没有找到运行中的服务器进程"
else
    echo "🔪 杀死进程: $pids"
    kill $pids
    sleep 2
    echo "✅ 服务器已停止"
fi