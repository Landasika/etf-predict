# 远程服务器0持仓问题 - 使用API数据的正确方法

## 问题本质

报告生成器应该从 **API** 获取持仓数据：
- API端点：`/api/watchlist/batch-signals`
- 字段：`latest_data.previous_positions_used`

## 诊断步骤

### 在远程服务器（192.168.8.30）上执行：

```bash
# 1. 测试API数据
python3 scripts/test_report_api.py
```

这个脚本会：
- ✅ 测试API是否正常工作
- ✅ 显示API返回的持仓数据
- ✅ 测试报告生成器是否正确使用API数据

### 可能的结果：

#### 结果1：API连接失败

```
❌ 所有API连接失败
请确保API服务器正在运行: python run.py
```

**解决**：
```bash
cd /root/etf-predict
python run.py &
```

#### 结果2：API返回0持仓

```
⚠️  API返回的所有ETF持仓都是0
需要运行回测来生成持仓数据
```

**解决**：运行回测生成真实持仓数据
```bash
# 访问回测页面
http://192.168.8.30:8001/backtest

# 或通过API调用
curl -X POST http://127.0.0.1:8001/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"etf_code": "510330.SH", "strategy": "macd_aggressive"}'
```

#### 结果3：报告显示0但API有数据

```
✅ API数据正常
❌ 报告生成异常
问题：报告生成器没有正确使用API数据
```

**这不应该发生**，因为我已经修改了代码让它优先使用API数据。

## 代码修改

我修改了 `core/feishu_report.py`：

### 之前：
```python
api_url = "http://127.0.0.1:8000/api/watchlist/batch-signals"
```
- 只尝试8000端口
- 失败后fallback到数据库

### 现在：
```python
api_urls = [
    "http://127.0.0.1:8001/api/watchlist/batch-signals",  # 优先8001
    "http://127.0.0.1:8000/api/watchlist/batch-signals"   # 备用8000
]
```
- 尝试多个端口
- 只有所有API都失败才fallback到数据库
- 添加了详细的日志

## 数据流向

```
回测数据 → 数据库 → API读取 → 报告生成器 → 飞书
   ↓         ↓        ↓          ↓          ↓
 (真实)    (存储)   (JSON)     (使用)     (发送)
```

### 为什么本地显示93仓？
- 本地运行过回测
- 数据库有回测结果
- API读取到数据
- 报告显示93仓 ✅

### 为什么远程显示0仓？
- 远程没运行过回测
- 数据库无回测结果
- API返回0
- 报告显示0仓 ❌

## 解决方案

### 方案1：运行回测（推荐）

这是标准做法，获取真实的持仓数据：

```bash
# 在远程服务器
cd /root/etf-predict

# 启动API服务器
python run.py &

# 访问回测页面
# http://192.168.8.30:8001/backtest

# 选择几个ETF运行回测
# 回测完成后，API会返回持仓数据
```

### 方案2：手动测试API

```bash
# 测试API是否返回持仓数据
curl http://127.0.0.1:8001/api/watchlist/batch-signals | jq '.data[0].latest_data.previous_positions_used'
```

如果返回 `0`，说明需要运行回测。
如果返回数字（如 `5`），说明API正常。

## 完整诊断命令

```bash
# 在远程服务器
cd /root/etf-predict

# 1. 确保API服务器运行
ps aux | grep "python run.py"
# 如果没有运行，启动它：
python run.py &

# 2. 测试API数据
python3 scripts/test_report_api.py

# 3. 如果API返回0，运行回测
# 访问 http://192.168.8.30:8001/backtest

# 4. 重新测试
python3 scripts/test_report_api.py
```

## 关键点

1. **报告不读数据库**：报告生成器优先从API获取数据
2. **API读数据库**：API从数据库的回测结果中读取持仓
3. **需要回测数据**：没有回测就没有持仓数据
4. **git pull不同步数据**：只同步代码，不同步数据库

## 常见误区

❌ **错误**：在数据库 `extname` 字段添加模拟数据
- 这只是fallback方案
- 不是标准做法
- API会返回 `previous_positions_used=0`

✅ **正确**：运行回测生成真实持仓数据
- 这是标准流程
- API会返回真实的 `previous_positions_used`
- 报告会正确显示

## 总结

| 操作 | 结果 | 推荐度 |
|------|------|--------|
| 运行回测 | API返回真实持仓 | ⭐⭐⭐⭐⭐ |
| 修改数据库extname | API仍返回0 | ⭐ |
| 测试脚本添加数据 | 临时测试用 | ⭐⭐ |

**正确流程**：
```
运行回测 → 数据库有数据 → API返回持仓 → 报告显示正确
```
