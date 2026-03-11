# 远程服务器飞书报告0持仓问题 - 快速修复指南

## 问题

远程服务器（192.168.8.30）通过 `git pull` 同步代码后，飞书报告显示：
```
| 有持仓ETF | 0个 | 昨日实际有持仓 |
| 昨日总仓位 | 0仓 | 实际持仓总和 |
| 昨日总资金 | ¥0 | 持仓总价值（200元/仓）|
```

## 根本原因

数据库中没有持仓数据。报告生成器需要持仓信息（`previous_positions_used`）才能正确显示统计。

## 快速修复（5分钟）

### 步骤1：SSH到远程服务器

```bash
ssh root@192.168.8.30
# 输入密码：Wyw80702002

cd /root/etf-predict
```

### 步骤2：运行诊断

```bash
python3 scripts/diagnose_holdings.py
```

这会告诉你：
- 数据库是否有持仓数据
- API是否正常工作
- 报告能否正常生成

### 步骤3：添加测试数据

```bash
python3 scripts/quick_test_feishu.py
```

这个脚本会：
- ✅ 为10-15个ETF添加模拟持仓（3-10仓）
- ✅ 生成随机涨跌幅数据
- ✅ 发送测试报告到飞书
- ✅ 保留数据供后续测试

### 步骤4：验证结果

检查飞书是否收到报告，应该显示类似：
```
| 有持仓ETF | 10个 | 昨日实际有持仓 |
| 昨日总仓位 | 73仓 | 实际持仓总和 |
| 昨日总资金 | ¥14,600 | 持仓总价值（200元/仓）|
```

## 如果需要清除测试数据

```bash
python3 scripts/clear_mock_positions.py
```

## 永久解决方案（获取真实持仓）

测试数据只是临时的。要获取真实的持仓数据，需要运行策略回测：

### 方案A：通过Web界面

1. 确保API服务器运行中：
   ```bash
   python run.py
   ```

2. 访问回测页面：
   ```
   http://192.168.8.30:8000/backtest
   ```

3. 选择ETF和策略，运行回测

### 方案B：通过API

```bash
curl -X POST http://127.0.0.1:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{
    "etf_code": "510330.SH",
    "strategy": "macd_aggressive",
    "start_date": "2024-01-01",
    "end_date": "2025-12-31"
  }'
```

## 常见错误排查

### 错误1：API连接失败

```
❌ 连接失败（API服务器可能未运行）
```

**解决**：
```bash
# 启动API服务器
python run.py

# 或者后台运行
nohup python run.py > logs/server.log 2>&1 &
```

### 错误2：无法加载自选列表

```
❌ 无法加载自选列表
```

**解决**：
```bash
# 检查文件是否存在
ls -la data/watchlist_etfs.json

# 如果不存在，从API创建
curl http://127.0.0.1:8000/api/watchlist/init
```

### 错误3：飞书消息发送失败

**解决**：运行飞书配置诊断
```bash
python3 scripts/diagnose_feishu.py
```

## 完整诊断流程

如果快速修复不工作，运行完整诊断：

```bash
# 1. 检查代码版本
git log -1 --oneline

# 2. 检查飞书配置
python3 scripts/diagnose_feishu.py

# 3. 检查持仓数据
python3 scripts/diagnose_holdings.py

# 4. 查看服务器日志
tail -50 logs/server.log | grep -i "error\|feishu"
```

## 技术说明

### 持仓数据来源

报告生成器按以下优先级获取持仓数据：

1. **API接口** `/api/watchlist/batch-signals`
   - 字段：`latest_data.previous_positions_used`
   - 来源：策略回测结果

2. **数据库解析** `etf_basic.extname`
   - 格式：`ETF名称 [X仓]`
   - 用于测试和临时数据

### 为什么git pull后显示0？

因为 `git pull` 只同步代码，不同步数据库数据：
- ✅ 代码文件（.py, .sh, .md等）
- ❌ 数据库文件（data/etf.db）
- ❌ 配置文件（conf.json，如果在.gitignore中）

## 下次更新代码时

为了避免每次更新后都显示0持仓：

1. **在远程服务器运行回测**（一次性）
2. **或使用测试数据脚本**（每次git pull后运行）
   ```bash
   python3 scripts/quick_test_feishu.py
   ```

## 相关文档

- 详细故障排查：`docs/FEISHU_TROUBLESHOOTING.md`
- 飞书集成文档：`docs/FEISHU_INTEGRATION.md`
- API文档：http://192.168.8.30:8000/docs

## 快速命令参考

```bash
# 诊断
python3 scripts/diagnose_holdings.py

# 快速测试（添加数据+发送报告）
python3 scripts/quick_test_feishu.py

# 清除测试数据
python3 scripts/clear_mock_positions.py

# 重启API服务器
./start.sh restart

# 查看日志
tail -f logs/server.log
```
