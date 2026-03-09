#!/bin/bash
# ETF预测系统启动脚本

echo "🚀 启动ETF预测系统..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到Python3"
    exit 1
fi

# 进入项目目录
cd "$(dirname "$0")"

# 检查必要的目录
mkdir -p logs data

echo "📂 项目目录: $(pwd)"
echo "📋 检查依赖..."

# 显示登录信息
echo ""
echo "=========================================="
echo "  ETF预测系统认证信息"
echo "=========================================="
echo "  访问地址: http://127.0.0.1:8000"
echo "  默认秘钥: admin123"
echo "=========================================="
echo ""
echo "⚠️  提示: 首次访问需要登录"
echo "⚠️  提示: 浏览器缓存问题请按 Ctrl+Shift+R 强制刷新"
echo ""

# 启动服务器
echo "🎯 启动服务器..."
python3 run.py
