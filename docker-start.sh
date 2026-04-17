#!/bin/bash
# ETF预测系统 Docker 快速启动脚本

set -e

echo "======================================"
echo "ETF预测系统 Docker 部署"
echo "======================================"

# 检查 .env 文件
if [ ! -f .env ]; then
    echo "⚠️  未找到 .env 文件"
    echo "📝 正在从模板创建 .env 文件..."

    if [ -f .env.docker.example ]; then
        cp .env.docker.example .env
        echo "✅ .env 文件已创建"
        echo "⚠️  请编辑 .env 文件，填写 TUSHARE_TOKEN 等必要配置"
        echo "   编辑命令: nano .env"
        echo ""
        read -p "是否现在编辑配置文件？(y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ${EDITOR:-nano} .env
        fi
    else
        echo "❌ 未找到 .env.docker.example 模板文件"
        exit 1
    fi
fi

# 检查 TUSHARE_TOKEN
if ! grep -q "^TUSHARE_TOKEN=" .env || grep -q "^TUSHARE_TOKEN=your_tushare_token_here" .env; then
    echo "⚠️  警告：TUSHARE_TOKEN 未配置或使用默认值"
    echo "   请编辑 .env 文件，设置正确的 TUSHARE_TOKEN"
    echo "   获取 Token: https://tushare.pro/user/token"
    echo ""
    read -p "是否继续启动？(y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# 构建镜像
echo ""
echo "📦 构建 Docker 镜像..."
docker-compose build

# 启动服务
echo ""
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo ""
echo "⏳ 等待服务启动..."
sleep 5

# 检查服务状态
echo ""
echo "📊 服务状态："
docker-compose ps

# 显示访问信息
echo ""
echo "======================================"
echo "✅ 服务已启动！"
echo "======================================"
echo "📱 API 地址: http://localhost:8000"
echo "📖 API 文档: http://localhost:8000/docs"
echo "💚 健康检查: http://localhost:8000/health"
echo "======================================"
echo ""
echo "📝 常用命令："
echo "   查看日志: docker-compose logs -f"
echo "   停止服务: docker-compose stop"
echo "   重启服务: docker-compose restart"
echo "======================================"
