# 更新日志

所有重要变更都会记录在此文件中。

## [1.3.1] - 2026-02-26

### 文档优化
- 📚 **文档体系重构**：按读者类型明确分类
  - 新增 `docs/README.md`：文档体系说明（206行）
    - 明确文档分类原则（开发者文档 vs 用户文档）
    - 提供文档结构树
    - 开发者/用户不同阅读路径
    - 快速查找表（按主题、按问题）
    - 文档维护规范
  - 所有文档添加受众标识：
    - 👨‍💻 开发者文档：关注技术实现、代码架构
    - 📊 用户文档：关注策略使用、实战应用
  - 优化 `docs/INDEX.md` 导航结构
    - 添加快速导航提示
    - 明确两大文档分类
    - 引导到详细说明

### 文档分类

**开发者文档**（5个）：
- `api.md` - RESTful API 接口文档（471行）
- `MACD_IMPLEMENTATION.md` - MACD 策略技术实现（208行）
- `MACD_Trading_Design.md` - MACD 交易信号设计原理（314行）
- `POSITION_MANAGEMENT.md` - 仓位管理实现机制

**用户文档**（5个）：
- `strategies.md` - 策略对比和选择指南（438行）⭐ 入门必读
- `MACD_AGGRESSIVE_GUIDE.md` - MACD 激进策略完整指南（398行）
- `MACD_KDJ_DISCRETE_GUIDE.md` - MACD+KDJ 离散仓位系统指南（454行）
- `KDJ_DISCRETE_STATE_GUIDE.md` - 状态组合速查表（231行）

### 优化效果
- ✅ 文档分类清晰：设计文档 vs 策略文档一目了然
- ✅ 受众明确：每个文档都标注适用读者和目的
- ✅ 导航优化：提供多种查找方式
- ✅ 内容聚焦：设计关注技术，策略关注使用
- ✅ 易于维护：明确的文档更新规范

---

## [1.3.0] - 2026-02-26

### 新增
- ✨ **MACD+KDJ 离散仓位系统 2.0**：全新的双层次决策策略
  - MACD 判断趋势方向（BULL 做多，BEAR 空仓）
  - KDJ 确定 0-10 成离散仓位（严格离散化：0/1/3/4/5/6/7/8/10）
  - 四状态机设计：OFF（空仓）、TRY（试仓）、HOLD（持仓）、TRIM（减仓）
  - 严格 T+1 执行：所有信号和仓位都 shift(1) 避免未来函数
  - 5 个 KDJ 区间：A 区（K<20）、B 区（20-50）、C 区（50-80）、D 区（80-90）、E 区（K≥90）
  - 参数优化功能：支持两阶段网格搜索优化 MACD 和 KDJ 参数
  - 参数持久化：优化后的参数保存到 JSON，自动用于回测和信号计算
- ✨ 新策略类型 `macd_kdj_discrete` 添加到系统
- ✨ 新增 `MACDKDJDiscreteSignalGenerator` 信号生成器
- ✨ 新增 `MACDKDJDiscreteBacktester` 回测引擎
- ✨ 新增 `MACDKDJDiscreteParamOptimizer` 参数优化器（两阶段网格搜索）
- ✨ Web 界面支持：
  - 策略选择器添加"MACD+KDJ 离散仓位系统 2.0"选项
  - 参数优化面板支持显示 KDJ 参数（N, M1, M2）
  - 一键优化按钮和恢复默认参数功能
- ✨ 新增 API 端点：
  - `POST /api/macd-kdj-discrete/optimize-params/{etf_code}` - 优化参数
  - `POST /api/watchlist/{etf_code}/macd-kdj-discrete-params` - 保存参数
  - `DELETE /api/watchlist/{etf_code}/macd-kdj-discrete-params` - 恢复默认
  - `GET /api/watchlist/{etf_code}/macd-kdj-discrete-params` - 获取参数

### 文档
- 📚 新增 `docs/MACD_KDJ_DISCRETE_GUIDE.md`：MACD+KDJ 离散仓位系统完整使用指南（446 行）
  - 策略概述、核心原理、参数说明
  - 使用方法、参数优化、实战案例
  - 常见问题、API 速查
- 📚 新增 `docs/KDJ_DISCRETE_STATE_GUIDE.md`：状态组合速查表（223 行）
  - 仓位到状态映射（OFF/TRY/HOLD/TRIM）
  - 完整状态转换表（5 个 KDJ 区间）
  - 特殊规则、实战示例、快速决策流程图
- 📚 更新 `docs/INDEX.md`：添加新策略文档链接并标注 ⭐ NEW
- 📚 更新 `docs/strategies.md`：添加第 4 个策略详细说明，更新对比表格
- 📚 更新 `README.md`：功能特性、策略说明、项目结构

