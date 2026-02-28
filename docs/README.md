# 文档体系说明

本文档说明 ETF 策略回测系统的文档组织结构和导航指南。

## 📋 文档分类原则

系统文档按**读者类型**分为两大类：

### 1. 👨‍💻 开发者文档
**关注点**：技术实现、代码架构、API接口

**主要内容**：
- 系统架构设计
- 代码实现流程
- 数据库结构
- API 接口说明
- 部署运维指南

**文档特点**：
- 包含代码示例
- 说明技术细节
- 面向二次开发
- 便于问题定位

### 2. 📊 用户文档
**关注点**：策略使用、参数优化、实战应用

**主要内容**：
- 策略原理说明
- 参数配置指南
- 使用操作步骤
- 实战案例分析
- 常见问题解答

**文档特点**：
- 易懂非技术语言
- 实例驱动
- 操作指南详细
- 面向实际应用

---

## 🗂️ 文档结构树

```
docs/
├── README.md                    # 本文档（文档体系说明）
│
├── 【开发者文档】
│   ├── api.md                   # RESTful API 接口文档
│   ├── MACD_IMPLEMENTATION.md   # MACD 策略技术实现
│   ├── MACD_Trading_Design.md   # MACD 交易信号设计原理
│   └── POSITION_MANAGEMENT.md   # 仓位管理实现机制
│
└── 【用户文档】
    ├── strategies.md            # 策略对比和选择指南 ⭐ 入门必读
    │
    ├── MACD_AGGRESSIVE_GUIDE.md # MACD 激进策略完整指南
    │   ├─ 策略概述
    │   ├─ 参数说明
    │   ├─ 交易规则
    │   ├─ 适用场景
    │   ├─ 实战案例
    │   └─ 优化建议
    │
    ├── MACD_SIGNAL_STRENGTH.md         # 信号强度计算详解 ⭐ NEW
    │   ├─ 信号强度定义（-10到+10）
    │   ├─ 5个优先级计算规则
    │   ├─ 特殊形态（鸭嘴、回踩MA60）
    │   ├─ 零轴位置、背离、金叉死叉
    │   └─ 完整计算流程和实战应用
    │
    ├── MACD_AGGRESSIVE_POSITION_RULES.md # 仓位控制和买卖操作详解
    │   ├─ 10等份资金管理机制
    │   ├─ 信号强度→仓位映射表（1-10）
    │   ├─ 买入逻辑详解（逐步加仓）
    │   ├─ 卖出优先级（止损>追踪止盈>分批止盈>信号反转）
    │   ├─ 完整交易流程示例（3个场景）
    │   └─ 参数配置和常见问题
    │
    ├── MACD_KDJ_DISCRETE_GUIDE.md      # MACD+KDJ 离散仓位系统指南 ⭐ NEW
    │   ├─ 策略概述
    │   ├─ 核心原理（MACD+KDJ双层次）
    │   ├─ 参数说明
    │   ├─ 使用方法（Web界面+API）
    │   ├─ 参数优化（两阶段网格搜索）
    │   ├─ 实战案例
    │   └─ FAQ
    │
    ├── KDJ_DISCRETE_STATE_GUIDE.md      # 状态组合速查表
    │   ├─ 仓位到状态映射
    │   ├─ 完整状态转换表（5个KDJ区间）
    │   ├─ 特殊规则说明
    │   └─ 快速决策流程图
    │
    ├── ../strategies/MULTIFACTOR_USAGE.md       # 多因子策略使用说明
    └── ../strategies/WEIGHT_OPTIMIZATION_GUIDE.md # 权重优化指南
```

---

## 🎯 文档使用指南

### 我是开发者，想了解技术实现

**推荐阅读顺序**：

1. **系统架构** → [README.md](../README.md)
   - 了解项目整体架构和模块划分

2. **技术实现** → [MACD_IMPLEMENTATION.md](MACD_IMPLEMENTATION.md)
   - 理解策略计算的完整代码流程

3. **API 接口** → [api.md](api.md)
   - 学习如何调用系统接口

4. **数据库** → [DATABASE_INFO.md](../data/DATABASE_INFO.md)
   - 了解数据存储结构

5. **部署运维** → [DEPLOYMENT.md](../DEPLOYMENT.md)
   - 掌握系统部署和运维

### 我是用户，想使用策略

**推荐阅读顺序**：

1. **策略选择** → [strategies.md](strategies.md) ⭐ **入门必读**
   - 了解所有策略的特点和适用场景
   - 选择最适合自己投资风格的策略

