#!/bin/bash

# 确保遇到错误自动退出
set -e

# 定义清理函数：脚本退出时关闭前后端进程
cleanup() {
    echo -e "\n[Info] 正在停止服务..."
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    if [ -n "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    exit 0
}

# 捕获终止信号
trap cleanup EXIT SIGINT SIGTERM

echo "[Info] 准备启动后端..."
cd backend
# 检查虚拟环境
if [ ! -d ".venv" ]; then
    echo "[Info] 正在创建虚拟环境并安装依赖..."
    uv venv
    uv pip install -r requirements.txt
fi

# 在后台启动后端
echo "[Info] 启动后端服务 (http://127.0.0.1:8010)..."
uv run uvicorn app.main:app --reload --port 8010 &
BACKEND_PID=$!
cd ..

echo "----------------------------------------"

echo "[Info] 准备启动前端..."
cd frontend
# 检查依赖
if [ ! -d "node_modules" ]; then
    echo "[Info] 正在安装前端依赖..."
    bun install
fi

# 在后台启动前端
echo "[Info] 启动前端服务 (http://127.0.0.1:5173)..."
bun run dev &
FRONTEND_PID=$!
cd ..

echo "----------------------------------------"
echo "[Success] API/Dashboard: http://127.0.0.1:8010/docs"
echo "[Success] Frontend App: http://127.0.0.1:5173"
echo "[Info] 按 Ctrl+C 停止所有服务"
echo "----------------------------------------"

# 等待后台进程结束
wait
