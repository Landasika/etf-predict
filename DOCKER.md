# ETF预测系统 - Docker 部署指南

## 🚀 构建优化

**已配置国内镜像源，构建速度更快！**

- ✅ APT 源：阿里云镜像（mirrors.aliyun.com）
- ✅ PyPI 源：清华大学镜像（pypi.tuna.tsinghua.edu.cn）
- ✅ 多阶段构建：减小最终镜像体积
- ✅ 无需额外配置，开箱即用

## 快速开始

### 1. 配置环境变量

```bash
# 复制环境变量模板
cp .env.docker.example .env

# 编辑 .env 文件，填写必要的配置
# 必须配置：TUSHARE_TOKEN
```

### 2. 构建并启动

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 3. 访问服务

- **API 地址**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 常用命令

### 服务管理

```bash
# 启动服务
docker-compose up -d

# 停止服务
docker-compose stop

# 重启服务
docker-compose restart

# 停止并删除容器
docker-compose down

# 查看日志
docker-compose logs -f etf-predict

# 查看容器状态
docker-compose ps
```

### 数据管理

```bash
# 进入容器
docker-compose exec etf-predict bash

# 初始化数据库
docker-compose exec etf-predict python init_db.py

# 下载数据
docker-compose exec etf-predict python scripts/download_etf_data.py

# 查看数据统计
docker-compose exec etf-predict python scripts/check_data.py
```

### 更新部署

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

## 环境变量说明

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `TUSHARE_TOKEN` | ✅ | - | Tushare API Token |
| `TUSHARE_PROXY_URL` | ❌ | - | Tushare 代理地址 |
| `API_HOST` | ❌ | 0.0.0.0 | API 监听地址 |
| `API_PORT` | ❌ | 8000 | API 端口 |
| `AUTH_KEY` | ❌ | admin123 | 认证密钥 |
| `UPDATE_SCHEDULE_ENABLED` | ❌ | true | 是否启用自动更新 |
| `UPDATE_SCHEDULE_TIME` | ❌ | 15:05 | 更新时间 |

## 数据持久化

Docker volumes 用于持久化数据：

- `etf-data` - SQLite 数据库
- `etf-logs` - 日志文件
- `etf-weights` - 优化权重
- `etf-config` - 配置文件

### 备份数据

```bash
# 备份数据库
docker run --rm -v etf-predict_etf-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/etf-data-backup.tar.gz /data

# 恢复数据库
docker run --rm -v etf-predict_etf-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/etf-data-backup.tar.gz -C /
```

## 性能优化

### 资源限制

编辑 `docker-compose.yml`，添加资源限制：

```yaml
services:
  etf-predict:
    # ... 其他配置
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### 日志管理

日志文件大小限制已在 `docker-compose.yml` 中配置：
- 单个文件最大 10MB
- 最多保留 3 个文件

## 故障排查

### 容器无法启动

```bash
# 查看详细日志
docker-compose logs etf-predict

# 检查配置
docker-compose config
```

### 数据连接失败

```bash
# 检查 volume 是否正常
docker volume ls | grep etf

# 检查数据库文件
docker-compose exec etf-predict ls -lh data/
```

### 权限问题

容器使用非特权用户 `appuser` 运行，如需修改权限：

```bash
# 在容器内修改
docker-compose exec etf-predict chown -R appuser:appuser /app
```

## 生产环境建议

1. **使用强密码**
   ```bash
   # 生成随机密钥
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **配置 HTTPS**
   - 使用 Nginx 反向代理
   - 配置 SSL 证书

3. **定期备份**
   - 设置 cron 任务自动备份 volumes
   - 保留最近 7 天的备份

4. **监控告警**
   - 配置健康检查告警
   - 监控容器资源使用
