# 飞书报告故障排查 - 脚本和文档索引

## 问题描述

远程服务器（192.168.8.30）通过 `git pull` 同步代码后，飞书报告显示0持仓。

## 诊断脚本

### 1. `scripts/diagnose_holdings.py` ⭐ 主要诊断工具

**用途**：诊断持仓数据问题

**运行**：
```bash
python3 scripts/diagnose_holdings.py
```

**检查内容**：
- 数据库 extname 字段是否有持仓信息
- 统计所有有持仓的ETF
- 测试API端点是否返回持仓数据
- 测试报告生成功能
- 保存完整诊断报告到 `diagnostic_report.md`

**输出**：完整的诊断报告，包括数据源检查和解决建议

---

### 2. `scripts/quick_test_feishu.py` ⭐ 快速修复工具

**用途**：添加模拟持仓数据并发送测试报告

**运行**：
```bash
python3 scripts/quick_test_feishu.py
```

**功能**：
1. 随机选择10-15个ETF添加模拟持仓（3-10仓）
2. 生成随机涨跌幅数据（-3%到+3%）
3. 发送完整报告到飞书
4. 保留数据供后续测试

**适用场景**：
- 快速验证飞书报告功能
- 测试报告格式
- 临时测试环境

---

### 3. `scripts/clear_mock_positions.py`

**用途**：清除数据库中的模拟持仓数据

**运行**：
```bash
python3 scripts/clear_mock_positions.py
```

**功能**：
- 从 `etf_basic.extname` 字段移除 `[X仓]` 标记
- 清除所有测试添加的持仓信息

---

### 4. `scripts/diagnose_feishu.py`

**用途**：诊断飞书配置问题

**运行**：
```bash
python3 scripts/diagnose_feishu.py
```

**检查内容**：
- conf.json 配置文件
- app_id、app_secret、chat_id 格式
- feishu_bot 模块导入
- 发送测试消息

**适用场景**：飞书消息发送失败时使用

---

### 5. `scripts/check_remote_feishu.sh`

**用途**：远程服务器综合诊断脚本

**运行**：
```bash
bash scripts/check_remote_feishu.sh
```

**检查内容**：
1. 代码版本
2. 飞书配置
3. 测试飞书连接
4. 调度器状态
5. **持仓数据诊断**（新增）
6. 服务器日志

**适用场景**：在远程服务器上运行完整诊断

---

## 文档指南

### 1. `docs/REMOTE_QUICKFIX.md` ⭐ 快速修复指南

**内容**：
- 问题原因说明
- 5分钟快速修复步骤
- 永久解决方案（运行回测）
- 常见错误排查
- 完整诊断流程

**适用场景**：遇到0持仓问题时首先查看

---

### 2. `docs/FEISHU_TROUBLESHOOTING.md` ⭐ 完整故障排查指南

**内容**：
- 配置文件问题
- feishu_bot.py 缺失
- Python模块导入错误
- 飞书API凭证错误
- 网络连接问题
- **报告显示0持仓的问题**（新增章节）

**适用场景**：深入排查飞书相关问题

---

## 使用流程

### 场景1：远程服务器显示0持仓

```bash
# 步骤1：SSH到远程服务器
ssh root@192.168.8.30
cd /root/etf-predict

# 步骤2：运行诊断
python3 scripts/diagnose_holdings.py

# 步骤3：快速修复（添加测试数据）
python3 scripts/quick_test_feishu.py

# 步骤4：验证飞书收到报告
```

### 场景2：飞书消息发送失败

```bash
# 步骤1：诊断飞书配置
python3 scripts/diagnose_feishu.py

# 步骤2：查看日志
tail -50 logs/server.log | grep -i "feishu\|error"

# 步骤3：根据诊断结果修复配置
```

### 场景3：git pull后功能异常

```bash
# 运行完整诊断脚本
bash scripts/check_remote_feishu.sh

# 根据输出逐项修复
```

