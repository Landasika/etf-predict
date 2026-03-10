# JSON 配置文件说明

ETF 预测系统现在使用 JSON 文件来存储所有配置，这些配置在服务器重启后会保持不变。

## 配置文件

### 1. `config.json` - 系统主配置

包含所有系统核心配置：

```json
{
  "database": {
    "path": "data/etf.db"        // SQLite 数据库路径
  },
  "watchlist": {
    "path": "data/watchlist_etfs.json"  // 自选 ETF 列表路径
  },
  "weights": {
    "path": "optimized_weights"  // 权重文件目录
  },
  "api": {
    "host": "0.0.0.0",           // API 服务器监听地址
    "port": 8000,                // API 服务器端口
    "title": "ETF预测系统API",
    "version": "1.0.0"
  },
  "auth": {
    "session_secret_key": "...", // 会话密钥（建议使用随机字符串）
    "auth_key": "admin123",      // 登录密码
    "max_login_attempts": 5,     // 最大登录尝试次数
    "login_attempt_window": 300, // 登录尝试时间窗口（秒）
    "lockout_duration": 900      // 账户锁定时长（秒）
  },
  "tushare": {
    "token": ""                  // Tushare API Token
  },
  "minishare": {
    "token": "..."               // Minishare API Token
  },
  "strategies": {
    "macd_aggressive": "MACD激进策略",
    "optimized_t_trading": "优化做T策略",
    "multifactor": "多因子量化策略"
  }
}
```

### 2. `conf.json` - 飞书通知配置

包含飞书机器人配置：

```json
{
  "feishu": {
    "enabled": false,            // 是否启用飞书通知
    "default_bot": "bot_1",      // 默认机器人 ID
    "bots": [                    // 飞书机器人列表
      {
        "id": "bot_1",
        "name": "默认机器人",
        "app_id": "cli_...",
        "app_secret": "...",
        "chat_id": "oc_...",
        "enabled": true
      }
    ],
    "notifications": {           // 通知类型开关
      "signal_alerts": true,     // 策略信号提醒
      "data_updates": false,     // 数据更新通知
      "backtest_complete": false,// 回测完成通知
      "error_alerts": true       // 错误告警
    }
  }
}
```

## 使用方式

### 通过 Web 界面配置

1. 访问系统设置页面：`http://127.0.0.1:8000/settings`
2. 修改相应配置项
3. 点击"保存设置"按钮
4. 配置会自动保存到对应的 JSON 文件

### 通过 API 配置

**获取系统配置：**
```bash
curl http://127.0.0.1:8000/api/config
```

**更新系统配置：**
```bash
curl -X POST http://127.0.0.1:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{
    "tushare": {"token": "your_token"},
    "auth": {"auth_key": "new_password"}
  }'
```

**重新加载配置（无需重启）：**
```bash
curl -X POST http://127.0.0.1:8000/api/config/reload
```

**获取飞书配置：**
```bash
curl http://127.0.0.1:8000/api/feishu/config
```

**更新飞书配置：**
```bash
curl -X POST http://127.0.0.1:8000/api/feishu/config \
  -H "Content-Type: application/json" \
  -d '{
    "feishu": {
      "enabled": true,
      "bots": [...]
    }
  }'
```

## 首次配置

### 1. 复制示例文件

```bash
cp config.json.example config.json
cp conf.json.example conf.json
```

### 2. 修改配置文件

使用文本编辑器打开 `config.json` 和 `conf.json`，填入实际配置：

**重要配置项：**
- `auth.session_secret_key`: 生成一个随机字符串
- `auth.auth_key`: 设置管理员登录密码
- `tushare.token`: 填入 Tushare Token（可选）
- `minishare.token`: 填入 Minishare Token（必需）

### 3. 启动服务器

```bash
./start.sh daemon
```

## 安全建议

1. **不要将 `config.json` 和 `conf.json` 提交到 Git**
   - 这两个文件已添加到 `.gitignore`
   - 仅提交 `*.example` 文件

2. **使用强密码**
   - 定期更换 `auth.auth_key`
   - 使用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成随机密钥

3. **保护敏感信息**
   - 生产环境使用 HTTPS
   - 限制配置文件访问权限（chmod 600 config.json conf.json）

## 配置热重载

修改配置后，无需重启服务器即可生效：

```bash
# 重新加载配置
curl -X POST http://127.0.0.1:8000/api/config/reload
```

部分配置（如 API 监听地址和端口）修改后仍需重启服务器：
```bash
./start.sh restart
```

## 故障排查

### 配置未生效
1. 检查 JSON 格式是否正确
2. 查看服务器日志：`./start.sh logs`
3. 确认文件权限：`ls -la config.json conf.json`

### 无法登录
1. 检查 `config.json` 中的 `auth.auth_key`
2. 尝试重置密码为默认值 `admin123`
3. 清除浏览器缓存并重新登录

### 飞书推送不工作
1. 确认 `conf.json` 中的机器人配置完整
2. 检查 `feishu.enabled` 是否为 `true`
3. 在设置页面测试飞书连接
