#!/bin/bash

# Fund Watch - 一键启动脚本
# 同时启动后端 (uvicorn) 和前端 (vite dev server)

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"

# PID 文件
BACKEND_PID_FILE="/tmp/fund-watch-backend.pid"
FRONTEND_PID_FILE="/tmp/fund-watch-frontend.pid"

# 日志文件
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}🛑 正在停止服务...${NC}"

    # 停止后端
    if [ -f "$BACKEND_PID_FILE" ]; then
        local backend_pid
        backend_pid=$(cat "$BACKEND_PID_FILE")
        if kill -0 "$backend_pid" 2>/dev/null; then
            kill "$backend_pid" 2>/dev/null || true
            wait "$backend_pid" 2>/dev/null || true
            echo -e "${GREEN}✓ 后端已停止${NC}"
        fi
        rm -f "$BACKEND_PID_FILE"
    fi

    # 停止前端
    if [ -f "$FRONTEND_PID_FILE" ]; then
        local frontend_pid
        frontend_pid=$(cat "$FRONTEND_PID_FILE")
        if kill -0 "$frontend_pid" 2>/dev/null; then
            kill "$frontend_pid" 2>/dev/null || true
            wait "$frontend_pid" 2>/dev/null || true
            echo -e "${GREEN}✓ 前端已停止${NC}"
        fi
        rm -f "$FRONTEND_PID_FILE"
    fi

    echo -e "${GREEN}👋 服务已清理${NC}"
    exit 0
}

# 设置信号处理
trap cleanup SIGINT SIGTERM EXIT

# 检查依赖
check_dependencies() {
    echo -e "${BLUE}🔍 检查依赖...${NC}"

    # 检查 uv
    if ! command -v uv &> /dev/null; then
        echo -e "${RED}✗ uv 未安装${NC}"
        echo "请安装 uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    echo -e "${GREEN}✓ uv 已安装${NC}"

    # 检查 bun
    if ! command -v bun &> /dev/null; then
        echo -e "${RED}✗ bun 未安装${NC}"
        echo "请安装 bun: curl -fsSL https://bun.sh/install | bash"
        exit 1
    fi
    echo -e "${GREEN}✓ bun 已安装${NC}"

    # 检查后端依赖
    if [ ! -d "$BACKEND_DIR/.venv" ]; then
        echo -e "${YELLOW}⚠ 后端虚拟环境不存在，正在创建...${NC}"
        (cd "$BACKEND_DIR" && uv sync)
    fi

    # 检查前端依赖
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo -e "${YELLOW}⚠ 前端依赖未安装，正在安装...${NC}"
        (cd "$FRONTEND_DIR" && bun install)
    fi
}

# 等待服务启动
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1

    echo -ne "${CYAN}⏳ 等待 $name 启动${NC}"
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e "\n${GREEN}✓ $name 已启动${NC}"
            return 0
        fi
        echo -n "."
        sleep 0.5
        ((attempt++))
    done
    echo -e "\n${RED}✗ $name 启动超时${NC}"
    return 1
}

# 启动后端
start_backend() {
    echo -e "${BLUE}🚀 启动后端服务...${NC}"

    cd "$BACKEND_DIR"

    # 启动后端（使用简洁日志格式）
    uv run python -c "
from app.main import app
import uvicorn

# 配置简洁日志
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)

uvicorn.run(
    app,
    host='0.0.0.0',
    port=8010,
    log_level='warning',
    access_log=False
)
" > "$BACKEND_LOG" 2>&1 &

    echo $! > "$BACKEND_PID_FILE"

    if wait_for_service "http://127.0.0.1:8010/api/health" "后端"; then
        echo -e "${CYAN}  → API: http://127.0.0.1:8010${NC}"
        echo -e "${CYAN}  → 日志: tail -f $BACKEND_LOG${NC}"
        return 0
    else
        return 1
    fi
}

# 启动前端
start_frontend() {
    echo -e "${BLUE}🚀 启动前端服务...${NC}"

    cd "$FRONTEND_DIR"

    # 启动前端
    bun run dev > "$FRONTEND_LOG" 2>&1 &

    echo $! > "$FRONTEND_PID_FILE"

    # 等待 vite 启动（检查端口）
    echo -ne "${CYAN}⏳ 等待前端启动${NC}"
    local attempt=1
    local max_attempts=30
    while [ $attempt -le $max_attempts ]; do
        if grep -q "Local:" "$FRONTEND_LOG" 2>/dev/null; then
            echo -e "\n${GREEN}✓ 前端已启动${NC}"
            break
        fi
        echo -n "."
        sleep 0.5
        ((attempt++))
    done

    if [ $attempt -gt $max_attempts ]; then
        echo -e "\n${RED}✗ 前端启动超时${NC}"
        return 1
    fi

    local url
    url=$(grep -oP 'Local:\s+\Khttp://[^\s]+' "$FRONTEND_LOG" | head -1)
    echo -e "${CYAN}  → 地址: ${url:-http://localhost:5173}${NC}"
    echo -e "${CYAN}  → 日志: tail -f $FRONTEND_LOG${NC}"

    return 0
}

# 显示使用说明
show_usage() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Fund Watch 开发服务器已启动${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${CYAN}📱 访问地址:${NC}"
    echo -e "  前端: ${YELLOW}http://localhost:5173${NC}"
    echo -e "  后端: ${YELLOW}http://127.0.0.1:8010${NC}"
    echo -e "  导入: ${YELLOW}http://localhost:5173/import${NC}"
    echo ""
    echo -e "${CYAN}📋 常用命令:${NC}"
    echo -e "  查看后端日志: ${YELLOW}tail -f logs/backend.log${NC}"
    echo -e "  查看前端日志: ${YELLOW}tail -f logs/frontend.log${NC}"
    echo -e "  停止服务:   ${YELLOW}Ctrl+C${NC}"
    echo ""
    echo -e "${CYAN}📁 项目目录:${NC}"
    echo -e "  $PROJECT_DIR"
    echo ""
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# 主函数
main() {
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}  Fund Watch 一键启动${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    check_dependencies
    echo ""

    # 清理旧日志
    > "$BACKEND_LOG"
    > "$FRONTEND_LOG"

    # 启动服务
    start_backend || exit 1
    echo ""
    start_frontend || exit 1
    echo ""

    show_usage

    # 等待用户中断
    echo -e "${CYAN}💡 按 Ctrl+C 停止服务${NC}"
    while true; do
        sleep 1
    done
}

# 运行主函数
main "$@"
