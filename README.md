# ETF 策略回测与信号预测系统

> 基于 MACD 和多因子策略的 ETF 回测和交易信号预测系统

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## 🐳 快速部署（Docker）

```bash
git clone https://github.com/Landasika/etf-predict.git
cd etf-predict
cp .env.docker.example .env
nano .env  # 填写 TUSHARE_TOKEN
make build && make up
```

访问 http://localhost:8000 查看系统

[📖 详细部署文档](DOCKER.md) | [🔧 配置说明](#-配置说明)

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

### 方式一：Docker 部署（推荐）

**适合生产环境，一键部署，无需手动配置依赖**

#### 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/Landasika/etf-predict.git
cd etf-predict

# 2. 配置环境变量
cp .env.docker.example .env
nano .env  # 填写 TUSHARE_TOKEN

# 3. 启动服务
./docker-start.sh

# 或使用 Makefile
make build && make up
```

#### 访问服务

- **API 地址**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

#### 常用命令

```bash
make ps          # 查看状态
make logs        # 查看日志
make restart     # 重启服务
make exec        # 进入容器
make init-db     # 初始化数据库
make download    # 下载数据
make clean       # 清理容器
```

#### 环境变量

| 变量名 | 必需 | 默认值 | 说明 |
|--------|------|--------|------|
| `TUSHARE_TOKEN` | ✅ | - | Tushare API Token |
| `API_PORT` | ❌ | 8000 | API 端口 |
| `AUTH_KEY` | ❌ | admin123 | 认证密钥 |

详细文档：[DOCKER.md](DOCKER.md)

---

### 方式二：本地安装

**适合开发环境，需要手动配置 Python 环境**

#### 1. 环境要求

- Python 3.8+
- SQLite 3
- 1GB+ 可用内存

#### 2. 快速开始

```bash
# 克隆项目
git clone https://github.com/Landasika/etf-predict.git
cd etf-predict

# 安装依赖
pip install -r requirements.txt

# 初始化数据库
python init_db.py

# 启动服务
python run.py
```

访问 http://127.0.0.1:8000 查看系统

### 3. 数据准备

#### 选项 1：使用现有数据库（推荐）

如果您已有 ETF 数据库，直接复制到 `data/` 目录：

```bash
# Docker 部署
docker cp /path/to/etf.db etf-predict:/app/data/

# 本地部署
cp /path/to/etf.db data/
```

#### 选项 2：从 Tushare 下载

**Docker 部署：**

```bash
# 1. 在 .env 中配置 TUSHARE_TOKEN
# 2. 下载数据
make download
```

**本地部署：**

1. 注册 Tushare 账号：https://tushare.pro
2. 配置环境变量或编辑 `config.json`
3. 运行下载脚本：

```bash
python scripts/download_etf_data.py
```

## 📖 使用指南

### 添加 ETF 到自选

1. 访问主页：http://127.0.0.1:8000（或 http://localhost:8000）
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
│   ├── verify_docker_config.py
│   └── check_data.py
├── docs/                 # 文档
│   ├── api.md           # API 文档
│   ├── strategies.md    # 策略说明
│   ├── MACD_AGGRESSIVE_GUIDE.md      # MACD激进策略详解
│   ├── MACD_KDJ_DISCRETE_GUIDE.md    # MACD+KDJ离散仓位系统详解 ⭐
│   └── KDJ_DISCRETE_STATE_GUIDE.md   # 状态组合速查表 ⭐
├── Dockerfile            # Docker 镜像构建
├── docker-compose.yml    # Docker 编排配置
├── Makefile              # Make 命令简化
├── .env.docker.example   # 环境变量模板
├── DOCKER.md             # Docker 部署文档
├── config.py            # 配置文件（支持环境变量）
├── config.json          # 配置文件（本地）
├── run.py              # 启动脚本
├── init_db.py          # 数据库初始化
├── requirements.txt    # Python 依赖
├── CLAUDE.md           # Claude Code 开发指南
└── README.md           # 本文档
```

## 🔧 配置说明

### Docker 部署配置

通过环境变量配置（编辑 `.env` 文件）：

```bash
# 数据源配置
TUSHARE_TOKEN=your_token_here
TUSHARE_PROXY_URL=http://124.222.60.121:8020/

# API 配置
API_HOST=0.0.0.0
API_PORT=8000

# 认证配置
AUTH_KEY=admin123
SESSION_SECRET_KEY=your-random-secret-key

# 调度配置
UPDATE_SCHEDULE_ENABLED=true
UPDATE_SCHEDULE_TIME=15:05
```

### 本地部署配置

编辑 `config.json` 或使用环境变量：

```json
{
  "database": {"path": "data/etf.db"},
  "api": {
    "host": "0.0.0.0",
    "port": 8000
  },
  "tushare": {
    "token": "your_token_here",
    "proxy_url": "http://124.222.60.121:8020/"
  },
  "auth": {
    "auth_key": "admin123"
  }
}
```

**注意**：环境变量优先级高于配置文件

## 🚀 API 文档

启动服务后访问 http://127.0.0.1:8000/docs 查看完整的 API 文档。

### 主要端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 主页 |
| GET | `/health` | 健康检查 |
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

### Q: Docker 部署如何查看日志？

A: 使用 `make logs` 或 `docker-compose logs -f etf-predict`

### Q: Docker 容器无法启动？

A:
1. 检查 .env 文件是否配置正确
2. 确保端口 8000 未被占用
3. 查看日志：`docker-compose logs etf-predict`

### Q: 为什么页面加载很慢？

A: 首次访问需要计算所有 ETF 的策略信号，请耐心等待。后续访问会使用缓存，速度很快。

### Q: 如何更新 ETF 数据？

**Docker 部署：** `make download`

**本地部署：** 点击页面上的"更新数据"按钮（需要配置 TUSHARE_TOKEN）

### Q: 权重优化失败怎么办？

A: 确保有足够的历史数据（至少 100 个交易日），检查 `optimized_weights/` 目录权限。

### Q: 如何添加新的 ETF？

A: 点击"添加 ETF"按钮，输入 ETF 代码（如 `510330.SH`）即可。

### Q: 如何备份数据？

**Docker 部署：**
```bash
# 备份数据卷
docker run --rm -v etf-predict_etf-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/etf-data-backup.tar.gz /data
```

**本地部署：** 直接复制 `data/etf.db` 文件

## 📝 更新日志

### v1.2.0 (2026-04-17)
- 🐳 **新增 Docker 生产部署支持**
  - 多阶段构建镜像，非特权用户运行
  - docker-compose 编排配置
  - 环境变量管理敏感信息
  - 健康检查和日志轮转
- ✨ 支持 Tushare 代理配置
- ✨ 配置文件支持环境变量覆盖
- 🔧 添加 Makefile 和快速启动脚本
- 📝 完善部署文档和配置验证工具

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