2. **策略深入学习** → 根据选择的策略阅读对应指南：
   - **MACD 激进策略** → [MACD_AGGRESSIVE_GUIDE.md](MACD_AGGRESSIVE_GUIDE.md) + [信号强度详解](MACD_SIGNAL_STRENGTH.md) + [仓位控制详解](MACD_AGGRESSIVE_POSITION_RULES.md) ⭐
   - **MACD+KDJ 离散仓位系统** → [MACD_KDJ_DISCRETE_GUIDE.md](MACD_KDJ_DISCRETE_GUIDE.md) + [状态速查表](KDJ_DISCRETE_STATE_GUIDE.md)
   - **多因子策略** → [MULTIFACTOR_USAGE.md](../strategies/MULTIFACTOR_USAGE.md)

3. **实战参考** → 查看策略文档中的实战案例部分
   - 学习实际应用场景
   - 理解策略表现

4. **参数优化** → 根据策略文档中的优化指南进行参数调优

---

## 📖 文档标识说明

每个文档开头都有明确的标识，帮助您快速判断文档类型：

| 标识 | 类型 | 说明 |
|------|------|------|
| 👨‍💻 开发者文档 | 技术文档 | 面向开发者，关注技术实现 |
| 📊 用户文档 | 使用文档 | 面向用户，关注策略使用 |
| ⭐ 必读 | 重点推荐 | 重要文档，建议优先阅读 |
| ⭐ NEW | 新增 | 最新添加的文档或内容 |

---

## 🔍 快速查找

### 按主题查找

**策略相关**：
- [策略对比](strategies.md) - 所有策略一览
- [MACD激进策略](MACD_AGGRESSIVE_GUIDE.md) - 详细使用指南
- [MACD信号强度计算详解](MACD_SIGNAL_STRENGTH.md) - 信号如何计算 ⭐ NEW
- [MACD激进策略 - 仓位控制详解](MACD_AGGRESSIVE_POSITION_RULES.md) - 买卖操作和仓位管理 ⭐
- [MACD+KDJ离散仓位系统](MACD_KDJ_DISCRETE_GUIDE.md) - 详细使用指南
- [状态速查表](KDJ_DISCRETE_STATE_GUIDE.md) - 快速决策参考

**技术相关**：
- [API文档](api.md) - 接口说明
- [技术实现](MACD_IMPLEMENTATION.md) - 代码流程
- [交易设计](MACD_Trading_Design.md) - 算法原理
- [仓位管理](POSITION_MANAGEMENT.md) - 实现机制

**优化相关**：
- [权重优化指南](../strategies/WEIGHT_OPTIMIZATION_GUIDE.md)
- [参数优化脚本](../optimization/README.md)

### 按问题查找

| 我想... | 推荐文档 |
|---------|---------|
| 选择一个策略 | [strategies.md](strategies.md) |
| 使用 MACD 激进策略 | [MACD_AGGRESSIVE_GUIDE.md](MACD_AGGRESSIVE_GUIDE.md) |
| 理解信号强度如何计算 | [MACD_SIGNAL_STRENGTH.md](MACD_SIGNAL_STRENGTH.md) ⭐ NEW |
| 理解 MACD 仓位控制 | [MACD_AGGRESSIVE_POSITION_RULES.md](MACD_AGGRESSIVE_POSITION_RULES.md) ⭐ |
| 使用 MACD+KDJ 离散仓位系统 | [MACD_KDJ_DISCRETE_GUIDE.md](MACD_KDJ_DISCRETE_GUIDE.md) |
| 查看状态决策表 | [KDJ_DISCRETE_STATE_GUIDE.md](KDJ_DISCRETE_STATE_GUIDE.md) |
| 优化策略参数 | 各策略指南中的"参数优化"章节 |
| 调用 API | [api.md](api.md) |
| 理解代码实现 | [MACD_IMPLEMENTATION.md](MACD_IMPLEMENTATION.md) |
| 部署系统 | [DEPLOYMENT.md](../DEPLOYMENT.md) |

---

## 📝 文档维护规范

### 编写原则

1. **明确受众**：每个文档必须明确是面向开发者还是用户
2. **目的清晰**：开头说明文档目的和适用读者
3. **内容聚焦**：
   - 开发者文档：关注技术实现、代码、架构
   - 用户文档：关注使用方法、参数、实战
4. **避免混淆**：不在技术文档中大量讲述使用方法，不在用户文档中深入讲解代码细节

### 文档更新

- 新增策略 → 更新 `strategies.md`，创建新的策略指南
- 修改 API → 更新 `api.md`，同时更新 Swagger 文档
- 算法调整 → 更新设计文档（如 `MACD_Trading_Design.md`）
- 实现变更 → 更新实现文档（如 `MACD_IMPLEMENTATION.md`）

---

## 🔗 外部资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Pandas 文档](https://pandas.pydata.org/docs/)
- [Tushare 文档](https://tushare.pro/document/1)

---

**最后更新**：2026-02-26
**文档版本**：v1.3.0
