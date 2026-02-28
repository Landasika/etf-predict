# MACD激进策略 - 技术实现总结

> **👨‍💻 开发者文档** | 本文档面向开发者，说明MACD策略的技术实现细节、代码流程和架构设计。

**文档目的**：帮助开发者理解系统内部实现，便于二次开发和问题定位。

**适用读者**：后端开发、算法工程师、技术维护人员

---

## 完整实现流程

### 1. 用户操作 → 数据保存
```
用户在Web界面添加ETF "512760.SH" + 策略 "macd_aggressive"
  ↓
API: POST /api/watchlist/add
  ↓
core/watchlist.py: add_to_watchlist()
  ├─ get_etf_info(512760.SH) → "芯片ETF"
  └─ save_watchlist() → 写入 data/watchlist_etfs.json
```

### 2. 加载首页 → 计算信号
```
用户访问 http://127.0.0.1:8001
  ↓
static/js/home.js: loadBatchSignals()
  ├─ fetch('/api/watchlist/batch-signals')
  ↓
api/main.py: get_batch_signals()
  ├─ load_watchlist() → 读取JSON获取ETF列表
  └─ 对每个ETF调用 calculate_realtime_signal()
```

### 3. 信号计算 → 回测执行
```
core/watchlist.py: calculate_realtime_signal()
  ↓
core/watchlist.py: run_macd_backtest_with_settings()
  ├─ get_etf_daily_data(512760.SH, '20240101')
  │   → 返回511天OHLCV数据
  ├─ 创建回测器:
  │   MACDBacktester(
  │     initial_capital=2000,
  │     num_positions=10,
  │     stop_loss_pct=0.05,      # 5%止损
  │     take_profit_pct1=0.10,   # 10%卖30%
  │     take_profit_pct2=0.20    # 20%卖30%
  │   )
  ├─ get_strategy_params('aggressive')
  │   → 返回激进策略过滤参数
  └─ backtester.run_backtest()
```

### 4. 数据处理流程
```
strategies/backtester.py: run_backtest()
  ↓
_load_data():
  ├─ database.get_etf_daily_data() → 获取OHLCV
  ├─ signal_generator.generate_signals()
  │   ├─ indicators.calculate_macd(fast=8, slow=17, signal=5)
  │   │   ├─ ema_fast = close.ewm(span=8).mean()
  │   │   ├─ ema_slow = close.ewm(span=17).mean()
  │   │   ├─ dif = ema_fast - ema_slow
  │   │   ├─ dea = dif.ewm(span=5).mean()
  │   │   └─ 识别金叉: prev_dif <= prev_dea and curr_dif > curr_dea
  │   │       └─ signal_strength = curr_dif - curr_dea (金叉强度)
  │   └─ _apply_strategy_filters(激进参数)
  │       ├─ zero_axis_filter: True, require_zero_above: False (不检查)
  │       ├─ ma60_tolerance: 0.05 (5%容忍度)
  │       ├─ volume_confirm: False (不检查)
  │       └─ divergence_confirm: False (不检查)
  └─ _execute_trades()
      ├─ 循环511天数据
      ├─ 对每天检查BUY/SELL信号
      │
      ├─ 【买入流程】(strategies/backtester.py:390-412)
      │   ├─ if signal_strength > 0:
      │   ├─     # 计算期望仓位
      │   ├─     desired_positions = calculate_desired_positions(signal_strength)
      │   ├─     # 强度映射: 1-3→1-2仓位, 4-6→3-5仓位, 7-9→6-9仓位, 10+→10仓位
      │   ├─     # 计算需要加多少仓位
      │   ├─     positions_to_add = desired_positions - positions_used
      │   ├─     # 检查资金并买入
      │   ├─     investment = positions_to_add * 200
      │   ├─     shares = int(investment / price)
      │   ├─     # 更新加权平均成本
      │   ├─     avg_cost = (avg_cost * position_shares + price * shares) / (position_shares + shares)
      │   ├─     positions_used += positions_to_add
      │   └─
      ├─ 【卖出流程】(strategies/backtester.py:270-340)
      │   ├─ # 止损: -5%全部卖出
      │   ├─ if (price - avg_cost) / avg_cost <= -0.05:
      │   ├─     sell_all()
      │   ├─     positions_used = 0
      │   ├─ # 分批止盈: +10%卖出30%, +20%再卖出30%
      │   ├─ elif (price - avg_cost) / avg_cost >= 0.10:
      │   ├─     sell_portion(0.3)
      │   ├─     positions_used -= int(positions_used * 0.3)
      │   ├─ # 死叉: 全部卖出
      │   ├─ elif signal == 'SELL':
      │   ├─     sell_all()
      │   └─     positions_used = 0
      │
      └─ 记录portfolio_value
```

