# 每日自动更新数据 - 使用指南

## 功能说明

这个脚本会自动：
1. ✅ 下载最新的ETF日线数据（增量更新）
2. ✅ 更新SQLite数据库
3. ✅ 清理过期缓存
4. ✅ 记录详细日志
5. ✅ 支持定时任务

## 快速开始

### 方法1: 手动更新（推荐测试）

```bash
cd /home/landasika/etf-predict
python scripts/auto_update_data.py --once
```

### 方法2: 使用 cron 定时任务（推荐）

#### 步骤1: 编辑crontab

```bash
crontab -e
```

#### 步骤2: 添加以下内容

```bash
# 每个交易日 15:05 自动更新数据
5 15 * * 1-5 cd /home/landasika/etf-predict && /home/landasika/anaconda3/bin/python scripts/auto_update_data.py --once >> /home/landasika/etf-predict/logs/cron.log 2>&1
```

#### 步骤3: 保存并退出

- 编辑器是nano: 按 `Ctrl+O` 保存，`Ctrl+X` 退出
- 编辑器是vim: 按 `:wq` 保存退出

#### 步骤4: 查看定时任务

```bash
crontab -l
```

### 方法3: 使用 systemd 服务（适合服务器）

#### 步骤1: 修改服务文件

```bash
cd /home/landasika/etf-predict/scripts
sed -i 's/YOUR_USERNAME/landasika/g' etf-auto-update.service
```

#### 步骤2: 安装服务

```bash
sudo cp etf-auto-update.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable etf-auto-update.service
sudo systemctl start etf-auto-update.service
```

#### 步骤3: 查看服务状态

```bash
sudo systemctl status etf-auto-update.service
```

#### 步骤4: 查看日志

```bash
sudo journalctl -u etf-auto-update.service -f
```

#### 停止/重启服务

```bash
# 停止
sudo systemctl stop etf-auto-update.service

# 重启
sudo systemctl restart etf-auto-update.service
```

### 方法4: 使用Python调度器（测试用）

```bash
cd /home/landasika/etf-predict
python scripts/auto_update_data.py --schedule
```

按 `Ctrl+C` 停止。

## 日志查看

### 查看自动更新日志

```bash
tail -f /home/landasika/etf-predict/logs/auto_update.log
```

### 查看最近20行

```bash
tail -n 20 /home/landasika/etf-predict/logs/auto_update.log
```

## 验证更新是否成功

### 方法1: 查看日志

日志中应该看到：
```
✅ 自动更新完成！
```

### 方法2: 检查数据库最新日期

```bash
python3 -c "
from core.database import get_latest_data_date
from datetime import datetime

data_date = get_latest_data_date()
today = datetime.now().strftime('%Y%m%d')

print(f'数据库最新日期: {data_date}')
print(f'今天日期: {today}')

if data_date == today:
    print('✅ 数据已是最新')
else:
    print(f'⚠️ 数据有{ (datetime.strptime(today, \"%Y%m%d\") - datetime.strptime(data_date, \"%Y%m%d\")).days }天延迟')
"
```

### 方法3: 查看Web界面

打开浏览器访问 `http://127.0.0.1:8000`，查看"📅 数据日期"显示的日期。

## 配置说明

### 修改更新时间

编辑 `scripts/auto_update_data.py` 中的配置：

```python
# 收盘时间（下午3点）
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 5

# 等待时间（收盘后多少分钟开始更新）
WAIT_MINUTES_AFTER_CLOSE = 10
```

### 修改Tushare Token

编辑 `config.py`：

```python
TUSHARE_TOKEN = '你的Token'
```

获取Token: https://tushare.pro/register

## 故障排除

### 问题1: 提示TUSHARE_TOKEN未配置

**解决方法**:
```bash
# 编辑config.py
vim config.py

# 添加你的Token
TUSHASE_TOKEN = '你的Token'
```

### 问题2: cron任务没有执行

**检查方法**:
```bash
# 查看cron日志
grep CRON /var/log/syslog | tail -20

# 查看脚本日志
tail -f logs/auto_update.log
```

**常见原因**:
1. 路径错误：确保使用绝对路径
2. Python路径错误：使用 `which python` 查看完整路径
3. 权限问题：确保脚本有执行权限

### 问题3: 更新失败，显示"无新数据"

**原因**:
- 可能周末或节假日，没有新数据
- 数据已经是最新的

**解决方法**:
这是正常的，等待下一个交易日即可。

### 问题4: 更新后Web界面显示旧数据

**原因**: 浏览器缓存

**解决方法**:
1. 强制刷新：`Ctrl + Shift + R`
2. 点击"刷新页面"按钮
3. 清理批量缓存后会自动刷新

## 高级配置

### 仅更新自选列表中的ETF

脚本默认从 `data/watchlist_etfs.json` 读取需要更新的ETF列表。

### 自定义更新时间（cron示例）

```bash
# 每天早上8点更新（前一天收盘后的数据）
0 8 * * 1-5 cd /home/landasika/etf-predict && python scripts/auto_update_data.py >> logs/cron.log 2>&1

# 每天晚上8点更新
0 20 * * * cd /home/landasika/etf-predict && python scripts/auto_update_data.py >> logs/cron.log 2>&1

# 每小时检查一次（有新数据就更新）
0 * * * 1-5 cd /home/landasika/etf-predict && python scripts/auto_update_data.py >> logs/cron.log 2>&1
```

## 推荐配置

**对于个人用户**: 使用 cron 定时任务
**对于服务器**: 使用 systemd 服务
**对于测试**: 手动运行或使用Python调度器

## 更新日志

- **2026-02-17**: 初始版本
  - 支持增量更新
  - 自动清理缓存
  - 多种定时方式
  - 详细日志记录
