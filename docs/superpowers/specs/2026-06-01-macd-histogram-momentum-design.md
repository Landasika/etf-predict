# MACD 量能柱动量策略 — 设计规格

## 概述

基于 MACD 量能柱（histogram）变化的新策略，通过跟踪柱体的方向和加速度提前捕捉趋势变化，替代传统金叉/死叉信号。

## 架构

三层解耦：

```
信号生成器 (strategies/macd_histogram_momentum.py)
    ↓ 通过 df['target_position'] 传递
回测引擎 (strategies/macd_histogram_momentum_backtester.py)
    ↑ 注册调度
core/watchlist.py
```

- **信号生成器**：纯计算模块，输入 OHLCV DataFrame，输出含 `target_position`(0-10) 的 DataFrame
- **回测引擎**：纯执行模块，只读 `target_position` 列，不依赖信号生成器的内部逻辑
- **调度层**：在 `core/watchlist.py` 的 `STRATEGY_TYPES` 注册，`calculate_realtime_signal` 添加调度分支

## 信号生成器

### 输入

Pandas DataFrame，包含列：`date`, `open`, `high`, `low`, `close`, `vol`

### 输出列

| 列名 | 类型 | 说明 |
|------|------|------|
| `macd_dif` | float | DIF 线 |
| `macd_dea` | float | DEA 线 |
| `macd_hist` | float | 量能柱 = 2*(DIF-DEA) |
| `hist_state` | str | 六阶段状态 |
| `hist_direction` | str | 柱体方向：EXPANDING/SHRINKING/FLAT |
| `hist_acceleration` | str | 加速度：ACCELERATING/DECELERATING/STEADY |
| `ma20` | float | 20日均线 |
| `ma20_slope` | str | MA20斜率：UP/DOWN/FLAT |
| `target_position` | int | 目标仓位 0-10 |
| `signal_reason` | str | 信号原因文本 |

### 六阶段状态机

| 状态 | 条件 | 含义 |
|------|------|------|
| `STRONG_BULL` | hist > 0 且 hist 在放大 | 多头加速，最强 |
| `BULL_WEAKENING` | hist > 0 且 hist 在缩小 | 多头减速，减速信号 |
| `BEAR_TO_BULL` | hist < 0 且 hist 在向零收缩 | 空头衰竭，加仓信号 |
| `STRONG_BEAR` | hist < 0 且 hist 在放大（更负）| 空头加速，最弱 |
| `JUST_CROSSED_UP` | hist 刚突破 0 向上 | 多空转折确认 |
| `JUST_CROSSED_DOWN` | hist 刚跌破 0 向下 | 多头转空头 |

方向判断：比较 `hist[t]` 与 `hist[t-1]` 的绝对值变化方向。

刚突破判断：当日 hist 与昨日 hist 异号（一个 >0，一个 <0）。

### 仓位计算

```
final = base_position + accel_adjust + ma20_adjust
target_position = clamp(final, 0, 10)

各部分：
  base_position:
    STRONG_BULL      → 9
    BULL_WEAKENING   → 4
    BEAR_TO_BULL     → 2
    STRONG_BEAR      → 0
    JUST_CROSSED_UP  → 6
    JUST_CROSSED_DOWN→ 1

  accel_adjust:
    连续2天柱体变化量递增（同方向）→ 急加速 +2
    连续2天柱体变化量递减（同方向）→ 急减速 -2
    其他（单日变化或方向不一致）→ STEADY 0

  ma20_adjust:
    close > ma20 → +1
    close < ma20 → 最高仓位封顶 5 成（先算前两步再 cap）
    ma20_slope UP → +1
    ma20_slope DOWN → -1
    ma20_slope FLAT → 0
```

MA20 斜率：比较当日 MA20 与 5 日前 MA20。

### 默认 MACD 参数

`fast=12, slow=26, signal=9`（标准参数，与现有策略区分）

## 回测引擎

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `initial_capital` | 2000 | 初始资金 |
| `num_positions` | 10 | 总仓位数 |
| `sell_fee` | 0.005 | 卖出手续费 |
| `stop_loss_pct` | 0.10 | 止损线 -10% |
| `take_profit_pct1` | 0.10 | 止盈1 - 卖30% |
| `take_profit_pct2` | 0.20 | 止盈2 - 卖30% |

### 交易逻辑

以 `target_position` 为驱动：

- 目标仓位 > 当前仓位 → 买入 (目标 - 当前) 成
- 目标仓位 < 当前仓位 → 卖出 (当前 - 目标) 成
- 目标仓位 == 当前仓位 → 持有不动

止损优先级最高：触及 -10% 止损线无视目标仓位，全部清仓。

## 注册

`core/watchlist.py`:

```python
'macd_histogram_momentum': {
    'name': 'MACD量能柱动量策略',
    'description': '基于MACD柱体变化方向和加速度，0-10成动态仓位管理'
}
```

`calculate_realtime_signal` 新增调度分支，`calculate_realtime_signal_macd_histogram_momentum` 函数。

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `strategies/macd_histogram_momentum.py` | 新建 — 信号生成器 |
| `strategies/macd_histogram_momentum_backtester.py` | 新建 — 回测引擎 |
| `core/watchlist.py` | 修改 — 注册策略 + 添加调度函数 |

## 不做什么

- 不修改现有 MACD 策略（macd_aggressive 保持不变）
- 不修改 indicators.py（复用现有 MACDIndicators.calculate_macd）
- 不修改现有回测引擎（新建独立 backtester）
- 不加布林带或波动率过滤（保持策略纯粹，后续可单独加）