**仓位管理核心逻辑**：

| 信号强度 | 期望仓位 | 资金投入 | 仓位比例 |
|---------|---------|---------|---------|
| 1 | 1 | 200元 | 5% |
| 2 | 2 | 400元 | 10% |
| 3 | 2 | 400元 | 10% |
| 4 | 3 | 600元 | 15% |
| 5 | 4 | 800元 | 20% |
| 6 | 5 | 1000元 | 25% |
| 7 | 7 | 1400元 | 35% |
| 8 | 8 | 1600元 | 40% |
| 9 | 9 | 1800元 | 45% |
| 10+ | 10 | 2000元 | 50% |

**仓位状态定义**：
- `positions_used = 0` → 空仓，0%仓位
- `positions_used = 5` → 半仓，50%仓位
- `positions_used = 10` → 满仓，100%仓位

详细仓位管理说明见 `docs/POSITION_MANAGEMENT.md`

### 5. 性能指标计算
```
strategies/backtester.py: _calculate_metrics()
  ├─ total_return_pct = (2841.6 - 2000) / 2000 * 100 = 42.08%
  ├─ buy_hold_return_pct = (2.14 - 1.52) / 1.52 * 100 = 40.60%
  ├─ sharpe_ratio = sqrt(252) * mean(daily_returns) / std(daily_returns)
  ├─ max_drawdown_pct = min(drawdown) * 100
  └─ win_rate = 盈利交易次数 / 总交易次数
```

## 关键代码位置

| 功能 | 文件 | 函数/类 | 行数 |
|------|------|---------|------|
| API端点 | api/main.py | get_batch_signals() | 45-134 |
| 添加ETF | core/watchlist.py | add_to_watchlist() | 71-120 |
| 计算信号 | core/watchlist.py | calculate_realtime_signal() | 180-260 |
| 回测执行 | core/watchlist.py | run_macd_backtest_with_settings() | 507-606 |
| 策略参数 | strategies/strategies.py | get_strategy_params('aggressive') | 27-54 |
| 信号生成 | strategies/signals.py | MACDSignalGenerator.generate_signals() | 68-110 |
| 策略过滤 | strategies/signals.py | _apply_strategy_filters() | 112-180 |
| MACD计算 | strategies/indicators.py | calculate_macd() | 20-80 |
| 回测引擎 | strategies/backtester.py | MACDBacktester.run_backtest() | 59-100 |
| 交易执行 | strategies/backtester.py | _execute_trades() | 250-450 |
| 仓位计算 | strategies/backtester.py | 买入与仓位计算 | 390-412 |
| 分批止盈 | strategies/backtester.py | 止盈止损逻辑 | 270-340 |
| 指标计算 | strategies/backtester.py | _calculate_metrics() | 460-540 |

## 数据库结构

```sql
-- 查询ETF历史数据
SELECT trade_date, open, high, low, close, vol
FROM etf_daily
WHERE ts_code = '512760.SH'
  AND trade_date >= '20240101'
ORDER BY trade_date;
```

## JSON配置

```json
{
  "etfs": [
    {
      "code": "512760.SH",
      "name": "芯片ETF",
      "strategy": "macd_aggressive",
      "added_at": "2026-02-16",
      "total_positions": 10,
      "build_position_date": "",
      "position_value": 2000,
      "initial_capital": 2000,
      "remark": "我的自定义备注"
    }
  ],
  "default_etf": "512760.SH",
  "last_updated": "2026-02-16T10:30:00"
}
```

## 执行命令

```bash
# 查看代码
cat strategies/strategies.py | grep -A 30 "aggressive"

# 测试回测
python3 -c "
from core.watchlist import run_backtest
result = run_backtest('512760.SH', '20240101', 'macd_aggressive')
print(result)
"
```

---
**实现总结完成 - 所有代码位置和执行流程已展示**
