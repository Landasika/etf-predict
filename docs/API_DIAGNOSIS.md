# 远程服务器0持仓问题 - 正确诊断流程

## 问题回顾

- **本地**：显示93仓 ✅
- **远程**（192.168.8.30）：显示0仓 ❌
- 已通过 `git pull` 同步代码

## 核心问题

报告生成器从 **API** 获取持仓数据，不是直接读数据库！

API端点：`/api/watchlist/batch-signals`

关键字段：`latest_data.previous_positions_used`

## 正确的诊断步骤

### 步骤1：SSH到远程服务器

```bash
ssh root@192.168.8.30
cd /root/etf-predict
```

### 步骤2：测试API是否返回持仓数据

```bash
python3 scripts/test_api_holdings.py
```

这个脚本会：
- 测试API连接（端口8000和8001）
- 显示前10个ETF的 `previous_positions_used`
- 统计有持仓的ETF数量

### 步骤3：根据结果判断

#### 情况A：API连接失败

```
❌ 连接失败（API服务器可能未运行）
```

**解决**：启动API服务器
```bash
python run.py
```

#### 情况B：API返回0持仓

```
⚠️  API连接成功，但所有ETF的 previous_positions_used 都是 0
```

**原因**：远程服务器没有回测数据

**解决**：运行回测
```bash
# 方式1：通过Web界面
# 访问 http://192.168.8.30:8000/backtest

# 方式2：通过API
curl -X POST http://127.0.0.1:8000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"etf_code": "510330.SH", "strategy": "macd_aggressive"}'
```

#### 情况C：API返回正确数据

```
✅ API返回了正确的持仓数据
  有持仓ETF: 10个
  总仓位: 93仓
```

**说明**：API正常，问题在报告生成器

**解决**：检查报告生成逻辑
```bash
# 手动测试报告生成
python3 -c "
from core.feishu_report import generate_etf_operation_report
report = generate_etf_operation_report()
print(report[:500])
"
```

## 数据流向

```
回测结果 → 数据库 → API → 报告生成器 → 飞书
   ↓           ↓       ↓         ↓           ↓
 (positions)  (读取)  (JSON)   (生成)     (发送)
```

### 为什么本地有数据？

- 本地运行过回测
- 数据库中有回测结果
- API能读取到 `previous_positions_used`

### 为什么远程显示0？

- 远程服务器没有回测数据
- API返回 `previous_positions_used = 0`
- 报告显示0仓

## 完整解决方案

### 方案1：运行回测（推荐，获取真实数据）

```bash
# 1. 启动API服务器
python run.py &

# 2. 等待服务器启动
sleep 5

# 3. 测试API是否正常
python3 scripts/test_api_holdings.py

# 4. 访问回测页面
# http://192.168.8.30:8000/backtest
# 运行几个ETF的回测

# 5. 重新测试报告
python3 scripts/test_api_holdings.py
```

### 方案2：使用测试脚本（临时，添加模拟数据）

如果只是想快速测试飞书报告功能，可以用测试脚本：

```bash
python3 scripts/quick_test_feishu.py
```

**注意**：这个脚本会在数据库 `extname` 字段添加模拟数据，作为API的fallback方案。这不是标准做法，只是为了快速测试。

## 常见问题

### Q1: 为什么之前的诊断脚本要操作数据库？

A: 那是 **fallback 方案**。报告生成器的逻辑是：

1. **优先**：从API获取 `previous_positions_used`
2. **备用**：如果API失败，从数据库 `extname` 解析 `[X仓]`

所以添加数据库数据只是临时测试方法，不是标准流程。

### Q2: git pull 会同步回测数据吗？

A: **不会**。`git pull` 只同步代码文件：
- ✅ Python代码
- ✅ 配置文件
- ❌ 数据库内容
- ❌ 回测结果

### Q3: 如何避免每次更新都丢失数据？

A: 使用独立的数据库文件，不通过git同步：

```bash
# 数据库已经在 .gitignore 中
echo "data/*.db" >> .gitignore

# 每次更新代码后
git pull
# 数据库数据不会丢失
```

### Q4: 能不能从本地复制数据库到远程？

A: 可以，但需要注意：

```bash
# 在本地
scp data/etf.db root@192.168.8.30:/root/etf-predict/data/

# 在远程
# 重启API服务器使其重新加载数据
./start.sh restart
```

**风险**：
- 如果本地和远程代码版本不一致，可能导致问题
- 数据库格式变化可能不兼容

## 推荐流程

### 首次部署远程服务器

```bash
# 1. 克隆代码
git clone <repo_url> /root/etf-predict
cd /root/etf-predict

# 2. 安装依赖
pip install -r requirements.txt

# 3. 初始化数据库
python init_db.py

# 4. 配置飞书
cp conf.json.example conf.json
nano conf.json  # 填写飞书配置

# 5. 启动API服务器
python run.py &

# 6. 运行回测（获取真实持仓）
# 访问 http://192.168.8.30:8000/backtest

# 7. 测试API
python3 scripts/test_api_holdings.py
```

### 日常更新代码

```bash
# 1. 拉取最新代码
git pull

# 2. 重启API服务器（如果代码有变化）
./start.sh restart

# 3. 测试API
python3 scripts/test_api_holdings.py
```

## 总结

| 方法 | 适用场景 | 数据来源 | 推荐度 |
|------|---------|---------|--------|
| 运行回测 | 生产环境 | 真实回测结果 | ⭐⭐⭐⭐⭐ |
| 复制数据库 | 快速部署 | 从其他服务器复制 | ⭐⭐⭐ |
| 测试脚本 | 功能测试 | 模拟数据 | ⭐⭐ |

**最佳实践**：在远程服务器上运行回测，生成真实的持仓数据。
