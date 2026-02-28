#!/usr/bin/env python3
"""
MACD Strategy Backtesting CLI

Usage:
    python -m macd_strategy.cli --etf 510330.SH --start 20200101 --end 20231231
    python -m macd_strategy.cli --etf 510330.SH --list-strategies
    python -m macd_strategy.cli --etf 510330.SH --strategy aggressive --start 20200101 --end 20231231
    python -m macd_strategy.cli --etf 510330.SH --mode multifactor --strategy default
"""
import argparse
import sys
import json
from typing import Dict
from .backtester import MACDBacktester, MultiFactorBacktester
from .strategies import get_strategy_params, print_available_strategies, get_multifactor_params, print_available_multifactor_strategies, create_multifactor_components
from .signals import MultiFactorSignalGenerator


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description='MACD Strategy Backtesting - 四大实战方法回测系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --etf 510330.SH --start 20200101 --end 20231231
  %(prog)s --etf 510330.SH --strategy aggressive
  %(prog)s --etf 510330.SH --list-strategies
        """
    )

    parser.add_argument('--etf', type=str, default=None,
                       help='ETF代码 (e.g., 510330.SH)')

    parser.add_argument('--start', type=str, default=None,
                       help='开始日期 (YYYYMMDD, e.g., 20200101)')

    parser.add_argument('--end', type=str, default=None,
                       help='结束日期 (YYYYMMDD, e.g., 20231231)')

    parser.add_argument('--strategy', type=str, default='default',
                       help='策略类型 (default: default)')

    parser.add_argument('--mode', type=str, default='macd',
                       choices=['macd', 'multifactor'],
                       help='回测模式: macd或multifactor (default: macd)')

    parser.add_argument('--list-strategies', action='store_true',
                       help='列出所有可用策略')

    parser.add_argument('--market-filter', action='store_true',
                       help='启用大盘过滤器 (仅multifactor模式)')

    parser.add_argument('--save', action='store_true',
                       help='保存回测结果到数据库')

    parser.add_argument('--verbose', '-v', action='store_true',
                       help='显示详细信息')

    args = parser.parse_args()

    # List strategies if requested
    if args.list_strategies:
        if args.mode == 'multifactor':
            print_available_multifactor_strategies()
        else:
            print_available_strategies()
        return 0

    # Get strategy parameters
    print(f"\n{'='*60}")
    mode_name = '多因子' if args.mode == 'multifactor' else 'MACD'
    print(f"{mode_name}策略回测系统 - {args.strategy.upper()} 策略")
    print(f"{'='*60}\n")

    # Run backtest based on mode
    print(f"开始回测 {args.etf}...")

    try:
        if args.mode == 'multifactor':
            # Multi-factor mode
            params = get_multifactor_params(args.strategy)
            print(f"策略参数:")
            print(f"  - 模型类型: {params.get('model_type')}")
            print(f"  - 正则化系数: {params.get('alpha')}")
            print(f"  - 风险比例: {params.get('risk_per_trade')*100}%")
            print(f"  - ATR倍数: {params.get('atr_multiplier')}")
            print(f"  - 大盘过滤: {args.market_filter}")
            print()

            # Create components
            model, position_sizer = create_multifactor_components(params)

            # Train model on historical data
            print("训练模型...")
            from .factors import FactorBuilder
            factor_builder = FactorBuilder()

            # Load data for training
            temp_backtester = MACDBacktester()
            train_data = temp_backtester._load_data(args.etf, args.start, args.end)

            if train_data is None or len(train_data) == 0:
                raise ValueError(f"无法加载 {args.etf} 的数据")

            # Build factors and train
            train_data = factor_builder.build_factor_matrix(train_data)
            X, y = model.prepare_training_data(train_data, params.get('forward_days', 5))
            model.train(X, y)

            print(f"模型训练完成 (R²={model.score(X, y):.4f})")
            print()

            # Create signal generator
            signal_gen = MultiFactorSignalGenerator(model, position_sizer)

            # Run backtest
            backtester = MultiFactorBacktester(signal_gen)
            result = backtester.run_backtest(
                etf_code=args.etf,
                start_date=args.start,
                end_date=args.end,
                use_market_filter=args.market_filter
            )

            # Print results
            print_multifactor_results(result, verbose=args.verbose)

            # Save to database if requested
            if args.save:
                save_multifactor_result(args.etf, args.strategy, params, result)
                print(f"\n回测结果已保存到数据库")

        else:
            # MACD mode (original)
            params = get_strategy_params(args.strategy)
            print(f"策略参数:")
            print(f"  - 零轴过滤: {params.get('zero_axis_filter')}")
            print(f"  - MA60过滤: {params.get('ma60_filter')}")
            print(f"  - 背离信号: {params.get('enable_divergence')}")
            print(f"  - 鸭嘴形态: {params.get('duck_bill_enable')}")
            print()

            backtester = MACDBacktester()
            result = backtester.run_backtest(
                etf_code=args.etf,
                strategy_params=params,
                start_date=args.start,
                end_date=args.end
            )

            # Print results
            print_results(result, verbose=args.verbose)

            # Save to database if requested
            if args.save:
                save_result(args.etf, args.strategy, params, result)
                print(f"\n回测结果已保存到数据库")

        return 0

    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def print_results(result: Dict, verbose: bool = False):
    """Print backtest results in formatted table"""
    metrics = result['metrics']
    trades = result['trades']
    strategy_params = result['strategy_params']

    print(f"\n{'='*60}")
    print("回测结果")
    print(f"{'='*60}\n")

    # Performance metrics
    print("核心指标:")
    print(f"  初始资金:        ¥{metrics['initial_capital']:,.2f}")
    print(f"  最终资金:        ¥{metrics['final_capital']:,.2f}")
    print(f"  总收益率:        {metrics['total_return_pct']:+.2f}%")
    print(f"  Buy&Hold收益率:  {metrics['buy_hold_return_pct']:+.2f}%")
    print(f"  夏普比率:        {metrics['sharpe_ratio']:.2f}")
    print(f"  最大回撤:        {metrics['max_drawdown']*100:.2f}%")
    print(f"  胜率:            {metrics['win_rate']*100:.2f}%")
    print(f"  平均持仓天数:    {metrics['avg_hold_days']:.1f}天")
    print()

    # Trade statistics
    print("交易统计:")
    print(f"  总交易次数:      {metrics['total_trades']}")
    print(f"  买入信号:        {metrics['buy_signals']}")
    print(f"  卖出信号:        {metrics['sell_signals']}")
    print(f"  止损次数:        {metrics['stop_loss_count']}")
    print(f"  止盈次数:        {metrics['take_profit_count']}")
    print(f"  信号反转平仓:    {metrics['signal_reversal_count']}")
    print(f"  手续费总额:      ¥{metrics['transaction_costs']:.2f}")
    print()

    # Performance vs Buy&Hold
    strategy_return = metrics['total_return_pct']
    buy_hold_return = metrics['buy_hold_return_pct']
    excess_return = strategy_return - buy_hold_return

    print("策略对比:")
    print(f"  超额收益:        {excess_return:+.2f}%")
    if excess_return > 0:
        print(f"  ✓ 策略跑赢Buy&Hold {excess_return:.2f}个百分点")
    else:
        print(f"  ✗ 策略跑输Buy&Hold {abs(excess_return):.2f}个百分点")
    print()

    # Recent trades if verbose
    if verbose and trades:
        print(f"{'='*60}")
        print("最近交易记录:")
        print(f"{'='*60}")
        for trade in trades[-10:]:
            trade_type = trade['type']
            date = trade['date']
            price = trade['price']
            shares = trade['shares']
            value = trade['value']
            reason = trade['reason']

            print(f"  {date} | {trade_type:4s} | {shares:4d}股 @ ¥{price:.2f} | ¥{value:.2f} | {reason}")
        print()


def save_result(etf_code: str, strategy_name: str, params: Dict, result: Dict):
    """Save backtest result to database"""
    from core.database import get_strategy_connection
    import json

    conn = get_strategy_connection()
    cursor = conn.cursor()

    try:
        # Get next iteration number
        cursor.execute('''
            SELECT COALESCE(MAX(iteration_number), 0) + 1
            FROM strategy_iterations
            WHERE etf_code = ?
        ''', (etf_code,))
        iteration_number = cursor.fetchone()[0]

        # Insert strategy iteration
        cursor.execute('''
            INSERT INTO strategy_iterations
            (iteration_number, etf_code, selected_factors, strategy_rationale)
            VALUES (?, ?, ?, ?)
        ''', (
            iteration_number,
            etf_code,
            json.dumps(params),
            f"MACD策略: {strategy_name}\n"
            f"零轴过滤={params.get('zero_axis_filter')}, "
            f"MA60过滤={params.get('ma60_filter')}, "
            f"背离信号={params.get('enable_divergence')}, "
            f"鸭嘴形态={params.get('duck_bill_enable')}"
        ))

        iteration_id = cursor.lastrowid

        # Insert backtest result
        metrics = result['metrics']
        cursor.execute('''
            INSERT INTO backtest_results
            (iteration_id, etf_code, start_date, end_date, initial_capital,
             final_capital, total_return_pct, buy_hold_return_pct, sharpe_ratio,
             max_drawdown, win_rate, total_trades, buy_signals, sell_signals,
             transaction_costs, avg_hold_days, stop_loss_count, take_profit_count,
             signal_reversal_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            iteration_id,
            etf_code,
            result.get('start_date', ''),
            result.get('end_date', ''),
            metrics['initial_capital'],
            metrics['final_capital'],
            metrics['total_return_pct'],
            metrics['buy_hold_return_pct'],
            metrics['sharpe_ratio'],
            metrics['max_drawdown'],
            metrics['win_rate'],
            metrics['total_trades'],
            metrics['buy_signals'],
            metrics['sell_signals'],
            metrics['transaction_costs'],
            metrics['avg_hold_days'],
            metrics['stop_loss_count'],
            metrics['take_profit_count'],
            metrics['signal_reversal_count']
        ))

        backtest_id = cursor.lastrowid

        # Insert trade signals
        for trade in result['trades']:
            cursor.execute('''
                INSERT INTO trade_signals
                (backtest_id, etf_code, signal_date, signal_type,
                 signal_strength, price, position_size, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                backtest_id,
                etf_code,
                trade['date'],
                trade['type'],
                trade.get('signal_strength', 0),
                trade['price'],
                trade['shares'],
                trade.get('reason', '')
            ))

        conn.commit()
        print(f"已保存到数据库 (iteration_id={iteration_id}, backtest_id={backtest_id})")

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def print_multifactor_results(result: Dict, verbose: bool = False):
    """Print multi-factor backtest results in formatted table"""
    metrics = result['metrics']
    trades = result['trades']

    print(f"\n{'='*60}")
    print("多因子回测结果")
    print(f"{'='*60}\n")

    # Performance metrics
    print("核心指标:")
    print(f"  初始资金:        ¥{metrics['initial_capital']:,.2f}")
    print(f"  最终资金:        ¥{metrics['final_capital']:,.2f}")
    print(f"  总收益率:        {metrics['total_return_pct']:+.2f}%")
    print(f"  Buy&Hold收益率:  {metrics['buy_hold_return_pct']:+.2f}%")
    print(f"  夏普比率:        {metrics['sharpe_ratio']:.2f}")
    print(f"  最大回撤:        {metrics['max_drawdown']*100:.2f}%")
    print(f"  胜率:            {metrics['win_rate']*100:.2f}%")
    print(f"  平均持仓天数:    {metrics['avg_hold_days']:.1f}天")
    print()

    # Trade statistics
    print("交易统计:")
    print(f"  总交易次数:      {metrics['total_trades']}")
    print(f"  买入信号:        {metrics['buy_signals']}")
    print(f"  卖出信号:        {metrics['sell_signals']}")
    print(f"  止损次数:        {metrics['stop_loss_count']}")
    print(f"  止盈次数:        {metrics['take_profit_count']}")
    print(f"  信号反转平仓:    {metrics['signal_reversal_count']}")
    print(f"  手续费总额:      ¥{metrics['transaction_costs']:.2f}")
    print()

    # Performance vs Buy&Hold
    strategy_return = metrics['total_return_pct']
    buy_hold_return = metrics['buy_hold_return_pct']
    excess_return = strategy_return - buy_hold_return

    print("策略对比:")
    print(f"  超额收益:        {excess_return:+.2f}%")
    if excess_return > 0:
        print(f"  ✓ 策略跑赢Buy&Hold {excess_return:.2f}个百分点")
    else:
        print(f"  ✗ 策略跑输Buy&Hold {abs(excess_return):.2f}个百分点")
    print()

    # Recent trades if verbose
    if verbose and trades:
        print(f"{'='*60}")
        print("最近交易记录:")
        print(f"{'='*60}")
        for trade in trades[-10:]:
            trade_type = trade['type']
            date = trade['date']
            price = trade['price']
            shares = trade['shares']
            value = trade['value']
            reason = trade['reason']

            print(f"  {date} | {trade_type:4s} | {shares:4d}股 @ ¥{price:.2f} | ¥{value:.2f} | {reason}")
        print()


def save_multifactor_result(etf_code: str, strategy_name: str, params: Dict, result: Dict):
    """Save multi-factor backtest result to database"""
    from core.database import get_strategy_connection

    conn = get_strategy_connection()
    cursor = conn.cursor()

    try:
        # Get next iteration number
        cursor.execute('''
            SELECT COALESCE(MAX(iteration_number), 0) + 1
            FROM strategy_iterations
            WHERE etf_code = ?
        ''', (etf_code,))
        iteration_number = cursor.fetchone()[0]

        # Insert strategy iteration
        cursor.execute('''
            INSERT INTO strategy_iterations
            (iteration_number, etf_code, selected_factors, strategy_rationale)
            VALUES (?, ?, ?, ?)
        ''', (
            iteration_number,
            etf_code,
            json.dumps(params),
            f"多因子策略: {strategy_name}\n"
            f"模型类型={params.get('model_type')}, "
            f"正则化系数={params.get('alpha')}, "
            f"风险比例={params.get('risk_per_trade')}, "
            f"ATR倍数={params.get('atr_multiplier')}"
        ))

        iteration_id = cursor.lastrowid

        # Insert backtest result
        metrics = result['metrics']
        cursor.execute('''
            INSERT INTO backtest_results
            (iteration_id, etf_code, start_date, end_date, initial_capital,
             final_capital, total_return_pct, buy_hold_return_pct, sharpe_ratio,
             max_drawdown, win_rate, total_trades, buy_signals, sell_signals,
             transaction_costs, avg_hold_days, stop_loss_count, take_profit_count,
             signal_reversal_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            iteration_id,
            etf_code,
            result.get('start_date', ''),
            result.get('end_date', ''),
            metrics['initial_capital'],
            metrics['final_capital'],
            metrics['total_return_pct'],
            metrics['buy_hold_return_pct'],
            metrics['sharpe_ratio'],
            metrics['max_drawdown'],
            metrics['win_rate'],
            metrics['total_trades'],
            metrics['buy_signals'],
            metrics['sell_signals'],
            metrics['transaction_costs'],
            metrics['avg_hold_days'],
            metrics['stop_loss_count'],
            metrics['take_profit_count'],
            metrics['signal_reversal_count']
        ))

        backtest_id = cursor.lastrowid

        # Insert trade signals
        for trade in result['trades']:
            cursor.execute('''
                INSERT INTO trade_signals
                (backtest_id, etf_code, signal_date, signal_type,
                 signal_strength, price, position_size, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                backtest_id,
                etf_code,
                trade['date'],
                trade['type'],
                trade.get('signal_strength', 0),
                trade['price'],
                trade['shares'],
                trade.get('reason', '')
            ))

        conn.commit()
        print(f"已保存到数据库 (iteration_id={iteration_id}, backtest_id={backtest_id})")

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


if __name__ == '__main__':
    sys.exit(main())
