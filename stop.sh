#!/bin/bash

# ETF预测系统停止脚本

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

PID_FILE="$PROJECT_DIR/etf-predict.pid"
SCHEDULER_PID_FILE="$PROJECT_DIR/scheduler.pid"

# 停止调度器
if [ -f "$SCHEDULER_PID_FILE" ]; then
    SCHEDULER_PID=$(cat "$SCHEDULER_PID_FILE")

    if ps -p "$SCHEDULER_PID" > /dev/null 2>&1; then
        echo "🛑 正在停止定时任务调度器 (PID: $SCHEDULER_PID)..."
        kill "$SCHEDULER_PID" 2>/dev/null

        # 等待进程结束
        for i in {1..5}; do
            if ! ps -p "$SCHEDULER_PID" > /dev/null 2>&1; then
                echo "✅ 定时任务调度器已停止"
                rm -f "$SCHEDULER_PID_FILE"
                break
            fi
            sleep 1
        done

        # 如果还未停止，强制杀死
        if ps -p "$SCHEDULER_PID" > /dev/null 2>&1; then
            echo "⚠️ 调度器未响应，强制停止..."
            kill -9 "$SCHEDULER_PID" 2>/dev/null
            sleep 1
            rm -f "$SCHEDULER_PID_FILE"
        fi
    else
        echo "⚠️ 调度器未运行 (PID: $SCHEDULER_PID)"
        rm -f "$SCHEDULER_PID_FILE"
    fi
    echo ""
fi

# 检查 PID 文件是否存在
if [ ! -f "$PID_FILE" ]; then
    echo "⚠️ 未找到 API 服务的 PID 文件，服务可能未通过脚本启动"

    # 尝试通过端口查找进程
    PORT="8000"
    PID=$(lsof -ti :$PORT 2>/dev/null)

    if [ -n "$PID" ]; then
        echo ""
        echo "发现端口 $PORT 上的进程 (PID: $PID)"
        read -p "是否停止该进程? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            kill $PID
            echo "✅ 进程已停止"
        fi
    else
        echo "ℹ️ 未发现运行中的服务"
    fi
    exit 0
fi

# 读取 PID
PID=$(cat "$PID_FILE")

# 检查进程是否存在
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "⚠️ API 服务未运行 (PID: $PID)"
    rm -f "$PID_FILE"
    exit 0
fi

echo "🛑 正在停止 API 服务 (PID: $PID)..."

# 发送 TERM 信号
kill "$PID"

# 等待进程结束
for i in {1..10}; do
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ API 服务已停止"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

# 如果还未停止，强制杀死
if ps -p "$PID" > /dev/null 2>&1; then
    echo "⚠️ 服务未响应，强制停止..."
    kill -9 "$PID"
    sleep 1
    if ! ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ API 服务已强制停止"
        rm -f "$PID_FILE"
    else
        echo "❌ 无法停止服务"
        exit 1
    fi
fi

echo ""
echo "✅ 所有服务已停止"
