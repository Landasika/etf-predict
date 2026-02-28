# 部署指南

本文档介绍如何在不同环境下部署 ETF 策略回测系统。

## 目录

- [开发环境](#开发环境)
- [生产环境](#生产环境)
- [Docker 部署](#docker-部署)
- [系统配置](#系统配置)

---

## 开发环境

### 1. 准备工作

```bash
# 克隆项目
git clone <repository-url>
cd etf-predict

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 数据准备

#### 使用现有数据库（推荐）

```bash
# 将已有数据库复制到 data 目录
cp /path/to/etf.db data/
```

#### 从 Tushare 下载

```bash
# 1. 注册 Tushare 账号：https://tushare.pro
# 2. 编辑 config.py，设置 TUSHARE_TOKEN
# 3. 运行下载脚本
python scripts/download_etf_data.py
```

### 3. 初始化数据库

```bash
python init_db.py
```

### 4. 启动服务

```bash
# 开发模式（热重载）
uvicorn api.main:app --host 0.0.0.0 --port 8001 --reload

# 或使用启动脚本
python run.py
```

访问 http://127.0.0.1:8001

---

## 生产环境

### 1. 使用 Gunicorn + Uvicorn

```bash
# 安装 gunicorn
pip install gunicorn

# 启动服务（4个worker进程）
gunicorn api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8001 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
```

### 2. 使用 Systemd（Linux）

创建服务文件 `/etc/systemd/system/etf-predict.service`：

```ini
[Unit]
Description=ETF Predict Service
After=network.target

[Service]
Type=notify
User=your_user
Group=your_group
WorkingDirectory=/path/to/etf-predict
Environment="PATH=/path/to/etf-predict/venv/bin"
ExecStart=/path/to/etf-predict/venv/bin/gunicorn \
    api.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8001
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
# 重载 systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start etf-predict

# 开机自启
sudo systemctl enable etf-predict

# 查看状态
sudo systemctl status etf-predict

# 查看日志
sudo journalctl -u etf-predict -f
```

### 3. 使用 Nginx 反向代理

创建 Nginx 配置 `/etc/nginx/sites-available/etf-predict`：

```nginx
server {
    listen 80;
    server_name your_domain.com;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/etf-predict/static;
    }

    location /media {
        alias /path/to/etf-predict/media;
    }
}
```

启用配置：

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/etf-predict /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```

---

## Docker 部署

### 1. 创建 Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 暴露端口
EXPOSE 8001

# 启动命令
CMD ["gunicorn", "api.main:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8001"]
```

### 2. 创建 docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8001:8001"
    volumes:
      - ./data:/app/data
      - ./optimized_weights:/app/optimized_weights
    environment:
      - PYTHONUNBUFFERED=1
    restart: always
```

### 3. 构建和运行

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

---

## 系统配置

### 环境变量

创建 `.env` 文件（不要提交到版本控制）：

```bash
# 服务器配置
API_HOST=0.0.0.0
API_PORT=8001

# 数据库配置
DATABASE_PATH=data/etf.db

# Tushare 配置
TUSHARE_TOKEN=your_token_here

# 缓存配置
ENABLE_CACHE=true
```

### 修改 config.py

```python
# 生产环境建议配置
DEBUG = False
API_HOST = '0.0.0.0'
API_PORT = 8001
DATABASE_PATH = '/var/lib/etf-predict/data/etf.db'
WATCHLIST_PATH = '/var/lib/etf-predict/data/watchlist_etfs.json'
WEIGHTS_PATH = '/var/lib/etf-predict/optimized_weights'
```

---

## 性能优化

### 1. 数据库优化

```bash
# 创建索引
python scripts/create_indexes.py
```

### 2. 缓存配置

```python
# config.py
CACHE_ENABLED = True
CACHE_TTL = 3600  # 缓存1小时
```

### 3. Worker 进程数调整

```bash
# 根据 CPU 核心数调整
CPU_CORES=$(nproc)
WORKERS=$((CPU_CORES * 2 + 1))

gunicorn api.main:app \
    --workers $WORKERS \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8001
```

---

## 监控和日志

### 日志配置

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/etf-predict/app.log'),
        logging.StreamHandler()
    ]
)
```

### 健康检查

```bash
# 添加健康检查端点
# GET /api/health
```

---

## 备份和恢复

### 数据库备份

```bash
# 备份数据库
cp data/etf.db data/backup/etf_$(date +%Y%m%d).db

# 备份配置
cp data/watchlist_etfs.json data/backup/watchlist_$(date +%Y%m%d).json
```

### 自动备份脚本

```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/path/to/backup"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR

# 备份数据库
cp data/etf.db $BACKUP_DIR/etf_$DATE.db

# 备份配置
cp data/watchlist_etfs.json $BACKUP_DIR/watchlist_$DATE.json

# 保留最近30天的备份
find $BACKUP_DIR -name "etf_*.db" -mtime +30 -delete
find $BACKUP_DIR -name "watchlist_*.json" -mtime +30 -delete
```

添加到 crontab：

```bash
# 每天凌晨2点自动备份
0 2 * * * /path/to/backup.sh
```

---

## 故障排除

### 服务无法启动

```bash
# 检查端口占用
lsof -i :8001

# 检查日志
tail -f /var/log/etf-predict/app.log

# 检查数据库权限
ls -la data/etf.db
```

### 数据库连接错误

```bash
# 检查数据库文件
file data/etf.db

# 修复数据库
sqlite3 data/etf.db "PRAGMA integrity_check;"
```

### 内存不足

```bash
# 减少 worker 数量
gunicorn api.main:app --workers 2 ...

# 或增加服务器内存
```

---

## 安全建议

1. **不要在代码中硬编码 Token**：使用环境变量或配置文件
2. **启用 HTTPS**：使用 Let's Encrypt 免费证书
3. **设置防火墙**：只开放必要端口
4. **定期更新依赖**：`pip install --upgrade -r requirements.txt`
5. **限制访问**：配置 Nginx IP 白名单

---

## 更新部署

```bash
# 拉取最新代码
git pull

# 激活虚拟环境
source venv/bin/activate

# 更新依赖
pip install -r requirements.txt

# 重启服务
sudo systemctl restart etf-predict
```

---

## 联系支持

如有问题，请提交 Issue 或联系开发团队。
