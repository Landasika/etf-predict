#!/bin/bash
# 日志清理脚本
# 定期清理旧日志文件

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"

echo "🧹 日志清理工具"
echo "================"

# 检查日志目录
if [ ! -d "$LOG_DIR" ]; then
    echo "❌ 日志目录不存在: $LOG_DIR"
    exit 1
fi

# 统计信息
total_size=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
log_count=$(find "$LOG_DIR" -type f -name "*.log*" 2>/dev/null | wc -l)

echo "📊 当前状态:"
echo "   日志目录: $LOG_DIR"
echo "   总大小: $total_size"
echo "   日志文件数: $log_count"
echo ""

# 清理参数
DAYS_TO_KEEP=${1:-7}  # 默认保留7天
DRY_RUN=${2:-false}   # 是否只是模拟运行

echo "🗑️  清理规则:"
echo "   保留天数: $DAYS_TO_KEEP 天"
echo "   模拟运行: $DRY_RUN"
echo ""

# 查找要删除的文件
if [ "$DRY_RUN" = "true" ]; then
    echo "📋 将要删除的文件:"
    find "$LOG_DIR" -type f -name "*.log*" -mtime +$DAYS_TO_KEEP -print -exec ls -lh {} \;
    echo ""
    echo "✅ 模拟运行完成（未实际删除）"
else
    # 实际删除
    deleted_count=$(find "$LOG_DIR" -type f -name "*.log*" -mtime +$DAYS_TO_KEEP -delete -print | wc -l)

    echo "🗑️  已删除 $deleted_count 个超过 $DAYS_TO_KEEP 天的日志文件"

    # 显示清理后的状态
    new_size=$(du -sh "$LOG_DIR" 2>/dev/null | cut -f1)
    new_count=$(find "$LOG_DIR" -type f -name "*.log*" 2>/dev/null | wc -l)

    echo ""
    echo "📊 清理后状态:"
    echo "   总大小: $new_size"
    echo "   日志文件数: $new_count"
    echo ""
    echo "✅ 清理完成！"
fi
