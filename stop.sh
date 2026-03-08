#!/bin/bash

# ETF预测系统停止脚本（无交互）

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

PID_FILE="$PROJECT_DIR/etf-predict.pid"
SCHEDULER_PID_FILE="$PROJECT_DIR/scheduler.pid"
PORT="${PORT:-8000}"

is_pid_running() {
    local pid="$1"
    ps -p "$pid" >/dev/null 2>&1
}

stop_by_pid() {
    local name="$1"
    local pid="$2"
    local wait_seconds="$3"

    if ! is_pid_running "$pid"; then
        return 1
    fi

    echo "🛑 正在停止${name} (PID: $pid)..."
    kill "$pid" >/dev/null 2>&1

    local i
    for ((i=1; i<=wait_seconds; i++)); do
        if ! is_pid_running "$pid"; then
            echo "✅ ${name}已停止"
            return 0
        fi
        sleep 1
    done

    echo "⚠️ ${name}未响应，强制停止..."
    kill -9 "$pid" >/dev/null 2>&1
    sleep 1

    if ! is_pid_running "$pid"; then
        echo "✅ ${name}已强制停止"
        return 0
    fi

    echo "❌ 无法停止${name} (PID: $pid)"
    return 2
}

STOPPED_ANY=false
HAS_ERROR=false

# 停止调度器
if [ -f "$SCHEDULER_PID_FILE" ]; then
    SCHEDULER_PID=$(cat "$SCHEDULER_PID_FILE")
    if stop_by_pid "定时任务调度器" "$SCHEDULER_PID" 5; then
        STOPPED_ANY=true
    fi
    rm -f "$SCHEDULER_PID_FILE"
fi

# 停止 API
if [ -f "$PID_FILE" ]; then
    API_PID=$(cat "$PID_FILE")
    if stop_by_pid "API 服务" "$API_PID" 10; then
        STOPPED_ANY=true
    fi
    rm -f "$PID_FILE"
fi

# 兜底：通过端口回收 API 进程
PORT_PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [ -n "$PORT_PIDS" ]; then
    for pid in $PORT_PIDS; do
        CMDLINE=$(ps -p "$pid" -o args= 2>/dev/null || true)
        if [[ "$CMDLINE" == *"$PROJECT_DIR"* ]]; then
            if stop_by_pid "端口${PORT}进程" "$pid" 5; then
                STOPPED_ANY=true
            else
                HAS_ERROR=true
            fi
        else
            echo "ℹ️ 跳过非本项目端口进程 (PID: $pid)"
        fi
    done
fi

# 兜底：回收本项目目录下的 scheduler.py
SCHEDULER_PIDS=$(pgrep -f "$PROJECT_DIR/scheduler.py" 2>/dev/null || true)
if [ -n "$SCHEDULER_PIDS" ]; then
    for pid in $SCHEDULER_PIDS; do
        if stop_by_pid "调度器兜底进程" "$pid" 5; then
            STOPPED_ANY=true
        else
            HAS_ERROR=true
        fi
    done
fi

rm -f "$PID_FILE" "$SCHEDULER_PID_FILE"

if [ "$HAS_ERROR" = true ]; then
    exit 1
fi

if [ "$STOPPED_ANY" = true ]; then
    echo ""
    echo "✅ 所有服务已停止"
else
    echo "ℹ️ 未发现运行中的服务"
fi
