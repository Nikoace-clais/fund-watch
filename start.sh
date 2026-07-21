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

# PID 文件（放项目内,避免 /tmp 多用户冲突与漂移）
RUN_DIR="$PROJECT_DIR/.run"
mkdir -p "$RUN_DIR"
BACKEND_PID_FILE="$RUN_DIR/backend.pid"
FRONTEND_PID_FILE="$RUN_DIR/frontend.pid"

# 日志文件
LOG_DIR="$PROJECT_DIR/logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

# 端口占用检查:优先 ss,退化为 /dev/tcp 探测
port_in_use() {
    local port=$1
    if command -v ss &> /dev/null; then
        ss -tln 2>/dev/null | awk '{print $4}' | grep -qE "(^|:|\])${port}$"
    else
        (echo > "/dev/tcp/127.0.0.1/$port") 2>/dev/null
    fi
}

check_ports_free() {
    local conflict=0
    if port_in_use 8010; then
        echo -e "${RED}✗ 端口 8010 已被占用（后端）${NC}"
        conflict=1
    fi
    if port_in_use 5173; then
        echo -e "${RED}✗ 端口 5173 已被占用（前端）${NC}"
        conflict=1
    fi
    if [ "$conflict" -eq 1 ]; then
        echo "可能有旧实例仍在运行，请先停止（如 lsof -i :8010 / :5173 确认后 kill），再重新启动。"
        exit 1
    fi
}

# 按 PID 文件停止进程;kill 前校验 /proc/<pid>/cmdline 匹配,防 stale PID 误杀
safe_kill() {
    local pid_file=$1 pattern=$2 name=$3
    [ -f "$pid_file" ] || return 0
    local pid
    pid=$(cat "$pid_file")
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
        if tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null | grep -qE "$pattern"; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            echo -e "${GREEN}✓ $name 已停止${NC}"
        else
            echo -e "${YELLOW}⚠ PID $pid 的进程不是 $name（stale PID 文件），跳过 kill${NC}"
        fi
    fi
    rm -f "$pid_file"
}

# 清理函数
cleanup() {
    echo -e "\n${YELLOW}🛑 正在停止服务...${NC}"

    safe_kill "$BACKEND_PID_FILE" 'app\.main|uvicorn' "后端"
    safe_kill "$FRONTEND_PID_FILE" 'pnpm run dev|vite' "前端"

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

    # 检查 pnpm(由 corepack 提供,Node 20+ 内置 corepack)
    if ! command -v pnpm &> /dev/null && command -v corepack &> /dev/null; then
        corepack enable
    fi
    if ! command -v pnpm &> /dev/null; then
        echo -e "${RED}✗ pnpm 未安装${NC}"
        echo "请启用 corepack(Node 20+ 内置): corepack enable"
        exit 1
    fi
    echo -e "${GREEN}✓ pnpm 已安装${NC}"

    # 检查后端依赖
    if [ ! -d "$BACKEND_DIR/.venv" ]; then
        echo -e "${YELLOW}⚠ 后端虚拟环境不存在，正在创建...${NC}"
        (cd "$BACKEND_DIR" && uv sync)
    fi

    # 检查前端依赖
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo -e "${YELLOW}⚠ 前端依赖未安装，正在安装...${NC}"
        (cd "$FRONTEND_DIR" && pnpm install)
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
    pnpm run dev > "$FRONTEND_LOG" 2>&1 &

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

    # 端口被占用直接退出,避免健康探测命中旧进程误判启动成功
    check_ports_free

    # 清理可能残留的 stale PID 文件与旧日志
    rm -f "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
    : > "$BACKEND_LOG"
    : > "$FRONTEND_LOG"

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
