# 文档目录

欢迎来到 ETF 策略回测系统文档中心！

## 📚 快速导航

**新手入门**？→ 从 [策略对比](strategies.md) 开始选择适合的策略 ⭐

**开发者**？→ 查看 [技术实现](MACD_IMPLEMENTATION.md) 或 [API文档](api.md)

**不知道看哪个**？→ 阅读 [文档体系说明](README.md) 了解文档组织

---

## 📖 文档分类

本文档按读者类型分为两大类：
- **👨‍💻 开发者文档**：技术实现、API、架构设计
- **📊 用户文档**：策略使用、参数优化、实战指南

> 💡 详细说明请查看：[文档体系说明](README.md)

---

## 👨‍💻 开发者文档

### 快速开始
- [README.md](../README.md) - 项目概述和主要功能
- [QUICKSTART.md](../QUICKSTART.md) - 5分钟快速启动指南
- [CLAUDE.md](../CLAUDE.md) - Claude Code 开发指南

### 架构与设计
- [MACD_IMPLEMENTATION.md](MACD_IMPLEMENTATION.md) - MACD策略技术实现（代码流程）
- [MACD_Trading_Design.md](MACD_Trading_Design.md) - MACD交易信号设计原理
- [POSITION_MANAGEMENT.md](POSITION_MANAGEMENT.md) - 仓位管理实现机制

### API 文档
- [api.md](api.md) - RESTful API 详细文档
- 在线文档：http://127.0.0.1:8001/docs（启动服务后访问）

### 数据库
- [DATABASE_INFO.md](../data/DATABASE_INFO.md) - 数据库结构和说明

### 部署运维
- [DEPLOYMENT.md](../DEPLOYMENT.md) - 部署指南（开发/生产/Docker）
- [START_SCRIPT_GUIDE.md](START_SCRIPT_GUIDE.md) - 启动脚本使用指南（前台/后台）

### 认证与安全
- [AUTHENTICATION.md](AUTHENTICATION.md) - 身份认证使用指南
- [FINAL_FIX.md](FINAL_FIX.md) - Session和鉴权修复说明
- [TROUBLESHOOTING_QUICK.md](TROUBLESHOOTING_QUICK.md) - 快速故障排除
- [LOG_MANAGEMENT.md](LOG_MANAGEMENT.md) - 日志管理

---

## 📊 用户文档

### 策略总览
- [strategies.md](strategies.md) - **策略类型对比和选择指南** 🌟

### 策略详细指南

#### MACD 激进策略
- [MACD_AGGRESSIVE_GUIDE.md](MACD_AGGRESSIVE_GUIDE.md) - 完整使用指南
  - 策略原理、参数说明、交易规则
  - 适用场景、优缺点分析
  - 实战案例、优化建议
- [MACD_SIGNAL_STRENGTH.md](MACD_SIGNAL_STRENGTH.md) - 信号强度计算详解 ⭐ NEW
  - 信号强度定义（-10到+10）
  - 5个优先级计算规则
  - 特殊形态（鸭嘴、回踩MA60）
  - 零轴位置、背离、金叉死叉
  - 完整计算流程示例
- [MACD_AGGRESSIVE_POSITION_RULES.md](MACD_AGGRESSIVE_POSITION_RULES.md) - 仓位控制和买卖操作详解 ⭐
  - 10等份资金管理
  - 信号强度→仓位映射
  - 买入逻辑（逐步加仓）
  - 卖出优先级（止损>追踪止盈>分批止盈>信号反转）
  - 完整交易流程示例

#### MACD+KDJ 离散仓位系统 2.0 ⭐ NEW
- [MACD_KDJ_DISCRETE_GUIDE.md](MACD_KDJ_DISCRETE_GUIDE.md) - 完整使用指南
  - 双层次决策原理（MACD趋势 + KDJ仓位）
  - 离散仓位表（0/1/3/4/5/6/7/8/10成）
  - 参数优化、实战案例、FAQ
- [KDJ_DISCRETE_STATE_GUIDE.md](KDJ_DISCRETE_STATE_GUIDE.md) - 状态组合速查表
  - 仓位到状态映射（OFF/TRY/HOLD/TRIM）
  - 完整决策表（5个KDJ区间）
  - 快速决策流程图

