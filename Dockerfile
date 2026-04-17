# ==========================================
# Stage 1: Builder - 编译依赖
# ==========================================
FROM python:3.11-slim AS builder

# 设置工作目录
WORKDIR /build

# 更换为阿里云镜像源（加速国内构建）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update

# 安装编译依赖
RUN apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 包到系统目录（所有用户可访问）
# 使用清华镜像源加速 pip 安装
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple


# ==========================================
# Stage 2: Runtime - 运行环境
# ==========================================
FROM python:3.11-slim

# 设置标签
LABEL maintainer="landasika"
LABEL description="ETF预测系统 - 基于MACD和多因子量化策略"

# 更换为阿里云镜像源（加速国内构建）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update

# 设置工作目录
WORKDIR /app

# 从 builder 阶段复制 Python 包（系统级安装）
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

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

# 创建必要的目录并设置权限
RUN mkdir -p data logs optimized_weights && \
    chmod 777 logs optimized_weights

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# 启动命令
CMD ["python", "run.py"]
