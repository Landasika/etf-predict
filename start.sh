#!/bin/bash

# ETF预测系统启动脚本
# 使用方法:
#   ./start.sh         - 前台运行（仅 API）
#   ./start.sh -s       - 后台运行（仅 API）
#   ./start.sh -d       - 后台运行（API + 定时任务）
#   ./start.sh -ds      - 前台运行（API + 定时任务）

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR" || exit 1

PID_FILE="$PROJECT_DIR/etf-predict.pid"
SCHEDULER_PID_FILE="$PROJECT_DIR/scheduler.pid"
LOG_FILE="$PROJECT_DIR/logs/server.log"
SCHEDULER_LOG_FILE="$PROJECT_DIR/logs/scheduler.log"
HOST="0.0.0.0"
PORT="8000"

# 解析参数
DAEMON_MODE=false
ENABLE_SCHEDULER=false
while getopts "sd" opt; do
    case $opt in
        s)
            DAEMON_MODE=true
            ;;
        d)
            ENABLE_SCHEDULER=true
            ;;
        \?)
            echo "使用方法: $0 [-s] [-d]"
            echo "  -s  后台运行模式"
            echo "  -d  启用定时任务（每个交易日的 9:40, 10:40, 11:40, 13:40, 14:40 推送飞书）"
            echo ""
            echo "示例:"
            echo "  $0          - 前台运行 API"
            echo "  $0 -s        - 后台运行 API"
            echo "  $0 -s -d    - 后台运行 API + 定时任务"
            echo "  $0 -d       - 前台运行 API + 定时任务"
            exit 1
            ;;
    esac
done

# 创建日志目录
mkdir -p logs

# 检查是否已经在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "服务已在运行 (PID: $OLD_PID)"
        echo "如需重启，请先运行 ./stop.sh"
        exit 1
    else
        echo "清理旧的 PID 文件"
        rm -f "$PID_FILE"
    fi
fi

# 检查端口是否被占用
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "端口 $PORT 已被占用"
    echo "请检查是否有其他服务正在使用该端口"
    exit 1
fi

echo "🚀 正在启动 ETF 预测系统..."
echo "监听地址: $HOST:$PORT"

# 启动 API 服务
if [ "$DAEMON_MODE" = true ]; then
    # 后台运行 API
    echo "📡 API 服务: 后台"
    nohup python run.py > "$LOG_FILE" 2>&1 &
    API_PID=$!
    echo $API_PID > "$PID_FILE"

    # 等待 API 启动
    sleep 3

    # 检查是否启动成功
    if ps -p $API_PID > /dev/null 2>&1; then
        echo "✅ API 服务启动成功! (PID: $API_PID)"
    else
        echo "❌ API 服务启动失败，请查看日志: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
else
    # 前台运行 API
    echo "📡 API 服务: 前台"
    python run.py &
    API_PID=$!
    echo $API_PID > "$PID_FILE"

    # 如果不启用定时任务，前台等待
    if [ "$ENABLE_SCHEDULER" = false ]; then
        echo "按 Ctrl+C 停止服务"
        echo ""
        echo "访问地址: http://127.0.0.1:$PORT"
        echo "API 文档: http://127.0.0.1:$PORT/docs"

        # 等待进程结束
        wait $API_PID

        # 进程结束后清理 PID 文件
        rm -f "$PID_FILE"
        exit 0
    fi
fi

# 启动定时任务
if [ "$ENABLE_SCHEDULER" = true ]; then
    echo ""
    echo "⏰ 定时任务: 后台"

    # 检查依赖
    if ! python3 -c "import schedule" 2>/dev/null; then
        echo "❌ 缺少依赖，正在安装 schedule..."
        pip3 install schedule -q
    fi

    # 启动调度器
    if [ "$DAEMON_MODE" = true ]; then
        # 后台运行调度器
        nohup python3 scheduler.py > "$SCHEDULER_LOG_FILE" 2>&1 &
        SCHEDULER_PID=$!
        echo $SCHEDULER_PID > "$SCHEDULER_PID_FILE"
        echo "✅ 定时任务启动成功! (PID: $SCHEDULER_PID)"
        echo "   日志: tail -f $SCHEDULER_LOG_FILE"
    else
        # 前台运行调度器
        echo "按 Ctrl+C 停止定时任务（不影响 API 服务）"
        echo ""
        python3 scheduler.py &
        SCHEDULER_PID=$!
        echo $SCHEDULER_PID > "$SCHEDULER_PID_FILE"

        # 等待调度器进程结束
        wait $SCHEDULER_PID

        # 清理调度器 PID 文件
        rm -f "$SCHEDULER_PID_FILE"
    fi
fi

# 显示服务信息
echo ""
echo "=" * 60
echo "📊 ETF 预测系统启动完成"
echo "=" * 60
echo "访问地址: http://127.0.0.0.1:$PORT"
echo "API 文档: http://127.0.0.0.1:$PORT/docs"
echo ""
echo "管理命令:"
echo "  查看日志: tail -f $LOG_FILE"
if [ "$ENABLE_SCHEDULER" = true ]; then
    echo "  查看调度器日志: tail -f $SCHEDULER_LOG_FILE"
fi
echo "  停止服务: ./stop.sh"
echo "=" * 60
