# 多因子量化框架使用指南

## 概述

本框架将原有MACD策略系统升级为**多因子打分模型 + 波动率驱动仓位控制系统**。

## 核心架构

```
指标层（Feature Layer）
    ├── MACD（已有）
    ├── KDJ（新增）
    ├── BOLL（新增）
    ├── 成交量因子（新增）
    ├── ATR波动率因子（新增）
    └── 大盘趋势因子（新增）
        ↓
因子矩阵 X (f_*)
        ↓
模型学习权重（Ridge/Lasso）
        ↓
预测 strength（连续值）
        ↓
ATR仓位管理
        ↓
执行层
```

## 新增模块

### 1. 技术指标扩展 (`indicators.py`)

新增指标：
- **KDJ指标**: `calculate_kdj()` - 随机指标
- **BOLL指标**: `calculate_boll()` - 布林带
- **ATR指标**: `calculate_atr()` - 平均真实波幅
- **成交量因子**: `calculate_volume_factors()` - 成交量分析

### 2. 因子工程模块 (`factors.py`)

`FactorBuilder` 类构建多因子特征矩阵：

```python
from macd_strategy.factors import FactorBuilder

builder = FactorBuilder()
df = builder.build_factor_matrix(data)

# 因子包括：
# - MACD因子: f_macd_trend, f_macd_cross, f_macd_hist_slope
# - KDJ因子: f_k_oversold, f_k_overbought, f_k_slope
# - BOLL因子: f_boll_lower_touch, f_boll_upper_touch, f_boll_position
# - 成交量因子: f_volume_ratio, f_volume_spike
# - 趋势因子: f_ma60_trend, f_price_momentum, f_atr_volatility
```

### 3. 机器学习模型 (`model.py`)

`SignalModel` 类用于预测信号强度：

```python
from macd_strategy.model import SignalModel

model = SignalModel(model_type='ridge', alpha=1.0)

# 准备训练数据
X, y = model.prepare_training_data(df, forward_days=5)

# 训练模型
metrics = model.train(X, y)

# 预测信号强度
strength = model.predict(df)
```

### 4. ATR仓位管理器 (`position_sizer.py`)

`ATRPositionSizer` 类实现波动率驱动的仓位控制：

```python
from macd_strategy.position_sizer import ATRPositionSizer

sizer = ATRPositionSizer(
    initial_capital=2000,
    risk_per_trade=0.01,  # 每笔交易1%风险
    atr_multiplier=2.0    # 2倍ATR作为止损距离
)

# 计算仓位大小
shares = sizer.calculate_position_size(cash, price, atr)

# 计算仓位比例
position_ratio = sizer.calculate_position_ratio(df, idx)
```

### 5. 大盘过滤器 (`market_filter.py`)

`MarketFilter` 类根据市场环境调整仓位：

```python
from macd_strategy.market_filter import MarketFilter

filter = MarketFilter(index_code='000300.SH')

# 获取市场趋势
market_trend = filter.get_market_trend(df_index)

# 应用过滤
df = filter.apply_filter(df, market_trend)
```

### 6. 多因子信号生成器 (`signals.py`)

`MultiFactorSignalGenerator` 整合所有模块：

```python
from macd_strategy.signals import MultiFactorSignalGenerator
from macd_strategy.model import SignalModel
from macd_strategy.position_sizer import ATRPositionSizer

# 创建组件
model = SignalModel()
position_sizer = ATRPositionSizer()

# 创建信号生成器
signal_gen = MultiFactorSignalGenerator(model, position_sizer)

# 生成信号
df = signal_gen.generate_signals(data)

# 或使用大盘过滤
df = signal_gen.generate_signals_with_market_filter(data, df_index)
```

### 7. 多因子回测引擎 (`backtester.py`)

`MultiFactorBacktester` 扩展原有回测引擎：

```python
from macd_strategy.backtester import MultiFactorBacktester

backtester = MultiFactorBacktester(signal_generator)

# 运行回测
result = backtester.run_backtest(
    etf_code='510330.SH',
    start_date='20200101',
    end_date='20231231',
    use_market_filter=True  # 启用大盘过滤
)
```

## 命令行使用

### MACD模式（原有功能）

```bash
# 默认策略
python -m macd_strategy.cli --etf 510330.SH --start 20200101 --end 20231231

# 激进策略
python -m macd_strategy.cli --etf 510330.SH --strategy aggressive

# 列出所有MACD策略
python -m macd_strategy.cli --list-strategies
```

### 多因子模式（新增功能）

```bash
# 默认多因子策略
python -m macd_strategy.cli --etf 510330.SH --mode multifactor --start 20200101 --end 20231231

# 保守策略 + 大盘过滤
python -m macd_strategy.cli --etf 510330.SH --mode multifactor --strategy conservative --market-filter

# 列出所有多因子策略
python -m macd_strategy.cli --mode multifactor --list-strategies
```

## 策略配置

### 多因子策略类型

1. **default**: 默认平衡策略
   - Ridge回归，α=1.0
   - 1%风险每笔交易
   - 2倍ATR止损

2. **conservative**: 保守策略
   - 更高正则化（α=2.0）
   - 更低风险（0.8%）
   - 更宽止损（2.5倍ATR）
   - 启用大盘过滤

3. **aggressive**: 激进策略
   - 更低正则化（α=0.5）
   - 更高风险（1.5%）
   - 更紧止损（1.5倍ATR）

4. **lasso**: Lasso特征选择
   - 使用Lasso回归
   - 自动特征选择
   - α=0.1

## 核心优势

1. **分离方向和风险**
   - 模型预测信号方向
   - ATR控制风险敞口
   - 各司其职，提高稳定性

2. **动态仓位管理**
   - 高波动期自动减仓
   - 低波动期可适当加仓
   - 风险调整后收益

3. **市场环境适应**
   - 牛市：正常仓位
   - 震荡市：50%仓位
   - 熊市：30%仓位或禁止做多

4. **避免未来函数**
   - 所有信号shift(1)
   - 真实模拟交易场景
   - 回测结果可靠

## 性能指标

回测结果包含：
- 总收益率
- 夏普比率
- 最大回撤
- 胜率
- 平均持仓天数
- 止损/止盈次数
- 超额收益（vs Buy&Hold）

## 下一步优化

1. **特征工程**
   - 添加更多技术指标
   - 尝试特征交互
   - 时间序列特征

2. **模型优化**
   - 尝试XGBoost/LightGBM
   - 滚动窗口训练
   - 集成学习

3. **风险控制**
   - Kelly公式仓位管理
   - 组合风险优化
   - 相关性分析

4. **实盘验证**
   - 纸面交易
   - 小资金测试
   - 逐步扩大规模

## 文件结构

```
macd_strategy/
├── __init__.py
├── indicators.py          # 扩展：新增KDJ/BOLL/ATR/成交量
├── factors.py             # 新建：因子特征工程
├── model.py              # 新建：机器学习模型
├── position_sizer.py     # 新建：ATR仓位管理
├── market_filter.py      # 新建：大盘过滤
├── signals.py            # 扩展：新增MultiFactorSignalGenerator
├── backtester.py         # 扩展：新增MultiFactorBacktester
├── strategies.py         # 扩展：新增多因子策略配置
├── cli.py               # 扩展：支持多因子模式
└── utils.py
```

## 技术要点

1. **特征标准化**: 使用StandardScaler标准化因子
2. **防止过拟合**: Ridge/Lasso正则化
3. **数据完整性**: 确保足够历史数据
4. **计算效率**: 向量化操作，避免循环
5. **模块化设计**: 各组件独立，易于测试和扩展
