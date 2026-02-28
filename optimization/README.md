# 权重优化说明

## 概述

本目录包含ETF权重优化脚本，使用遗传算法和交叉验证来寻找最优策略参数。

## 优化方法

### 1. 遗传算法 (Genetic Algorithm)

模拟生物进化过程的全局优化算法：

- **种群大小**: 50个个体
- **迭代次数**: 100代
- **交叉概率**: 0.8
- **变异概率**: 0.2
- **精英保留**: 前20%直接进入下一代

### 2. 交叉验证 (Cross-Validation)

防止过拟合的验证方法：

- **折数**: 5折（可配置）
- **训练集**: 80%
- **测试集**: 20%
- **评估指标**: 夏普比率优先，其次收益率

## 优化脚本

### optimize_etf_advanced.py

高级优化脚本，功能最全：

```bash
python optimize_etf_advanced.py --etf_code 510330.SH
```

**参数**：
- `--etf_code`: ETF代码（必需）
- `--start_date`: 起始日期（默认：20240101）
- `--end_date`: 结束日期（默认：最新）
- `--cv_folds`: 交叉验证折数（默认：2）
- `--test_size`: 测试集比例（默认：0.2）
- `--population`: 种群大小（默认：50）
- `--generations`: 迭代次数（默认：100）

**优化参数**：
- MACD快线周期：5-20
- MACD慢线周期：15-40
- MACD信号线周期：3-15
- 买入阈值：0.0-1.0
- 卖出阈值：0.0-1.0

**输出**：
- 权重文件：`optimized_weights/{etf_code}_weights.json`
- 优化日志：控制台输出

### optimize_etf_weights.py

基础优化脚本：

```bash
python optimize_etf_weights.py --etf_code 510330.SH
```

**特点**：
- 简单的网格搜索
- 适合快速测试
- 参数范围较窄

### batch_optimize_watchlist.py

批量优化自选列表：

```bash
python batch_optimize_watchlist.py
```

**功能**：
- 自动读取 `data/watchlist_etfs.json`
- 为每个ETF运行优化
- 生成优化报告

**输出**：
- 每个ETF的权重文件
- 汇总报告：`optimization_report.txt`

## 优化流程

### 1. 准备数据

确保数据库有足够的历史数据（建议至少1年）：

```bash
python init_db.py
```

### 2. 运行优化

单个ETF：

```bash
cd optimization
python optimize_etf_advanced.py --etf_code 510330.SH --cv_folds 3
```

批量优化：

```bash
python batch_optimize_watchlist.py
```

### 3. 查看结果

优化完成后，权重保存在：

```
optimized_weights/
├── 510330.SH_weights.json
├── 159672.SZ_weights.json
└── ...
```

权重文件格式：

```json
{
  "etf_code": "510330.SH",
  "optimized_at": "2026-02-16",
  "params": {
    "fast_period": 8,
    "slow_period": 17,
    "signal_period": 5,
    "buy_threshold": 0.65,
    "sell_threshold": 0.35
  },
  "performance": {
    "sharpe_ratio": 1.45,
    "total_return_pct": 18.5,
    "max_drawdown_pct": -8.2
  },
  "cv_scores": [1.42, 1.48, 1.45]
}
```

### 4. 应用权重

权重文件会自动被系统识别。运行回测时：

```python
import requests

response = requests.get(
    'http://127.0.0.1:8000/api/macd/backtest/watchlist/510330.SH'
)
# 系统会自动使用优化后的权重
```

## 性能评估

优化算法会根据以下指标评估参数组合：

1. **夏普比率**（最重要）：
   ```
   Sharpe = (收益率 - 无风险利率) / 波动率
   ```
   - 目标：> 1.5
   - 优秀：> 2.0

2. **总收益率**：
   - 目标：> 15%
   - 优秀：> 25%

3. **最大回撤**：
   - 目标：< -10%
   - 优秀：< -5%

