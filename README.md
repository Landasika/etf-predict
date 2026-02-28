# ETF 策略回测与信号预测系统

> 基于 MACD 和多因子策略的 ETF 回测和交易信号预测系统

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## ✨ 功能特性

### 🎯 多策略支持
- **MACD 激进策略**：快速响应市场变化，适合波动较大的ETF
- **优化做 T 策略**：降低交易频率，减少手续费，适合震荡市场
- **多因子量化策略**：综合 MACD、KDJ、BOLL 等多个指标，适合长期投资
- **MACD+KDJ 离散仓位系统 2.0** ⭐：MACD判断趋势，KDJ确定0-10成离散仓位，精细化仓位管理

### 📊 数据与回测
- **52+ 主流 ETF**：覆盖宽基、行业、主题等各类 ETF
- **智能缓存机制**：基于 SQLite 的数据缓存，快速加载
- **全面回测分析**：收益率、夏普比率、最大回撤、胜率等指标
- **权重自动优化**：基于遗传算法和交叉验证的参数优化

### 🖥️ Web 界面
- **策略汇总页面**：一览所有自选 ETF 的实时信号和收益
- **详细策略页面**：单个 ETF 的详细分析和可视化
- **自定义备注**：支持为 ETF 添加个人备注
- **一键刷新**：快速更新数据和缓存

## 📦 安装部署

### 1. 环境要求

- Python 3.8+
- SQLite 3
- 1GB+ 可用内存

### 2. 快速开始

```bash
# 克隆项目
git clone <repository-url>
cd etf-predict

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python init_db.py

# 启动服务
python run.py
```

访问 http://127.0.0.1:8001 查看系统

### 3. 数据准备

#### 选项 1：使用现有数据库（推荐）

如果您已有 ETF 数据库，直接复制到 `data/` 目录：

```bash
cp /path/to/etf.db data/
```

#### 选项 2：从 Tushare 下载

1. 注册 Tushare 账号：https://tushare.pro
2. 编辑 `config.py`，设置 `TUSHARE_TOKEN`
3. 运行下载脚本：

```bash
python scripts/download_etf_data.py
```

## 📖 使用指南

### 添加 ETF 到自选

1. 访问主页：http://127.0.0.1:8001
2. 点击"添加 ETF"按钮
3. 输入 ETF 代码（如 `510330.SH`）
4. 选择策略类型
5. 点击"确认添加"

### 查看策略信号

系统会自动计算并显示：
- **当前信号**：买入/持有/卖出
- **下个交易日操作**：具体的操作建议
- **近一年收益率**：策略收益 vs 股票涨幅
- **MACD 指标**：DIF、DEA 数值
- **持仓状态**：当前仓位使用情况

### 自定义备注

点击表格中的"备注"列，可以添加个人备注，备注会保存到配置文件中。

### 刷新数据

- **刷新页面**：重新计算所有策略信号（使用缓存）
- **更新数据**：从 Tushare 下载最新数据（需要配置 Token）

## 🎛️ 策略说明

### MACD 激进策略

- **适用场景**：波动较大的 ETF
- **参数**：快速 MACD（8, 17, 5）
- **止损止盈**：5% 止损，10%/20% 分批止盈
- **特点**：快速进出，追求短期收益

### 优化做 T 策略

- **适用场景**：震荡市场
- **参数**：中等 MACD（12, 26, 9）
- **止损止盈**：20% 止损，10%/20%/35% 分批止盈 + 追踪止盈
- **特点**：降低交易频率，减少手续费磨损

### 多因子量化策略

- **适用场景**：长期投资
- **因子**：MACD + KDJ + BOLL
- **优化**：需要先运行权重优化
- **特点**：多指标综合，信号更稳定

### MACD+KDJ 离散仓位系统 2.0 ⭐ NEW

- **适用场景**：震荡市、趋势市
- **决策层次**：MACD判断趋势（BULL/BEAR），KDJ确定仓位（0-10成离散）
- **仓位设置**：0/1/3/4/5/6/7/8/10成（严格离散化）
- **特点**：精细化仓位管理，T+1执行避免未来函数
- **文档**：[详细指南](docs/MACD_KDJ_DISCRETE_GUIDE.md) | [速查表](docs/KDJ_DISCRETE_STATE_GUIDE.md)

## 📁 项目结构

