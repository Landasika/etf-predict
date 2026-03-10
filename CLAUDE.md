# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于 Python + FastAPI 的 ETF 回测和交易信号预测系统，专注于 MACD 和多因子量化策略。系统采用模块化架构，将 API、核心业务逻辑、策略引擎和优化功能清晰分离。

## 核心开发命令

### 运行系统
```bash
# 启动 API 服务器（默认端口 8001）
python run.py

# 访问地址
# 主页: http://127.0.0.1:8001
# API 文档: http://127.0.0.1:8001/docs
```

### 数据库管理
```bash
# 初始化数据库（创建表结构）
python init_db.py

# 检查数据质量
python scripts/check_data.py

# 下载数据（需要配置 TUSHARE_TOKEN）
python scripts/download_etf_data.py
```

### 权重优化
```bash
# 优化单个 ETF 的权重（使用遗传算法 + 交叉验证）
cd optimization
python optimize_etf_advanced.py --etf_code 510330.SH

# 批量优化自选列表
python batch_optimize_watchlist.py
```

### 测试
```bash
# 运行测试（目前 tests/ 目录为空）
pytest
```

## 架构设计

### 模块组织

项目采用严格的分层架构：

1. **api/** - FastAPI Web 应用层
   - `main.py`: 所有 REST 端点定义
   - 路由组织：ETF 查询、自选管理、回测、信号生成、权重优化

2. **core/** - 核心业务逻辑层
   - `database.py`: SQLAlchemy 数据库操作（ETF 基础信息、K 线数据）
   - `watchlist.py`: 自选 ETF 列表管理（JSON 文件持久化）
   - `weight_manager.py`: 优化权重的加载和管理

3. **strategies/** - 策略引擎层
   - `signals.py`: 信号生成器（MACDSignalGenerator, MultiFactorSignalGenerator）
   - `indicators.py`: 技术指标计算（MACD、MA、KDJ、BOLL 等）
   - `backtester.py`: 回测引擎（MACDBacktester）
   - `factors.py`: 多因子分析（FactorBuilder）
   - `optimizer.py`: 权重优化器（基于遗传算法和交叉验证）

4. **optimization/** - 参数优化脚本
   - `optimize_etf_advanced.py`: 单 ETF 权重优化
   - `batch_optimize_watchlist.py`: 批量优化

5. **templates/** + **static/** - 前端层
   - Jinja2 模板 + ECharts 图表

### 数据流

1. **数据获取**: Tushare API → SQLite 数据库（`data/etf.db`）
2. **信号生成**: 数据库数据 → 技术指标计算 → 策略信号
3. **回测**: 历史数据 + 信号生成 → 回测引擎 → 性能指标
4. **优化**: 历史数据 → 交叉验证 → 遗传算法 → 最优权重（保存至 `optimized_weights/`）

### 策略系统

系统支持三种策略，通过 `core/watchlist.py` 中的 `STRATEGY_TYPES` 定义：

1. **macd_aggressive**: MACD 激进策略
   - 基于金叉死叉信号
   - 快速止损止盈
   - 适合波动较大的 ETF

2. **optimized_t_trading**: 优化做 T 策略
   - 降低交易频率
   - 宽松止损（-20%）+ 分批止盈
   - 适合震荡市场

3. **multifactor**: 多因子量化策略
   - 结合 MACD、KDJ、BOLL 等多个指标
   - 需要优化权重文件
   - 使用机器学习进行信号加权

### 关键配置文件

- `config.py`: 集中配置管理
  - API_HOST, API_PORT: 服务器地址
  - DATABASE_PATH: SQLite 数据库路径
  - WATCHLIST_PATH: 自选列表 JSON 路径
  - WEIGHTS_PATH: 优化权重存储路径
  - ETF_LIST: 支持的 52 个 ETF 列表

- `data/watchlist_etfs.json`: 用户自选 ETF 列表（运行时生成）

### 优化系统设计

权重优化采用先进的机器学习方法：

1. **因子构建** (`strategies/factors.py`): 从原始价格数据构建技术因子
2. **交叉验证**: 5 折交叉验证防止过拟合
3. **遗传算法**: 使用 DEAP 库进行参数空间搜索
4. **多目标优化**: 平衡收益率和夏普比率

优化结果保存在 `optimized_weights/{etf_code}/` 目录下。

## 开发注意事项

### 数据库操作
- 使用 SQLAlchemy 进行数据库访问
- 所有数据库操作集中在 `core/database.py`
- 表结构：`etf_basic`（ETF 基础信息）、`etf_daily`（日线数据）

### 策略参数
- 策略参数通过字典传递，参见 `strategies/signals.py:default_params()`
- MACD 默认参数：快线 8，慢线 17，信号线 5
- 回测默认参数：初始资金 2000，10 个仓位，止损 10%

### 信号生成
- MACD 四种实用方法：零轴趋势判断、多周期共振、MA60 过滤、背离检测
- 多因子信号需要先运行优化生成权重文件

### API 设计
- FastAPI 自动生成 Swagger 文档（/docs）
- 所有端点返回 JSON 格式
- 错误处理使用 HTTPException

### 性能考虑
- 回测 52 个 ETF 约 1 分钟
- 单个 ETF 优化约 5 分钟（取决于交叉验证折数）
- 数据库大小约 125MB

## 代码风格

- Python 3.8+
- 中文注释和文档字符串
- 类型提示（可选但推荐）
- 函数命名：snake_case
- 类命名：PascalCase

## 开发工作流

本项目使用 **Linear + GitHub + Claude Code** 的工作流系统。

### 项目跟踪配置

- **Linear 团队**: Engineering (ENG)
- **Linear 项目**: ETF-Predict
- **Review 状态**: In Review

### 自定义 Slash Commands

项目配置了以下自定义命令来规范开发流程：

1. **`/work-task ENG-{N}`** - 开始处理 Linear issue
   - 检查依赖阻塞
   - 验证 issue 质量（范围、验收标准）
   - 创建功能分支
   - 制定实施计划并等待批准

2. **`/finish-task`** - 完成当前任务
   - 运行所有质量检查
   - 代码审查
   - 创建 PR
   - 更新 Linear 状态为 In Review

3. **`/check-board`** - 检查项目面板
   - 汇总各状态的 issue 数量
   - 里程碑进度
   - 风险识别
   - 推荐接下来优先处理的 3 个 issue

4. **`/create-issue [context]`** - 创建新 issue
   - 从新发现的需求或阻塞创建后续 issue
   - 自动推断并确认
   - 设置依赖关系

### 质量检查命令

在创建 PR 之前，所有检查必须通过：

```bash
# 运行测试
pytest tests/ -v

# 类型检查
mypy core/ strategies/ api/ optimization/ --strict

# 代码风格检查
ruff check .

# 格式检查
ruff format --check .
```

### 分支命名规范

分支格式：`<prefix>/<issue-id-lowercase>-<slug>`

- `feature/` - 新功能
- `fix/` - Bug 修复
- `cleanup/` - 重构或技术债务

示例：`feature/eng-123-add-macd-indicator`

### 提交信息格式

`<summary> (ENG-{N})`

示例：`添加 MACD 指标计算功能 (ENG-42)`

### Pull Request 标准格式

标题：`ENG-{N}: <concise summary>`

Body 必须包含：
- `Closes ENG-{N}`
- 变更摘要
- 验证步骤
- 修改的文件列表
- 关联的里程碑

## 添加新策略

1. 在 `strategies/signals.py` 中创建新的信号生成器类
2. 在 `strategies/backtester.py` 中添加回测逻辑
3. 在 `core/watchlist.py` 的 `STRATEGY_TYPES` 中注册新策略
4. 在 `api/main.py` 中添加相应的 API 端点

## 常见问题排查

- **数据库错误**: 运行 `python init_db.py`
- **端口被占用**: 修改 `config.py` 中的 `API_PORT`
- **数据不足**: 运行 `python scripts/check_data.py` 检查
- **优化失败**: 确保有至少 200 天的历史数据