4. **胜率**：
   - 目标：> 50%
   - 优秀：> 60%

## 优化技巧

### 1. 选择合适的回测期间

```bash
# 牛市期间
python optimize_etf_advanced.py --etf_code 510330.SH \
    --start_date 20240101 --end_date 20240630

# 熊市期间
python optimize_etf_advanced.py --etf_code 510330.SH \
    --start_date 20240701 --end_date 20241231

# 完整周期
python optimize_etf_advanced.py --etf_code 510330.SH \
    --start_date 20230101 --end_date 20241231
```

### 2. 调整计算资源

```bash
# 快速测试（牺牲精度）
python optimize_etf_advanced.py --etf_code 510330.SH \
    --cv_folds 2 --population 20 --generations 30

# 精细优化（耗时较长）
python optimize_etf_advanced.py --etf_code 510330.SH \
    --cv_folds 5 --population 100 --generations 200
```

### 3. 参数范围调整

编辑 `optimize_etf_advanced.py`，修改参数范围：

```python
# 扩大搜索范围
param_ranges = {
    'fast_period': (3, 25),      # 原值：(5, 20)
    'slow_period': (10, 50),     # 原值：(15, 40)
    'signal_period': (2, 20)     # 原值：(3, 15)
}
```

### 4. 多策略对比

优化完成后，对比不同策略的效果：

```python
# 优化激进策略
python optimize_etf_advanced.py --etf_code 510330.SH \
    --strategy aggressive --output weights_aggressive.json

# 优化稳健策略
python optimize_etf_advanced.py --etf_code 510330.SH \
    --strategy conservative --output weights_conservative.json

# 对比结果
python compare_strategies.py
```

## 故障排除

### 1. 优化速度慢

**原因**：
- 参数范围太大
- 交叉验证折数太多
- 数据量太大

**解决**：
```bash
# 减少计算量
python optimize_etf_advanced.py --etf_code 510330.SH \
    --cv_folds 2 --population 30 --generations 50
```

### 2. 优化结果不理想

**原因**：
- 数据质量差
- 市场环境不适合该策略
- 参数范围设置不当

**解决**：
```bash
# 1. 检查数据质量
python scripts/check_data.py

# 2. 调整优化期间
python optimize_etf_advanced.py --etf_code 510330.SH \
    --start_date 20230101  # 使用更长历史

# 3. 扩大参数范围
# 编辑脚本中的 PARAM_RANGES
```

### 3. 内存不足

**原因**：
- 种群太大
- 数据加载过多

**解决**：
```bash
# 减少种群大小
python optimize_etf_advanced.py --etf_code 510330.SH \
    --population 20 --generations 50
```

## 最佳实践

1. **定期重新优化**：每季度优化一次
2. **使用足够长的历史数据**：至少1-2年
3. **考虑交易成本**：设置合理的佣金率
4. **避免过拟合**：使用交叉验证
5. **分市场环境优化**：牛市、熊市分别优化

## 高级功能

### 自定义适应度函数

编辑 `optimize_etf_advanced.py`：

```python
def custom_fitness(params, data):
    """自定义适应度函数"""
    backtest = run_backtest_with_params(params, data)

    # 综合评分
    score = (
        backtest['sharpe_ratio'] * 0.5 +
        backtest['total_return_pct'] * 0.01 -
        abs(backtest['max_drawdown_pct']) * 0.02
    )

    return score
```

### 多目标优化

同时优化多个目标：

```python
from deap import algorithms

# 定义多个目标
creator.create("FitnessMulti", base.Fitness, weights=(1.0, -1.0, 1.0))
# 权重表示：(最大化收益, 最小化回撤, 最大化夏普)
```

## 参考资料

- 遗传算法原理：https://en.wikipedia.org/wiki/Genetic_algorithm
- DEAP库文档：https://github.com/DEAP/deap
- 交叉验证：https://scikit-learn.org/stable/modules/cross_validation.html