```
etf-predict/
├── api/                    # FastAPI Web 应用
│   └── main.py            # 所有 API 端点
├── core/                  # 核心业务逻辑
│   ├── database.py        # 数据库操作（ETF、缓存）
│   ├── watchlist.py       # 自选列表管理
│   └── weight_manager.py  # 权重优化管理
├── strategies/            # 策略引擎
│   ├── backtester.py     # 回测引擎
│   ├── indicators.py     # 技术指标计算
│   ├── signals.py        # 信号生成器
│   ├── factors.py        # 多因子分析
│   ├── optimizer.py      # 权重优化器
│   ├── macd_kdj_discrete.py           # MACD+KDJ离散仓位信号生成器 ⭐
│   ├── macd_kdj_discrete_backtester.py # MACD+KDJ离散仓位回测引擎 ⭐
│   └── macd_kdj_discrete_param_optimizer.py # 参数优化器 ⭐
├── optimization/          # 参数优化脚本
│   ├── optimize_etf_advanced.py
│   └── batch_optimize_watchlist.py
├── templates/            # HTML 模板
│   └── index.html        # 主页
├── static/               # 静态资源
│   ├── css/             # 样式文件
│   └── js/              # JavaScript 文件
├── data/                 # 数据目录
│   ├── etf.db           # SQLite 数据库
│   └── watchlist_etfs.json # 自选列表
├── scripts/              # 实用脚本
│   ├── download_etf_data.py
│   └── check_data.py
├── docs/                 # 文档
│   ├── api.md           # API 文档
│   ├── strategies.md    # 策略说明
│   ├── MACD_AGGRESSIVE_GUIDE.md      # MACD激进策略详解
│   ├── MACD_KDJ_DISCRETE_GUIDE.md    # MACD+KDJ离散仓位系统详解 ⭐
│   └── KDJ_DISCRETE_STATE_GUIDE.md   # 状态组合速查表 ⭐
├── config.py            # 配置文件
├── run.py              # 启动脚本
├── init_db.py          # 数据库初始化
├── requirements.txt    # Python 依赖
├── CLAUDE.md           # Claude Code 开发指南
└── README.md           # 本文档
```

## 🔧 配置说明

编辑 `config.py` 可以修改：

```python
# 服务器配置
API_HOST = '0.0.0.0'
API_PORT = 8001

# 数据库路径
DATABASE_PATH = 'data/etf.db'

# 自选列表路径
WATCHLIST_PATH = 'data/watchlist_etfs.json'

# 优化权重存储路径
WEIGHTS_PATH = 'optimized_weights'

# Tushare Token（可选）
TUSHARE_TOKEN = 'your_token_here'

# 支持的 ETF 列表
ETF_LIST = [
    '510330.SH',  # 沪深300ETF
    '159672.SZ',  # 创业板ETF
    # ... 更多 ETF
]
```

## 🚀 API 文档

启动服务后访问 http://127.0.0.1:8001/docs 查看完整的 API 文档。

### 主要端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/watchlist` | 获取自选列表 |
| POST | `/api/watchlist/add` | 添加 ETF |
| DELETE | `/api/watchlist/{code}` | 删除 ETF |
| GET | `/api/watchlist/batch-signals` | 批量获取信号 |
| POST | `/api/watchlist/refresh-cache` | 刷新缓存 |
| POST | `/api/watchlist/remark` | 更新备注 |
| GET | `/api/data/latest-date` | 获取最新数据日期 |
| POST | `/api/data/update` | 更新市场数据 |

## 📈 性能优化

### 缓存机制

系统使用 SQLite 缓存批量数据，以数据日期为 key：

- **首次访问**：计算所有 ETF 的信号和回测，并缓存
- **后续访问**：直接从缓存读取，响应速度提升 10 倍+
- **数据更新**：点击"刷新页面"按钮强制重新计算并更新缓存

### 数据查询优化

- 使用索引加速数据库查询
- 批量查询减少数据库连接次数
- 延迟加载图表数据

## ❓ 常见问题

### Q: 为什么页面加载很慢？

A: 首次访问需要计算所有 ETF 的策略信号，请耐心等待。后续访问会使用缓存，速度很快。

### Q: 如何更新 ETF 数据？

A: 点击页面上的"更新数据"按钮（需要配置 TUSHARE_TOKEN）。

### Q: 权重优化失败怎么办？

A: 确保有足够的历史数据（至少 100 个交易日），检查 `optimized_weights/` 目录权限。

### Q: 如何添加新的 ETF？

A: 点击"添加 ETF"按钮，输入 ETF 代码（如 `510330.SH`）即可。

## 📝 更新日志

### v1.1.0 (2026-02-17)
- ✨ 新增用户自定义备注功能
- ✨ 新增 SQLite 缓存机制，大幅提升加载速度
- ✨ 新增"近一年收益率"显示（年化处理）
- 🐛 修复表头排序功能
- 🔧 优化首页布局，删除回测汇总表格

### v1.0.0 (2026-02-16)
- 🎉 初始版本发布
- ✨ 支持 MACD 和多因子策略
- ✨ Web 界面和 API
- ✨ 权重优化功能

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## ⚠️ 免责声明

本系统仅供学习和研究使用，不构成任何投资建议。投资有风险，请谨慎决策。

---

**Made with ❤️ by ETF Predict Team**