---

## 技术说明

### 持仓数据存储位置

1. **主要存储**：策略回测结果表
   - 表名：`backtest_results_*`
   - 字段：`positions_used`
   - 获取方式：通过API `/api/watchlist/batch-signals`

2. **测试存储**：`etf_basic.extname` 字段
   - 格式：`ETF名称 [X仓]`
   - 用途：临时测试和演示
   - 脚本：`quick_test_feishu.py`

### 报告生成流程

```
generate_etf_operation_report()
  ├─ load_data()
  │   ├─ 尝试API获取数据（主要）
  │   └─ 回退到数据库解析（备用）
  ├─ _calculate_stats()
  │   └─ 统计 previous_positions_used > 0 的ETF
  └─ generate_markdown_report()
      └─ 生成Markdown格式的报告
```

### 为什么本地正常、远程显示0？

| 项目 | 本地 | 远程 |
|------|------|------|
| 代码 | ✅ 最新 | ✅ git pull 同步 |
| 数据库 | ✅ 有测试数据 | ❌ 无持仓数据 |
| 配置 | ✅ 已配置 | ✅ 已配置 |
| API服务器 | ✅ 运行中 | ❓ 可能未启动 |

**关键差异**：`git pull` 只同步代码文件，不同步数据库内容。

---

## 常用命令

### 诊断命令

```bash
# 持仓数据诊断
python3 scripts/diagnose_holdings.py

# 飞书配置诊断
python3 scripts/diagnose_feishu.py

# 完整服务器诊断
bash scripts/check_remote_feishu.sh
```

### 测试命令

```bash
# 快速测试（添加数据+发送报告）
python3 scripts/quick_test_feishu.py

# 清除测试数据
python3 scripts/clear_mock_positions.py
```

### 服务器管理

```bash
# 启动API服务器
python run.py

# 后台运行
nohup python run.py > logs/server.log 2>&1 &

# 重启服务器
./start.sh restart

# 查看日志
tail -f logs/server.log
```

---

## 文件清单

### 脚本文件

```
scripts/
├── diagnose_holdings.py          # 持仓数据诊断（新增）
├── quick_test_feishu.py          # 快速测试工具（新增）
├── clear_mock_positions.py       # 清除测试数据（新增）
├── diagnose_feishu.py            # 飞书配置诊断
├── check_remote_feishu.sh        # 远程服务器综合诊断
├── test_report_with_data.py      # 原有测试脚本
└── add_mock_positions.py         # 原有添加数据脚本
```

### 文档文件

```
docs/
├── REMOTE_QUICKFIX.md            # 快速修复指南（新增）
├── FEISHU_TROUBLESHOOTING.md     # 完整故障排查指南（已更新）
└── FEISHU_INTEGRATION.md         # 飞书集成文档
```

---

## 下次更新代码后

为了避免每次 `git pull` 后都显示0持仓：

### 方案A：运行测试脚本（推荐）

```bash
git pull
python3 scripts/quick_test_feishu.py
```

### 方案B：确保API服务器运行

```bash
git pull
python run.py &  # 如果未运行
```

### 方案C：运行完整回测（一次性）

```bash
# 通过Web界面运行回测
# http://192.168.8.30:8000/backtest
```

---

## 获取帮助

如果以上方法都无法解决问题：

1. 运行诊断并保存输出：
   ```bash
   python3 scripts/diagnose_holdings.py > diagnose.txt 2>&1
   python3 scripts/diagnose_feishu.py > feishu_diagnose.txt 2>&1
   ```

2. 收集服务器信息：
   ```bash
   python3 --version > system_info.txt
   git log -1 >> system_info.txt
   uname -a >> system_info.txt
   ```

3. 提供以下文件：
   - `diagnose.txt`
   - `feishu_diagnose.txt`
   - `system_info.txt`
   - `logs/server.log`（最近500行）
