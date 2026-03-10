# 🚀 ETF预测系统 - 启动脚本使用指南

## 快速开始

### 后台启动（推荐）
```bash
./start.sh daemon
```
服务器将在后台运行，关闭终端窗口后服务仍继续运行。

### 前台启动
```bash
./start.sh start
```
或简单执行：
```bash
./start.sh
```

### 查看状态
```bash
./start.sh status
```

### 停止服务
```bash
./start.sh stop
```
或
```bash
./stop.sh
```

### 重启服务
```bash
./start.sh restart
```

### 查看日志
```bash
./start.sh logs
```

实时查看日志：
```bash
tail -f logs/server.log
```

---

## 完整命令列表

| 命令 | 说明 | 示例 |
|------|------|------|
| `start` / `run` | 前台启动 | `./start.sh start` |
| `daemon` / `start-daemon` | 后台启动 | `./start.sh daemon` |
| `background` / `bg` | 后台启动（简写） | `./start.sh bg` |
| `stop` | 停止服务 | `./start.sh stop` |
| `restart` | 重启服务 | `./start.sh restart` |
| `status` | 查看状态 | `./start.sh status` |
| `logs` | 查看日志 | `./start.sh logs` |
| `help` | 显示帮助 | `./start.sh help` |

---

## 常见使用场景

### 场景1: 开发调试
```bash
# 前台启动，实时查看日志
./start.sh start

# 或使用 Python 直接启动
python run.py
```

### 场景2: 生产环境部署
```bash
# 后台启动
./start.sh daemon

# 查看状态
./start.sh status

# 查看日志
./start.sh logs
```

### 场景3: 更新代码后重启
```bash
# 修改代码后，重启服务
./start.sh restart

# 或者先停止再启动
./start.sh stop
./start.sh daemon
```

### 场景4: 关闭终端前后台启动
```bash
# 关闭终端前，先后台启动
./start.sh daemon

# 然后可以安全关闭终端
exit
```

---

## 进程管理

### PID文件
- 位置: `etf-predict.pid`
- 作用: 存储服务器进程ID
- 自动管理: 启动时创建，停止时删除

### 日志文件
- 位置: `logs/server.log`
- 内容: 服务器输出日志
- 查看方法: `tail -f logs/server.log`

### 查看进程
```bash
# 使用 start.sh
./start.sh status

# 或使用 ps 命令
ps aux | grep python

# 或查看 PID 文件
cat etf-predict.pid
```

### 停止进程
```bash
# 方法1: 使用 start.sh
./start.sh stop

# 方法2: 使用 stop.sh
./stop.sh

# 方法3: 手动停止
kill $(cat etf-predict.pid)

# 方法4: 强制停止
kill -9 $(cat etf-predict.pid)
```

---

## 开机自启动（可选）

### 使用 systemd（推荐）

创建服务文件 `/etc/systemd/system/etf-predict.service`:

```ini
[Unit]
Description=ETF预测系统
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/landasika/etf-predict
ExecStart=/home/landasika/etf-predict/start.sh daemon
ExecStop=/home/landasika/etf-predict/start.sh stop
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable etf-predict
sudo systemctl start etf-predict
```

管理服务：
```bash
sudo systemctl start etf-predict   # 启动
sudo systemctl stop etf-predict    # 停止
sudo systemctl restart etf-predict  # 重启
sudo systemctl status etf-predict   # 状态
```

---

## 故障排除

### 问题1: 端口被占用
**症状**: 启动失败，提示端口8000被占用

**解决方案**:
```bash
# 查看占用端口的进程
lsof -i :8000

# 停止占用端口的进程
./start.sh stop

# 或者使用 stop.sh
./stop.sh
```

### 问题2: 后台启动后无法访问
**症状**: 后台启动成功，但无法访问页面

**解决方案**:
```bash
# 检查状态
./start.sh status

# 查看日志
./start.sh logs

# 或实时查看日志
tail -f logs/server.log
```

### 问题3: PID文件损坏
**症状**: 无法停止服务，提示进程不存在

**解决方案**:
```bash
# 清理PID文件
rm -f etf-predict.pid

# 查找并手动停止进程
ps aux | grep "python.*run.py"
kill <PID>
```

### 问题4: 多个实例运行
**症状**: 启动时提示已在运行

**解决方案**:
```bash
# 检查状态
./start.sh status

# 停止旧实例
./start.sh stop

# 或使用 stop.sh（更彻底）
./stop.sh

# 重新启动
./start.sh daemon
```

---

## 日志管理

### 查看实时日志
```bash
tail -f logs/server.log
```

### 查看最近日志
```bash
tail -50 logs/server.log
```

### 搜索错误日志
```bash
grep -i error logs/server.log
```

### 清理日志
```bash
# 清空日志文件
> logs/server.log

# 或清理所有日志
rm logs/*.log
```

---

## 性能监控

### 实时监控
```bash
# 查看状态
watch -n 1 ./start.sh status

# 查看资源使用
watch -n 1 'ps aux | grep python'
```

### 内存使用
```bash
# 查看进程内存
ps aux | grep "python.*run.py" | awk '{print $6}'

# 转换为MB
ps aux | grep "python.*run.py" | awk '{mem=$6/1024; printf "%.2f MB\n", mem}'
```

---

## 总结

### 推荐使用方式

**开发环境**:
```bash
./start.sh start  # 前台启动，方便调试
```

**生产环境**:
```bash
./start.sh daemon  # 后台启动，关闭终端不影响
```

### 完整工作流程

```bash
# 1. 后台启动
./start.sh daemon

# 2. 查看状态
./start.sh status

# 3. 查看日志
./start.sh logs

# 4. 修改代码后重启
./start.sh restart

# 5. 停止服务
./start.sh stop
```

---

**最后更新**: 2026-03-10
**版本**: v2.0