### 策略参数
- 🔧 MACD 默认参数：fast=12, slow=26, signal=9
- 🔧 KDJ 默认参数：n=9, m1=3, m2=3
- 🔧 MACD 优化范围：fast(8-25), slow(20-45), signal(3-15)
- 🔧 KDJ 优化范围：n(5-15), m1(2-5), m2(2-5)
- 🔧 离散仓位表：0/1/3/4/5/6/7/8/10 成（严格离散化）

### 优化
- 🔧 参数优化器使用两阶段网格搜索：
  - 粗粒度搜索：大范围快速扫描（步长 3-5）
  - 精细搜索：最优区域精细调整（步长 1）
  - 测试约 11,000 组参数，耗时 30-90 秒
- 🔧 优化效果显著：默认参数收益 0.61% → 优化参数收益 4.85%（提升 695%）

### 修复
- 🐛 修复参数验证约束：移除 `signal < fast` 限制，允许更大的优化空间
- 🐛 修复收益计算：使用实际股数×价格而非固定单位价值
- 🐛 修复前端显示：优化结果面板正确显示 MACD 和 KDJ 参数

---

## [1.2.0] - 2026-02-17

### 新增
- ✨ **MACD+KDJ 融合策略**：双指标融合策略，MACD 负责方向，KDJ 负责择时
  - MACD 基础强度离散化为 1-10 档
  - KDJ 修正因子（0.6-1.2）动态调整信号强度
  - KDJ 仓位上限：根据 K 值限制最大仓位（3/5/10/6 仓）
  - KDJ 单日加仓限制：根据 KDJ 状态限制单次加仓数量
  - KDJ 风控减仓：高位死叉/J拐头时提前卖出 30%
- ✨ 新策略类型 `macd_kdj` 添加到 `STRATEGY_TYPES`
- ✨ 新增 `MACDKDJSignalGenerator` 类实现融合信号生成
- ✨ 更新回测引擎支持 KDJ 仓位控制和风控减仓

### 文档
- 📚 新增 `docs/MACD_KDJ_GUIDE.md`：MACD+KDJ 融合策略完整指南
- 📚 更新 `docs/INDEX.md`：添加新策略文档链接
- 📚 更新 `docs/MACD_IMPLEMENTATION.md`：添加仓位管理核心逻辑说明
- 📚 更新 `docs/POSITION_MANAGEMENT.md`：详细仓位管理实现机制

### 策略参数
- 🔧 新增 `get_strategy_params('macd_kdj')` 配置
- 🔧 支持 MACD 参数：fast=8, slow=17, signal=5
- 🔧 支持 KDJ 参数：n=9, m1=3, m2=3
- 🔧 支持 KDJ 阈值和因子配置

---

## [1.1.0] - 2026-02-17

### 新增
- ✨ **用户自定义备注功能**：点击备注列可添加/编辑个人备注，保存到 JSON 配置
- ✨ **SQLite 缓存机制**：批量数据使用 SQLite 缓存，首次计算后后续访问速度提升 10 倍+
- ✨ **"近一年收益率"显示**：策略收益率和股票涨幅率都进行年化处理（除以 2）
- ✨ **缓存刷新 API**：新增 `/api/watchlist/refresh-cache` 端点
- ✨ **备注更新 API**：新增 `/api/watchlist/remark` 端点

### 修复
- 🐛 修复表头排序功能：使用 `onclick` 和 `data-sortable` 属性确保事件监听器正确绑定
- 🐛 修复收益率显示不一致问题：策略收益率和股票涨幅率统一为年化收益率

### 优化
- 🔧 删除回测汇总表格，简化首页布局
- 🔧 优化加载逻辑：缓存状态在控制台显示
- 🔧 提升用户体验：刷新时显示进度和结果统计

### 数据库变更
- 📊 新增 `batch_cache` 表用于缓存批量数据

---

## [1.0.0] - 2026-02-16

### 新增
- 🎉 **初始版本发布**
- ✨ 支持 MACD 激进策略、优化做 T 策略、多因子量化策略
- ✨ Web 界面：策略汇总页面和详细策略页面
- ✨ RESTful API：完整的 CRUD 操作
- ✨ 权重优化功能：基于遗传算法和交叉验证
- ✨ 自选列表管理：JSON 文件持久化
- ✨ 回测分析：收益率、夏普比率、最大回撤等指标

### 数据支持
- 📊 支持 52+ 主流 ETF
- 📊 从 Tushare 下载数据功能
- 📊 SQLite 数据库存储

---

## 版本说明

版本号格式：`主版本.次版本.修订版本`

- **主版本**：重大架构变更或不兼容更新
- **次版本**：新功能添加，向后兼容
- **修订版本**：Bug 修复和小优化
