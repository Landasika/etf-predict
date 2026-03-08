#!/bin/bash

# ETF预测系统启动脚本
# 使用方法:
#   ./start.sh        - 前台运行（仅 API）
#   ./start.sh -s     - 后台运行（仅 API）
#   ./start.sh -d     - 前台运行（API + 定时任务）
#   ./start.sh -s -d  - 后台运行（API + 定时任务）

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

PID_FILE="$PROJECT_DIR/etf-predict.pid"
SCHEDULER_PID_FILE="$PROJECT_DIR/scheduler.pid"
LOG_FILE="$PROJECT_DIR/logs/server.log"
SCHEDULER_LOG_FILE="$PROJECT_DIR/logs/scheduler.log"

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

# 自动加载 .env（供 scheduler.py / run.py 读取）
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
fi

is_pid_running() {
    local pid="$1"
    ps -p "$pid" >/dev/null 2>&1
}

cleanup_stale_pid() {
    local pid_file="$1"
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if ! is_pid_running "$pid"; then
            rm -f "$pid_file"
        fi
    fi
}

# 参数解析
DAEMON_MODE=false
ENABLE_SCHEDULER=false
while getopts "sdh" opt; do
    case $opt in
        s)
            DAEMON_MODE=true
            ;;
        d)
            ENABLE_SCHEDULER=true
            ;;
        h|\?)
            echo "使用方法: $0 [-s] [-d]"
            echo "  -s  后台运行模式"
            echo "  -d  启用 Python 定时任务（时间由 SCHEDULER_TIMES 或 scheduler.py 参数决定）"
            echo ""
            echo "示例:"
            echo "  $0           - 前台运行 API"
            echo "  $0 -s        - 后台运行 API"
            echo "  $0 -d        - 前台运行 API + 定时任务"
            echo "  $0 -s -d     - 后台运行 API + 定时任务"
            exit 0
            ;;
    esac
done

mkdir -p "$PROJECT_DIR/logs"
cleanup_stale_pid "$PID_FILE"
cleanup_stale_pid "$SCHEDULER_PID_FILE"

if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if is_pid_running "$OLD_PID"; then
        echo "❌ API 服务已在运行 (PID: $OLD_PID)"
        echo "如需重启，请先运行 ./stop.sh"
        exit 1
    fi
    rm -f "$PID_FILE"
fi

if [ "$ENABLE_SCHEDULER" = true ] && [ -f "$SCHEDULER_PID_FILE" ]; then
    OLD_SCHED_PID=$(cat "$SCHEDULER_PID_FILE")
    if is_pid_running "$OLD_SCHED_PID"; then
        echo "❌ 定时任务已在运行 (PID: $OLD_SCHED_PID)"
        echo "如需重启，请先运行 ./stop.sh"
        exit 1
    fi
    rm -f "$SCHEDULER_PID_FILE"
fi

if lsof -Pi :"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "❌ 端口 $PORT 已被占用"
    echo "请先释放端口，或修改 PORT 环境变量"
    exit 1
fi

start_api() {
    if [ "$DAEMON_MODE" = true ]; then
        echo "📡 API 服务: 后台"
        nohup "$PYTHON_BIN" run.py > "$LOG_FILE" 2>&1 &
        API_PID=$!
    else
        echo "📡 API 服务: 前台"
        "$PYTHON_BIN" run.py > "$LOG_FILE" 2>&1 &
        API_PID=$!
    fi

    echo "$API_PID" > "$PID_FILE"
    sleep 3

    if is_pid_running "$API_PID"; then
        echo "✅ API 服务启动成功! (PID: $API_PID)"
    else
        echo "❌ API 服务启动失败，请查看日志: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

start_scheduler() {
    if ! "$PYTHON_BIN" -c "import schedule" >/dev/null 2>&1; then
        echo "❌ 缺少依赖: schedule"
        echo "请先安装: pip install schedule"
        exit 1
    fi

    echo "⏰ 定时任务: 已启用"

    if [ "$DAEMON_MODE" = true ]; then
        nohup "$PYTHON_BIN" scheduler.py > "$SCHEDULER_LOG_FILE" 2>&1 &
        SCHEDULER_PID=$!
    else
        "$PYTHON_BIN" scheduler.py > "$SCHEDULER_LOG_FILE" 2>&1 &
        SCHEDULER_PID=$!
    fi

    echo "$SCHEDULER_PID" > "$SCHEDULER_PID_FILE"
    sleep 1

    if is_pid_running "$SCHEDULER_PID"; then
        echo "✅ 定时任务启动成功! (PID: $SCHEDULER_PID)"
    else
        echo "❌ 定时任务启动失败，请查看日志: $SCHEDULER_LOG_FILE"
        rm -f "$SCHEDULER_PID_FILE"
        exit 1
    fi
}

cleanup_on_signal() {
    echo ""
    echo "🛑 收到停止信号，正在清理进程..."

    if [ -n "${SCHEDULER_PID:-}" ] && is_pid_running "$SCHEDULER_PID"; then
        kill "$SCHEDULER_PID" >/dev/null 2>&1
    fi

    if [ -n "${API_PID:-}" ] && is_pid_running "$API_PID"; then
        kill "$API_PID" >/dev/null 2>&1
    fi

    wait >/dev/null 2>&1
    rm -f "$PID_FILE" "$SCHEDULER_PID_FILE"
    echo "✅ 已停止"
    exit 0
}

if [ "$DAEMON_MODE" = false ]; then
    trap cleanup_on_signal INT TERM
fi

echo "🚀 正在启动 ETF 预测系统..."
echo "监听地址: $HOST:$PORT"
start_api

if [ "$ENABLE_SCHEDULER" = true ]; then
    start_scheduler
fi

echo ""
echo "============================================================"
echo "📊 ETF 预测系统启动完成"
echo "============================================================"
echo "访问地址: http://127.0.0.1:$PORT"
echo "API 文档: http://127.0.0.1:$PORT/docs"
echo ""
echo "管理命令:"
echo "  查看 API 日志: tail -f $LOG_FILE"
if [ "$ENABLE_SCHEDULER" = true ]; then
    echo "  查看调度器日志: tail -f $SCHEDULER_LOG_FILE"
fi
echo "  停止服务: ./stop.sh"
echo "============================================================"

if [ "$DAEMON_MODE" = true ]; then
    exit 0
fi

if [ "$ENABLE_SCHEDULER" = true ]; then
    wait "$SCHEDULER_PID"
    SCHEDULER_EXIT_CODE=$?
    rm -f "$SCHEDULER_PID_FILE"

    # 前台模式下，调度器退出后同步停止 API
    if [ -n "${API_PID:-}" ] && is_pid_running "$API_PID"; then
        kill "$API_PID" >/dev/null 2>&1
        wait "$API_PID" >/dev/null 2>&1
    fi
    rm -f "$PID_FILE"
    exit "$SCHEDULER_EXIT_CODE"
else
    wait "$API_PID"
    API_EXIT_CODE=$?
    rm -f "$PID_FILE"
    exit "$API_EXIT_CODE"
fi
