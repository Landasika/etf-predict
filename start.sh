#!/bin/bash
# ETF预测系统启动脚本（支持前台/后台运行）

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目配置
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PID_FILE="$PROJECT_DIR/etf-predict.pid"
LOG_FILE="$PROJECT_DIR/logs/server.log"

# 进入项目目录
cd "$PROJECT_DIR"

# 显示帮助信息
show_help() {
    echo "ETF预测系统启动脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  start, run      前台启动服务器（默认）"
    echo "  start-daemon, daemon, background, bg"
    echo "                  后台启动服务器"
    echo "  stop            停止服务器"
    echo "  restart         重启服务器"
    echo "  status          查看服务器状态"
    echo "  logs            查看服务器日志"
    echo "  help, -h        显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start         # 前台启动"
    echo "  $0 daemon        # 后台启动"
    echo "  $0 stop          # 停止服务"
    echo "  $0 restart       # 重启服务"
}

# 检查环境
check_environment() {
    echo -e "${BLUE}📋 检查环境...${NC}"

    # 检查Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ 错误: 未找到Python3${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ Python3: $(python3 --version)${NC}"

    # 检查必要的目录
    mkdir -p logs data
    echo -e "${GREEN}  ✓ 目录创建完成${NC}"

    # 检查依赖
    if ! python3 -c "import fastapi" &> /dev/null; then
        echo -e "${YELLOW}  ⚠️  依赖未安装，正在安装...${NC}"
        pip install -q -r requirements.txt 2>/dev/null || {
            echo -e "${YELLOW}  ⚠️  requirements.txt 不存在，跳过依赖安装${NC}"
        }
    fi

    echo ""
}

# 获取进程ID
get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

# 检查进程是否运行
is_running() {
    local pid=$(get_pid)
    if [ -n "$pid" ]; then
        # 检查进程是否存在
        if ps -p "$pid" &> /dev/null; then
            return 0
        else
            # 进程不存在，清理PID文件
            rm -f "$PID_FILE"
        fi
    fi
    return 1
}

# 启动服务器（前台）
start_foreground() {
    check_environment

    if is_running; then
        echo -e "${YELLOW}⚠️  服务器已在运行中 (PID: $(get_pid))${NC}"
        echo "使用 '$0 restart' 重启服务器"
        exit 1
    fi

    show_banner
    echo -e "${GREEN}🎯 启动服务器（前台模式）...${NC}"
    echo -e "${YELLOW}按 Ctrl+C 停止服务器${NC}"
    echo ""

    # 启动服务器
    python3 run.py
}

# 启动服务器（后台）
start_daemon() {
    check_environment

    if is_running; then
        echo -e "${YELLOW}⚠️  服务器已在运行中 (PID: $(get_pid))${NC}"
        echo "使用 '$0 restart' 重启服务器"
        exit 1
    fi

    show_banner
    echo -e "${GREEN}🎯 启动服务器（后台模式）...${NC}"

    # 启动服务器（后台）
    nohup python3 run.py >> "$LOG_FILE" 2>&1 &
    local pid=$!

    # 保存PID
    echo $pid > "$PID_FILE"

    # 等待服务器启动
    sleep 2

    if is_running; then
        echo -e "${GREEN}✓ 服务器启动成功${NC}"
        echo -e "  PID: $pid"
        echo -e "  日志: $LOG_FILE"
        echo ""
        echo -e "  使用 '$0 status' 查看状态"
        echo -e "  使用 '$0 logs' 查看日志"
        echo -e "  使用 '$0 stop' 停止服务"
    else
        echo -e "${RED}❌ 服务器启动失败${NC}"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# 停止服务器
stop_server() {
    if ! is_running; then
        echo -e "${YELLOW}⚠️  服务器未运行${NC}"
        exit 0
    fi

    local pid=$(get_pid)
    echo -e "${YELLOW}🛑 停止服务器 (PID: $pid)...${NC}"

    # 发送TERM信号
    kill "$pid" 2>/dev/null || true

    # 等待进程结束（最多10秒）
    local count=0
    while [ $count -lt 10 ]; do
        if ! ps -p "$pid" &> /dev/null; then
            break
        fi
        sleep 1
        count=$((count + 1))
    done

    # 如果进程还在运行，强制杀死
    if ps -p "$pid" &> /dev/null; then
        echo -e "${YELLOW}  强制停止...${NC}"
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi

    # 清理PID文件
    rm -f "$PID_FILE"

    echo -e "${GREEN}✓ 服务器已停止${NC}"
}

# 重启服务器
restart_server() {
    echo -e "${BLUE}🔄 重启服务器...${NC}"
    echo ""

    # 如果正在运行，先停止
    if is_running; then
        stop_server
        sleep 2
    fi

    # 后台启动
    start_daemon
}

# 查看状态
show_status() {
    echo -e "${BLUE}📊 服务器状态${NC}"
    echo ""

    if is_running; then
        local pid=$(get_pid)
        echo -e "${GREEN}  状态: 运行中${NC}"
        echo -e "  PID: $pid"
        echo -e "  端口: 8000"
        echo -e "  地址: http://127.0.0.1:8000"

        # 显示内存使用
        local mem_usage=$(ps -o rss= -p "$pid" | tail -1 2>/dev/null || echo "0")
        local mem_mb=$((mem_usage / 1024))
        echo -e "  内存: ${mem_mb} MB"

        # 显示运行时间
        local elapsed=$(ps -o etime= -p "$pid" | tail -1 2>/dev/null || echo "未知")
        echo -e "  运行时间: $elapsed"

        echo ""
        echo "使用 '$0 logs' 查看日志"
    else
        echo -e "${RED}  状态: 未运行${NC}"
        echo ""
        echo "使用 '$0 start' 启动服务器"
    fi
}

# 查看日志
show_logs() {
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}📋 服务器日志 (最近50行)${NC}"
        echo ""
        tail -50 "$LOG_FILE"
        echo ""
        echo "使用 'tail -f $LOG_FILE' 实时查看日志"
    else
        echo -e "${YELLOW}⚠️  日志文件不存在: $LOG_FILE${NC}"
    fi
}

# 显示横幅
show_banner() {
    echo ""
    echo "=========================================="
    echo "  ETF预测系统"
    echo "=========================================="
    echo "  访问地址: http://127.0.0.1:8000"
    echo "  默认秘钥: admin123"
    echo "=========================================="
    echo ""
    echo -e "${YELLOW}提示:${NC}"
    echo "  • 首次访问需要登录"
    echo "  • 浏览器缓存问题请按 Ctrl+Shift+R"
    echo "  • 后台模式使用 '$0 daemon' 启动"
    echo ""
}

# 主程序
main() {
    local command="${1:-start}"

    case "$command" in
        start|run)
            start_foreground
            ;;
        start-daemon|daemon|background|bg)
            start_daemon
            ;;
        stop)
            stop_server
            ;;
        restart)
            restart_server
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        help|-h|--help)
            show_help
            ;;
        *)
            echo -e "${RED}错误: 未知命令 '$command'${NC}"
            echo ""
            echo "使用 '$0 help' 查看帮助信息"
            exit 1
            ;;
    esac
}

# 运行主程序
main "$@"
