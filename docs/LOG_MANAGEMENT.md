# 日志管理说明

本项目已配置自动日志轮转，防止日志文件无限增长。

## 日志轮转配置

### Python 日志轮转（已实现）

所有日志模块都已配置使用 `RotatingFileHandler`：

- **单个文件最大大小**: 10MB
- **保留备份文件数**: 5 个
- **总占用空间**: 约 60MB (10MB × 6)

当日志文件达到 10MB 时，会自动轮转：
- `data_update_scheduler.log` (当前)
- `data_update_scheduler.log.1` (备份1)
- `data_update_scheduler.log.2` (备份2)
- ...
- `data_update_scheduler.log.5` (备份5)

## 已配置日志轮转的文件

1. **data_update_scheduler.log** - 数据更新调度器日志
2. **realtime_updater.log** - 实时数据更新器日志
3. **scheduler.log** - 飞书定时通知日志（通过 start.sh 重定向）

## 定期清理旧日志

### 方法 1：手动清理

```bash
# 清理 7 天前的日志（模拟运行，查看会删除什么）
./scripts/clean_logs.sh 7 true

# 实际清理 7 天前的日志
./scripts/clean_logs.sh 7

# 清理 30 天前的日志
./scripts/clean_logs.sh 30
```

### 方法 2：配置定时清理（推荐）

添加到 crontab：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天凌晨 3 点清理 7 天前的日志）
0 3 * * * /home/landasika/etf-predict/scripts/clean_logs.sh 7 >> /home/landasika/etf-predict/logs/clean_logs.log 2>&1
```

### 方法 3：使用 logrotate（系统级别）

创建 `/etc/logrotate.d/etf-predict`：

```
/home/landasika/etf-predict/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 644 landasika landasika
}
```

## 当前日志状态

查看日志占用空间：

```bash
# 查看日志目录大小
du -sh /home/landasika/etf-predict/logs/

# 查看所有日志文件大小
ls -lh /home/landasika/etf-predict/logs/

# 查看备份文件
ls -lh /home/landasika/etf-predict/logs/*.log.*
```

## 修改日志轮转配置

如需调整日志大小限制或备份数量，编辑 `core/logging_config.py`：

```python
logger = setup_logger(
    name='your_logger',
    log_file=log_file,
    max_bytes=10 * 1024 * 1024,  # 修改这个值（默认10MB）
    backup_count=5                # 修改这个值（默认5个）
)
```

## 故障排查

### 问题：日志文件没有轮转

**可能原因**：
1. 日志文件还未达到 10MB
2. 使用了旧的日志配置

**解决方案**：
```bash
# 检查日志文件大小
ls -lh /home/landasika/etf-predict/logs/

# 如果很大，检查是否使用了新的配置
grep "RotatingFileHandler" /home/landasika/etf-predict/core/*.py
```

### 问题：需要手动清理大日志

```bash
# 备份当前日志
cp /home/landasika/etf-predict/logs/data_update_scheduler.log \
   /home/landasika/etf-predict/logs/data_update_scheduler.log.backup

# 清空当前日志
> /home/landasika/etf-predict/logs/data_update_scheduler.log
```

## 最佳实践

1. **定期检查日志大小**：每周检查一次日志目录大小
2. **设置自动清理**：使用 crontab 定期清理旧日志
3. **监控磁盘空间**：使用 `df -h` 检查磁盘使用情况
4. **保留重要日志**：在清理前备份重要的错误日志