#### 多因子策略
- [MULTIFACTOR_USAGE.md](../strategies/MULTIFACTOR_USAGE.md) - 多因子策略使用说明
- [WEIGHT_OPTIMIZATION_GUIDE.md](../strategies/WEIGHT_OPTIMIZATION_GUIDE.md) - 权重优化指南

### 优化工具
- [优化脚本README](../optimization/README.md) - 参数优化脚本说明

### 系统更新
- [CHANGELOG.md](../CHANGELOG.md) - 版本更新日志

---

## 🎯 按角色查看

### 👨‍💻 开发者
1. 阅读 [QUICKSTART.md](../QUICKSTART.md) 快速启动
2. 查看 [CLAUDE.md](../CLAUDE.md) 了解项目架构
3. 参考 [api.md](api.md) 进行二次开发

### 📊 量化交易者
1. 阅读 [README.md](../README.md) 了解策略类型
2. 查看 [strategies.md](strategies.md) 选择合适策略
3. 参考 [WEIGHT_OPTIMIZATION_GUIDE.md](../strategies/WEIGHT_OPTIMIZATION_GUIDE.md) 优化参数

### 🚀 运维工程师
1. 阅读 [DEPLOYMENT.md](../DEPLOYMENT.md) 部署系统
2. 配置 Systemd 服务
3. 设置 Nginx 反向代理

### 🔬 研究人员
1. 查看 [strategies.md](strategies.md) 了解策略原理
2. 阅读 [MULTIFACTOR_USAGE.md](../strategies/MULTIFACTOR_USAGE.md) 研究多因子模型
3. 运行回测验证假设

---

## 📖 文档结构

```
docs/
├── INDEX.md              # 本文档（文档导航）
├── api.md                # API 文档
└── strategies.md         # 策略说明

项目根目录/
├── README.md             # 项目主文档
├── QUICKSTART.md         # 快速开始
├── CHANGELOG.md          # 更新日志
├── DEPLOYMENT.md         # 部署指南
├── CLAUDE.md             # 开发指南
│
├── strategies/
│   ├── WEIGHT_OPTIMIZATION_GUIDE.md  # 权重优化
│   ├── MULTIFACTOR_USAGE.md         # 多因子使用
│   └── IMPLEMENTATION_SUMMARY.md    # 实现总结
│
├── optimization/
│   └── README.md                      # 优化脚本说明
│
└── data/
    └── DATABASE_INFO.md              # 数据库文档
```

---

## 🔍 搜索文档

### 按关键词查找

**启动和安装**
- 快速开始 → [QUICKSTART.md](../QUICKSTART.md)
- 依赖安装 → [README.md#安装部署](../README.md#安装部署)
- 环境要求 → [DEPLOYMENT.md#开发环境](../DEPLOYMENT.md#开发环境)

**配置和优化**
- 配置说明 → [README.md#配置说明](../README.md#配置说明)
- 权重优化 → [strategies/WEIGHT_OPTIMIZATION_GUIDE.md](../strategies/WEIGHT_OPTIMIZATION_GUIDE.md)
- 性能优化 → [DEPLOYMENT.md#性能优化](../DEPLOYMENT.md#性能优化)

**策略和回测**
- 策略类型 → [strategies.md](strategies.md)
- 回测指标 → [README.md#性能指标](../README.md#性能指标)
- 信号生成 → [strategies.md#信号生成](strategies.md#信号生成)

**API 和集成**
- API 端点 → [api.md](api.md)
- 在线文档 → http://127.0.0.1:8001/docs
- SDK 示例 → [api.md#示例](api.md#示例)

**故障排除**
- 常见问题 → [README.md#常见问题](../README.md#常见问题)
- 故障排除 → [DEPLOYMENT.md#故障排除](../DEPLOYMENT.md#故障排除)

---

## 📝 文档贡献

发现文档错误或遗漏？欢迎贡献！

1. Fork 项目
2. 创建文档分支：`git checkout -b docs/update-xxx`
3. 修改文档
4. 提交 PR

---

## 🔗 外部资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)
- [Pandas 文档](https://pandas.pydata.org/docs/)
- [Tushare 文档](https://tushare.pro/document/1)

---

**最后更新**：2026-02-17
