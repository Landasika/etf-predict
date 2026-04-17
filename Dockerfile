# ==========================================
# Stage 1: Builder - 编译依赖
# ==========================================
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /build

# 安装编译依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 包到临时目录
RUN pip install --no-cache-dir --user -r requirements.txt


# ==========================================
# Stage 2: Runtime - 运行环境
# ==========================================
FROM python:3.11-slim

# 设置标签
LABEL maintainer="landasika"
LABEL description="ETF预测系统 - 基于MACD和多因子量化策略"

# 创建非特权用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 设置工作目录
WORKDIR /app

# 从 builder 阶段复制 Python 包
COPY --from=builder /root/.local /root/.local

# 确保 Python 包在 PATH 中
ENV PATH=/root/.local/bin:$PATH

# 复制项目文件
COPY api/ ./api/
COPY core/ ./core/
COPY strategies/ ./strategies/
COPY optimization/ ./optimization/
COPY scripts/ ./scripts/
COPY static/ ./static/
COPY templates/ ./templates/
COPY tests/ ./tests/
COPY run.py .
COPY init_db.py .
COPY scheduler.py .
COPY config.py .
COPY mypy.ini .
COPY pytest.ini .
COPY ruff.toml .

# 创建必要的目录
RUN mkdir -p data logs optimized_weights && \
    chown -R appuser:appuser /app

# 切换到非特权用户
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# 启动命令
CMD ["python", "run.py"]
