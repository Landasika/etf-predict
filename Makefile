.PHONY: help build up down restart logs ps exec shell test clean

# 默认目标
.DEFAULT_GOAL := help

# 颜色定义
GREEN  := \033[0;32m
YELLOW := \033[0;33m
BLUE   := \033[0;34m
NC     := \033[0m # No Color

help: ## 显示帮助信息
	@echo "$(GREEN)ETF预测系统 Docker 命令$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-15s$(NC) %s\n", $$1, $$2}'

build: ## 构建 Docker 镜像
	@echo "$(GREEN)📦 构建 Docker 镜像...$(NC)"
	docker-compose build

up: ## 启动服务
	@echo "$(GREEN)🚀 启动服务...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✅ 服务已启动$(NC)"
	@echo "   API: http://localhost:8000"
	@echo "   文档: http://localhost:8000/docs"

down: ## 停止并删除容器
	@echo "$(YELLOW)🛑 停止服务...$(NC)"
	docker-compose down

restart: ## 重启服务
	@echo "$(GREEN)🔄 重启服务...$(NC)"
	docker-compose restart

logs: ## 查看实时日志
	docker-compose logs -f etf-predict

ps: ## 查看容器状态
	docker-compose ps

exec: ## 进入容器
	docker-compose exec etf-predict bash

shell: exec ## 进入容器（别名）

test: ## 运行测试
	docker-compose exec etf-predict pytest tests/ -v

init-db: ## 初始化数据库
	docker-compose exec etf-predict python init_db.py

download: ## 下载数据
	docker-compose exec etf-predict python scripts/download_etf_data.py

clean: ## 清理容器和镜像
	@echo "$(YELLOW)🧹 清理容器和镜像...$(NC)"
	docker-compose down -v
	docker-compose rm -f
	docker rmi etf-predict_etf-predict 2>/dev/null || true

rebuild: clean build ## 完全重新构建

check: ## 健康检查
	@curl -s http://localhost:8000/health | jq . || echo "服务未运行或健康检查失败"

status: ## 显示详细状态
	@echo "$(BLUE)📊 系统状态$(NC)"
	@echo ""
	@docker-compose ps
	@echo ""
	@echo "$(BLUE)💾 存储卷$(NC)"
	@docker volume ls | grep etf || echo "未找到存储卷"
	@echo ""
	@echo "$(BLUE)📝 日志（最后 20 行）$(NC)"
	@docker-compose logs --tail=20 etf-predict
