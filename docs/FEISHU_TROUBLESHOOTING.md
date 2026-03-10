# 飞书推送故障排查指南

## 问题描述

远程服务器（192.168.8.30）发送飞书消息时报错：
```json
{"success":false,"message":"发送失败，请检查配置"}
```

## 可能的原因和解决方案

### 1. 配置文件缺失或错误

**检查步骤：**

```bash
# 登录远程服务器
ssh root@192.168.8.30

# 进入项目目录
cd /root/etf-predict

# 检查配置文件
cat conf.json
```

**正确配置示例：**

```json
{
  "feishu": {
    "enabled": true,
    "default_bot": "bot_1",
    "bots": [
      {
        "id": "bot_1",
        "name": "默认机器人",
        "app_id": "cli_a922558c12f95bc9",
        "app_secret": "S835JryPfKQ9HcJpgER0ddWlNjwDqmzQ",
        "chat_id": "oc_13b2ed371174bf3440c8763584341979",
        "enabled": true
      }
    ]
  }
}
```

**解决方案：**

使用同步脚本自动上传正确配置：

```bash
# 在本地服务器（127.0.0.1）运行
./sync_remote_feishu.sh
```

### 2. feishu_bot.py 文件缺失

**检查步骤：**

```bash
# 检查 feishu_bot.py 是否存在
ls -la /root/etf-predict/feishu_bot.py
```

**解决方案：**

如果文件缺失，从本地服务器复制：

```bash
# 在本地服务器运行
scp feishu_bot.py root@192.168.8.30:/root/etf-predict/
```

### 3. Python 模块导入错误

**检查步骤：**

```bash
# 登录远程服务器并测试
ssh root@192.168.8.30

cd /root/etf-predict

# 测试导入
python3 -c "from feishu_bot import FeishuBot; print('OK')"
```

**如果报错：**

- 检查是否在项目根目录
- 检查 feishu_bot.py 文件是否存在
- 检查 Python 版本（需要 Python 3.8+）

### 4. 飞书 API 凭证错误

**验证凭证：**

1. **app_id 格式检查**
   - 必须以 `cli_` 开头
   - 示例：`cli_a922558c12f95bc9`

2. **app_secret 检查**
   - 长度通常在 20-40 字符
   - 不能包含空格或特殊字符

3. **chat_id 检查**
   - 必须以 `oc_` 开头
   - 示例：`oc_13b2ed371174bf3440c8763584341979`

**如何获取正确的凭证：**

1. 登录[飞书开放平台](https://open.feishu.cn/)
2. 创建应用或选择已有应用
3. 获取 App ID 和 App Secret
4. 在飞书群组中添加机器人应用
5. 从群组设置中获取 Chat ID

### 5. 网络连接问题

**检查网络连接：**

```bash
# 测试飞书 API 连通性
curl -I https://open.feishu.cn

# 测试 DNS 解析
nslookup open.feishu.cn

# 测试端口连通性
telnet open.feishu.cn 443
```

**如果网络不通：**

- 检查防火墙设置
- 检查代理配置
- 检查 DNS 设置

### 6. 权限问题

**检查文件权限：**

```bash
# 检查配置文件权限
ls -la conf.json

# 确保文件可读
chmod 644 conf.json

# 确保目录可访问
chmod 755 /root/etf-predict
```

## 诊断工具

### 使用诊断脚本

```bash
# 在远程服务器运行
cd /root/etf-predict
python3 scripts/diagnose_feishu.py
```

脚本会检查：
- ✓ 配置文件是否存在
- ✓ app_id、app_secret、chat_id 是否配置
- ✓ 格式是否正确
- ✓ feishu_bot 模块是否可用
- ✓ 实际发送测试消息

### 手动测试

```bash
# Python 交互式测试
cd /root/etf-predict

python3 << EOF
import asyncio
from core.feishu_notifier import get_feishu_notifier

async def test():
    notifier = get_feishu_notifier()
    result = await notifier.send_message("测试消息", "bot_1")
    print(f"发送结果: {'成功' if result else '失败'}")

asyncio.run(test())
EOF
```

## 查看服务器日志

```bash
# 查看实时日志
tail -f logs/server.log | grep -i "feishu"

# 查看最近的错误
tail -100 logs/server.log | grep -i "error\|feishu"
```

## 常见错误信息

### "发送失败，请检查配置"

- **原因**：配置文件中缺失必需字段
- **解决**：检查 conf.json 是否包含 app_id、app_secret、chat_id

### "飞书机器人配置不完整"

- **原因**：某个机器人的凭证为空
- **解决**：填写完整的机器人配置

### "未找到可用的飞书机器人"

- **原因**：没有启用的机器人
- **解决**：设置 `"enabled": true` 和 `"feishu": {"enabled": true}`

### "获取 tenant_access_token 失败"

- **原因**：app_id 或 app_secret 错误
- **解决**：验证凭证是否正确

### "发送消息失败"

- **原因**：chat_id 错误或机器人不在群组中
- **解决**：
  1. 确保 chat_id 格式正确（oc_ 开头）
  2. 确保机器人已添加到飞书群组
  3. 确保机器人在群组中有发送消息权限

## 快速解决方案

### 方案 1：使用同步脚本（推荐）

```bash
# 在本地服务器运行
./sync_remote_feishu.sh
```

这会自动完成所有配置和测试。

### 方案 2：手动配置

```bash
# 1. SSH 到远程服务器
ssh root@192.168.8.30

# 2. 进入项目目录
cd /root/etf-predict

# 3. 编辑配置文件
nano conf.json

# 4. 运行诊断
python3 scripts/diagnose_feishu.py

# 5. 重启服务器
./start.sh restart
```

## 预防措施

1. **定期备份配置**
   ```bash
   cp conf.json conf.json.backup
   ```

2. **使用版本控制**
   ```bash
   git add conf.json.example
   # 不提交 conf.json（包含敏感信息）
   ```

3. **监控日志**
   ```bash
   # 设置日志监控
   tail -f logs/server.log | grep --line-buffered "飞书\|feishu"
   ```

4. **定期测试**
   - 每次修改配置后运行诊断脚本
   - 定期发送测试消息

## 获取帮助

如果以上方法都无法解决问题：

1. 收集诊断信息：
   ```bash
   python3 scripts/diagnose_feishu.py > diagnose_output.txt 2>&1
   ```

2. 查看完整日志：
   ```bash
   tail -500 logs/server.log > server_log.txt
   ```

3. 提供以下信息：
   - 服务器 IP 和操作系统版本
   - Python 版本 (`python3 --version`)
   - 诊断输出
   - 相关日志片段

## 联系方式

- 项目文档：`docs/FEISHU_INTEGRATION.md`
- API 文档：http://192.168.8.30:8000/docs
- 配置示例：`conf.json.example`
