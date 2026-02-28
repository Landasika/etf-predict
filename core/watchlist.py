"""
自选ETF管理模块 - 支持多策略选择
策略类型：
- macd_aggressive: MACD激进策略
- optimized_t_trading: MACD优化做T策略
- macd_kdj: MACD+KDJ融合策略
- macd_kdj_position: MACD+KDJ量化管理策略
- multifactor: MACD+KDJ+BOLL量化策略
- rsi_macd_kdj_triple: RSI+MACD+KDJ三指标共振策略
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from core.database import get_etf_info, get_etf_daily_data


# 数据文件路径
WATCHLIST_FILE = 'data/watchlist_etfs.json'

# 策略类型定义
STRATEGY_TYPES = {
    'macd_aggressive': {
        'name': 'MACD激进策略',
        'description': '基于MACD金叉死叉，激进止损止盈'
    },
    'macd_kdj_discrete': {
        'name': 'MACD+KDJ离散仓位系统2.0',
        'description': 'MACD判断趋势，KDJ确定0-10成离散仓位'
    },
    'rsi_macd_kdj_triple': {
        'name': 'RSI+MACD+KDJ三指标共振策略（优化版）',
        'description': 'MA60大趋势过滤 + RSI(14) + MACD(12,26,9)红柱放大 + KDJ(14,3,3)，0-10成精准仓位管理，避免单边下跌反复抄底'
    },
    'pure_rsi': {
        'name': '纯RSI 0-10仓策略',
        'description': '仅基于RSI(9)的纯机械仓位管理，0-10成精准仓位'
    },
    'rsi_triple_lines': {
        'name': 'RSI三线金叉死叉策略',
        'description': 'RSI(6/12/24)三线金叉死叉+多空排列，0-10成趋势仓位管理'
    }
}


def load_watchlist() -> Dict:
    """加载自选ETF列表"""
    if not Path(WATCHLIST_FILE).exists():
        # 创建默认文件
        default_data = {
            "etfs": [],
            "default_etf": None,
            "last_updated": datetime.now().isoformat()
        }
        save_watchlist(default_data)
        return default_data

    try:
        with open(WATCHLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading watchlist: {e}")
        return {"etfs": [], "default_etf": None, "last_updated": datetime.now().isoformat()}


def save_watchlist(data: Dict) -> bool:
    """保存自选ETF列表"""
    try:
        data['last_updated'] = datetime.now().isoformat()
        with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving watchlist: {e}")
        return False


def add_to_watchlist(etf_code: str, strategy: str = 'macd_aggressive') -> Dict:
    """添加ETF到自选

    Args:
        etf_code: ETF代码
        strategy: 策略类型 (macd_aggressive 或 multifactor)

    Returns:
        {'success': bool, 'message': str, 'etf': dict}
    """
    # 检查策略类型是否有效
    if strategy not in STRATEGY_TYPES:
        return {
            'success': False,
            'message': f'无效的策略类型: {strategy}',
            'etf': None
        }

    # 检查ETF是否存在
    etf_info = get_etf_info(etf_code)
    if not etf_info:
        return {
            'success': False,
            'message': f'ETF代码 {etf_code} 不存在',
            'etf': None
        }

    # 加载当前列表
    watchlist = load_watchlist()

    # 检查是否已存在
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            return {
                'success': False,
                'message': f'{etf_code} 已经在自选列表中',
                'etf': etf
            }

    # 添加到列表
    new_etf = {
        'code': etf_code,
        'name': etf_info.get('extname', etf_code),
        'added_at': datetime.now().strftime('%Y-%m-%d'),
        'strategy': strategy
    }

    watchlist['etfs'].append(new_etf)

    # 如果是第一个ETF，设置为默认
    if watchlist['default_etf'] is None:
        watchlist['default_etf'] = etf_code

    # 保存
    if save_watchlist(watchlist):
        return {
            'success': True,
            'message': f'成功添加 {etf_code} 到自选（策略: {STRATEGY_TYPES[strategy]["name"]}）',
            'etf': new_etf
        }
    else:
        return {
            'success': False,
            'message': '保存失败',
            'etf': None
        }


def update_etf_strategy(etf_code: str, strategy: str) -> Dict:
    """更新ETF的策略

    Args:
        etf_code: ETF代码
        strategy: 新的策略类型

    Returns:
        {'success': bool, 'message': str}
    """
    # 检查策略类型是否有效
    if strategy not in STRATEGY_TYPES:
        return {
            'success': False,
            'message': f'无效的策略类型: {strategy}'
        }

    # 加载列表
    watchlist = load_watchlist()

    # 查找并更新ETF
    found = False
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            etf['strategy'] = strategy
            found = True
            break

    if not found:
        return {
            'success': False,
            'message': f'{etf_code} 不在自选列表中'
        }

    # 保存
    if save_watchlist(watchlist):
        return {
            'success': True,
            'message': f'成功更新 {etf_code} 的策略为 {STRATEGY_TYPES[strategy]["name"]}'
        }
    else:
        return {
            'success': False,
            'message': '保存失败'
        }


def remove_from_watchlist(etf_code: str) -> Dict:
    """从自选删除ETF

    Returns:
        {'success': bool, 'message': str}
    """
    watchlist = load_watchlist()

    # 查找并删除
    original_length = len(watchlist['etfs'])
    watchlist['etfs'] = [e for e in watchlist['etfs'] if e['code'] != etf_code]

    if len(watchlist['etfs']) == original_length:
        return {
            'success': False,
            'message': f'{etf_code} 不在自选列表中'
        }

    # 如果删除的是默认ETF，需要重新设置默认
    if watchlist['default_etf'] == etf_code:
        if watchlist['etfs']:
            watchlist['default_etf'] = watchlist['etfs'][0]['code']
        else:
            watchlist['default_etf'] = None

    # 保存
    if save_watchlist(watchlist):
        return {
            'success': True,
            'message': f'成功删除 {etf_code}'
        }
    else:
        return {
            'success': False,
            'message': '保存失败'
        }


def update_etf_remark(etf_code: str, remark: str) -> Dict:
    """更新ETF备注

    Args:
        etf_code: ETF代码
        remark: 备注内容

    Returns:
        {'success': bool, 'message': str}
    """
    watchlist = load_watchlist()

    # 查找ETF
    found = False
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            etf['remark'] = remark
            found = True
            break

    if not found:
        return {
            'success': False,
            'message': f'{etf_code} 不在自选列表中'
        }

    # 保存
    if save_watchlist(watchlist):
        return {
            'success': True,
            'message': f'成功更新 {etf_code} 的备注'
        }
    else:
        return {
            'success': False,
            'message': '保存失败'
        }


def update_etf_settings(etf_code: str, total_positions: int = None, build_position_date: str = None, initial_capital: float = None) -> Dict:
    """更新ETF的高级设置

    Args:
        etf_code: ETF代码
        total_positions: 总仓位数
        build_position_date: 建仓日期 (YYYYMMDD)
        initial_capital: 初始资金

    Returns:
        {'success': bool, 'message': str}
    """
    watchlist = load_watchlist()

    # 查找ETF
    etf = next((e for e in watchlist['etfs'] if e['code'] == etf_code), None)
    if not etf:
        return {
            'success': False,
            'message': f'{etf_code} 不在自选列表中'
        }

    # 更新设置
    if initial_capital is not None:
        etf['initial_capital'] = initial_capital
    if total_positions is not None:
        etf['total_positions'] = total_positions
    if build_position_date is not None:
        etf['build_position_date'] = build_position_date

    # 保存
    if save_watchlist(watchlist):
        return {
            'success': True,
            'message': '设置已保存'
        }
    else:
        return {
            'success': False,
            'message': '保存失败'
        }


def update_etf_position(etf_code: str, position_value: float) -> Dict:
    """更新ETF的当前持仓金额

    Args:
        etf_code: ETF代码
        position_value: 当前持仓金额

    Returns:
        {'success': bool, 'message': str, 'initial_capital': float}
    """
    watchlist = load_watchlist()

    # 查找ETF
    etf = next((e for e in watchlist['etfs'] if e['code'] == etf_code), None)
    if not etf:
        return {
            'success': False,
            'message': f'{etf_code} 不在自选列表中'
        }

    # 保存持仓金额
    etf['position_value'] = position_value

    # 同时更新initial_capital，这样收益计算会基于新的持仓金额
    etf['initial_capital'] = position_value

    # 保存
    if save_watchlist(watchlist):
        return {
            'success': True,
            'message': f'持仓金额已更新为 ¥{position_value:.2f}',
            'initial_capital': position_value  # 返回新的初始资金用于前端显示
        }
    else:
        return {
            'success': False,
            'message': '保存失败'
        }


def _generate_next_action(positions_used: int, latest_signal: Dict, strategy: str) -> str:
    """
    生成下个交易日的操作建议

    Args:
        positions_used: 当前使用的仓位数
        latest_signal: 最新信号数据
        strategy: 策略类型

    Returns:
        操作建议字符串
    """
    signal_strength = latest_signal.get('signal_strength', 0)

    # 获取MACD状态
    macd_dif = latest_signal.get('macd_dif', 0)
    macd_dea = latest_signal.get('macd_dea', 0)
    is_golden_cross = macd_dif > macd_dea
    is_above_zero = macd_dif > 0

    # 生成操作建议
    if positions_used == 0:
        # 空仓状态
        if signal_strength > 0.5:
            return f"🔥 强买入信号，建议建仓3-5成"
        elif signal_strength > 0.2:
            if is_golden_cross and is_above_zero:
                return f"✅ MACD金叉且在零轴上方，建议建仓2-3成"
            else:
                return f"⚡ 有买入信号，可考虑建仓1-2成"
        elif signal_strength > 0:
            return f"⚠️ 信号偏弱，建议观望或小仓位试探"
        elif signal_strength > -0.2:
            return f"👀 观望为主，等待明确信号"
        else:
            return f"⛔ 卖出信号，继续观望等待"

    elif positions_used <= 3:
        # 轻仓状态
        if signal_strength > 0.5:
            return f"🔥 信号强劲，建议加仓至5-7成"
        elif signal_strength > 0.2:
            if is_golden_cross:
                return f"✅ 趋势良好，可继续持有或小幅加仓"
            else:
                return f"⚡ 信号一般，建议持有观望"
        elif signal_strength > 0:
            return f"ℹ️ 信号转弱，建议暂不加仓"
        elif signal_strength > -0.3:
            return f"⚠️ 有调整迹象，可考虑减仓"
        else:
            return f"⛔ 信号转负，建议减仓或清仓"

    elif positions_used <= 7:
        # 中等仓位
        if signal_strength > 0.3:
            return f"✅ 信号良好，建议持有"
        elif signal_strength > 0:
            return f"ℹ️ 信号一般，可持有或小幅减仓"
        elif signal_strength > -0.3:
            return f"⚠️ 信号转弱，建议减仓至3-5成"
        else:
            return f"⛔ 卖出信号，建议减仓至1-2成"

    else:
        # 重仓状态
        if signal_strength > 0.5:
            return f"🔥 信号强劲，继续持有"
        elif signal_strength > 0.2:
            return f"✅ 信号良好，继续持有"
        elif signal_strength > 0:
            return f"⚠️ 信号转弱，建议减仓保住利润"
        elif signal_strength > -0.3:
            return f"⚠️ 有调整风险，建议减仓至5成以下"
        else:
            return f"⛔ 信号转负，建议大幅减仓或清仓"


def calculate_realtime_signal(etf_code: str, start_date: str = '20250101', strategy: str = None) -> Dict:
    """计算ETF的实时信号和持仓状态

    Args:
        etf_code: ETF代码
        start_date: 回测开始日期
        strategy: 策略类型（如果不指定，从watchlist读取）

    Returns:
        {
            'success': bool,
            'message': str,
            'data': {
                'position_value': float,
                'profit': float,
                'profit_pct': float,
                'positions_used': int,  # 新增：当前使用的仓位数
                'signal_strength': float,
                'next_action': str,
                'latest_data': dict,
                'backtest_summary': dict
            }
        }
    """
    # 如果没有指定策略，从watchlist读取
    watchlist = load_watchlist()
    etf_settings = {}
    if strategy is None:
        for etf in watchlist['etfs']:
            if etf['code'] == etf_code:
                strategy = etf.get('strategy', 'macd_aggressive')
                etf_settings = {
                    'initial_capital': etf.get('initial_capital', 2000),
                    'total_positions': etf.get('total_positions', 10),
                    'build_position_date': etf.get('build_position_date', None),
                    'optimized_macd_params': etf.get('optimized_macd_params', None),
                    'optimized_params': etf.get('optimized_params', None)  # 用于macd_kdj_discrete策略
                }
                break
        else:
            strategy = 'macd_aggressive'
    else:
        # 即使指定了策略，也要读取设置
        for etf in watchlist['etfs']:
            if etf['code'] == etf_code:
                etf_settings = {
                    'initial_capital': etf.get('initial_capital', 2000),
                    'total_positions': etf.get('total_positions', 10),
                    'build_position_date': etf.get('build_position_date', None),
                    'optimized_macd_params': etf.get('optimized_macd_params', None),
                    'optimized_params': etf.get('optimized_params', None)  # 用于macd_kdj_discrete策略
                }
                break

    # 根据策略类型调用不同的计算函数
    if strategy == 'macd_aggressive':
        # MACD激进策略
        return calculate_realtime_signal_macd(etf_code, start_date, etf_settings, strategy)
    elif strategy == 'macd_kdj_discrete':
        # MACD+KDJ离散仓位系统
        return calculate_realtime_signal_macd_kdj_discrete(etf_code, start_date, etf_settings)
    elif strategy == 'rsi_macd_kdj_triple':
        # RSI+MACD+KDJ三指标共振策略
        return calculate_realtime_signal_rsi_macd_kdj_triple(etf_code, start_date, etf_settings)
    elif strategy == 'pure_rsi':
        # 纯RSI 0-10仓策略
        return calculate_realtime_signal_pure_rsi(etf_code, start_date, etf_settings)
    elif strategy == 'rsi_triple_lines':
        # RSI三线金叉死叉策略
        return calculate_realtime_signal_rsi_triple_lines(etf_code, start_date, etf_settings)
    else:
        return {
            'success': False,
            'message': f'不支持的策略类型: {strategy}',
            'data': None
        }


def run_macd_backtest_with_settings(etf_code: str, start_date: str, strategy: str,
                                     initial_capital: int = 2000, num_positions: int = 10,
                                     build_date: str = None, optimized_macd_params: Dict = None) -> Dict:
    """运行MACD策略回测（带参数）

    Args:
        etf_code: ETF代码
        start_date: 回测开始日期
        strategy: 策略类型
        initial_capital: 初始资金
        num_positions: 总仓位数
        build_date: 建仓日期
        optimized_macd_params: 优化后的MACD参数 {'macd_fast': int, 'macd_slow': int, 'macd_signal': int}

    Returns:
        回测结果
    """
    try:
        from strategies.backtester import MACDBacktester
        from strategies.strategies import get_strategy_params
    except ImportError as e:
        return {
            'success': False,
            'message': f'无法导入MACD回测模块: {e}',
            'data': None
        }

    # 加载数据
    data = get_etf_daily_data(etf_code, start_date)
    if not data or len(data) < 60:
        return {
            'success': False,
            'message': f'数据不足（至少需要60天，当前有{len(data) if data else 0}天）',
            'data': None
        }

    df = pd.DataFrame(data)

    # 如果有建仓日期，需要特殊处理
    if build_date:
        build_date_int = int(build_date)

        # 找到建仓日期在数据中的索引
        build_idx = None
        for i, row in df.iterrows():
            date_int = int(row['trade_date'].replace('-', ''))
            if date_int >= build_date_int:
                build_idx = i
                break

        if build_idx is None or build_idx < 30:
            return {
                'success': False,
                'message': f'建仓日期 {build_date} 无效或数据不足',
                'data': None
            }

        print(f"[建仓回测] 建仓日期: {build_date}, 建仓索引: {build_idx}, 总数据: {len(df)}, 初始资金: {initial_capital}")

        # 根据策略类型选择回测参数
        if strategy == 'optimized_t_trading':
            # 优化做T策略：宽松止损，分批止盈，追踪止盈
            backtester = MACDBacktester(
                initial_capital=initial_capital,
                sell_fee=0.005,
                num_positions=num_positions,
                stop_loss_pct=0.20,  # -20%止损
                take_profit_pct1=0.10,  # +10%卖出30%
                take_profit_pct2=0.20,  # +20%卖出30%
                take_profit_pct3=0.35,  # +35%卖出40%
                enable_trailing_stop=True,  # 启用追踪止盈
                trailing_stop_pct=0.05,
                trailing_stop_activation=0.15
            )
            strategy_params = get_strategy_params('optimized_t_trading')
        elif strategy == 'macd_kdj':
            # MACD+KDJ融合策略：标准止损止盈，信号生成器使用KDJ融合
            backtester = MACDBacktester(
                initial_capital=initial_capital,
                sell_fee=0.005,
                num_positions=num_positions,
                stop_loss_pct=0.05,  # -5%止损
                take_profit_pct1=0.10,  # +10%卖出30%
                take_profit_pct2=0.20   # +20%卖出30%
            )
            strategy_params = get_strategy_params('macd_kdj')
        else:
            # 默认激进策略
            backtester = MACDBacktester(
                initial_capital=initial_capital,
                sell_fee=0.005,
                num_positions=num_positions,
                stop_loss_pct=0.05,
                take_profit_pct1=0.10,
                take_profit_pct2=0.20
            )
            strategy_params = get_strategy_params('aggressive')

        # 如果有优化后的MACD参数，覆盖默认值
        if optimized_macd_params:
            strategy_params['macd_fast'] = optimized_macd_params['macd_fast']
            strategy_params['macd_slow'] = optimized_macd_params['macd_slow']
            strategy_params['macd_signal'] = optimized_macd_params['macd_signal']

        # 运行回测
        try:
            result = backtester.run_backtest(
                etf_code=etf_code,
                strategy_params=strategy_params,
                start_date=start_date,
                end_date=None
            )
        except Exception as e:
            return {
                'success': False,
                'message': f'回测失败: {str(e)}',
                'data': None
            }

        # 提取数据
        trades = result.get('trades', [])
        performance = result.get('performance', [])
        metrics = result.get('metrics', {})

        # 过滤：只保留建仓日期后的交易记录
        filtered_trades = [t for t in trades if int(t['date'].replace('-', '')) >= build_date_int]

        # 过滤：只保留建仓日期后的performance数据
        filtered_performance = [p for p in performance if int(p['date'].replace('-', '')) >= build_date_int]

        if len(filtered_performance) == 0:
            return {
                'success': False,
                'message': '建仓日期后无数据',
                'data': None
            }

        # 获取建仓日期时的资产作为新的初始值
        initial_capital_at_build = filtered_performance[0]['portfolio_value']
        initial_price_at_build = filtered_performance[0]['price']

        # 重新计算收益曲线（从建仓日期开始，收益从0开始）
        dates = [p['date'] for p in filtered_performance]
        prices = [p['price'] for p in filtered_performance]
        strategy_values = [(p['portfolio_value'] - initial_capital_at_build) for p in filtered_performance]
        benchmark_values = [((p['price'] - initial_price_at_build) / initial_price_at_build * initial_capital_at_build) for p in filtered_performance]

        # 计算最终收益
        final_value = filtered_performance[-1]['portfolio_value']
        adjusted_profit = final_value - initial_capital_at_build
        adjusted_return_pct = (adjusted_profit / initial_capital_at_build) * 100 if initial_capital_at_build > 0 else 0

        # 重新计算交易统计
        total_trades = len(filtered_trades)
        win_trades = len([t for t in filtered_trades if t.get('pnl', 0) > 0])
        win_rate = (win_trades / total_trades) if total_trades > 0 else 0

        # 更新metrics
        metrics['initial_capital'] = initial_capital_at_build
        metrics['final_capital'] = final_value
        metrics['total_return'] = adjusted_profit
        metrics['total_return_pct'] = adjusted_return_pct
        metrics['build_position_date'] = build_date
        metrics['buy_hold_return'] = benchmark_values[-1]
        metrics['buy_hold_return_pct'] = (benchmark_values[-1] / initial_capital_at_build) * 100
        metrics['total_trades'] = total_trades
        metrics['trades'] = total_trades
        metrics['win_rate'] = win_rate

        # 过滤后的交易记录
        trades = filtered_trades

        print(f"[建仓回测完成] 初始资产: {initial_capital_at_build:.2f}, 最终: {final_value:.2f}, 收益: {adjusted_profit:.2f} ({adjusted_return_pct:.2f}%), 交易次数: {total_trades}")

    else:
        # 没有建仓日期，正常回测
        # 根据策略类型选择回测参数
        if strategy == 'optimized_t_trading':
            # 优化做T策略：宽松止损，分批止盈，追踪止盈
            backtester = MACDBacktester(
                initial_capital=initial_capital,
                sell_fee=0.005,
                num_positions=num_positions,
                stop_loss_pct=0.20,  # -20%止损
                take_profit_pct1=0.10,  # +10%卖出30%
                take_profit_pct2=0.20,  # +20%卖出30%
                take_profit_pct3=0.35,  # +35%卖出40%
                enable_trailing_stop=True,  # 启用追踪止盈
                trailing_stop_pct=0.05,
                trailing_stop_activation=0.15
            )
            strategy_params = get_strategy_params('optimized_t_trading')
        elif strategy == 'macd_kdj':
            # MACD+KDJ融合策略：标准止损止盈，信号生成器使用KDJ融合
            backtester = MACDBacktester(
                initial_capital=initial_capital,
                sell_fee=0.005,
                num_positions=num_positions,
                stop_loss_pct=0.05,  # -5%止损
                take_profit_pct1=0.10,  # +10%卖出30%
                take_profit_pct2=0.20   # +20%卖出30%
            )
            strategy_params = get_strategy_params('macd_kdj')
        else:
            # 默认激进策略
            backtester = MACDBacktester(
                initial_capital=initial_capital,
                sell_fee=0.005,
                num_positions=num_positions,
                stop_loss_pct=0.05,
                take_profit_pct1=0.10,
                take_profit_pct2=0.20
            )
            strategy_params = get_strategy_params('aggressive')

        # 如果有优化后的MACD参数，覆盖默认值
        if optimized_macd_params:
            strategy_params['macd_fast'] = optimized_macd_params['macd_fast']
            strategy_params['macd_slow'] = optimized_macd_params['macd_slow']
            strategy_params['macd_signal'] = optimized_macd_params['macd_signal']

        try:
            result = backtester.run_backtest(
                etf_code=etf_code,
                strategy_params=strategy_params,
                start_date=start_date,
                end_date=None
            )
        except Exception as e:
            return {
                'success': False,
                'message': f'回测失败: {str(e)}',
                'data': None
            }

        trades = result.get('trades', [])
        performance = result.get('performance', [])
        metrics = result.get('metrics', {})

        if isinstance(performance, pd.DataFrame) and len(performance) > 0:
            # performance是DataFrame，使用列名访问
            dates = performance['date'].tolist()
            strategy_values = [(performance['portfolio_value'].iloc[i] - initial_capital) for i in range(len(performance))]
            initial_price = performance['price'].iloc[0]
            benchmark_values = [((performance['price'].iloc[i] - initial_price) / initial_price * initial_capital) for i in range(len(performance))]
            prices = performance['price'].tolist()
            # 添加成交量数据
            volumes = performance['vol'].tolist() if 'vol' in performance.columns else []
        elif isinstance(performance, list) and len(performance) > 0:
            # performance是list（向后兼容）
            dates = [p['date'] for p in performance]
            strategy_values = [(p['portfolio_value'] - initial_capital) for p in performance]
            initial_price = performance[0]['price']
            benchmark_values = [((p['price'] - initial_price) / initial_price * initial_capital) for p in performance]
            prices = [p['price'] for p in performance]
            # 添加成交量数据
            volumes = [p.get('vol', 0) for p in performance]
        else:
            return {
                'success': False,
                'message': '回测数据格式错误',
                'data': None
            }

    # 提取买卖信号
    buy_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'positions': t.get('positions_added', 1),
            'strength': t.get('signal_strength', 0)
        }
        for t in trades if t['type'] == 'BUY'
    ]

    sell_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'reason': t.get('reason', 'SIGNAL'),
            'strength': t.get('signal_strength', 0),
            'positions_closed': t.get('positions_closed', 0)
        }
        for t in trades if t['type'] == 'SELL'
    ]

    # 获取最新仓位（从performance记录的最后一个）
    latest_positions_used = performance[-1].get('positions_used', 0) if len(performance) > 0 else 0

    # 获取前一天的持仓数（用于判断信号类型）
    previous_positions_used = performance[-2].get('positions_used', 0) if len(performance) > 1 else 0

    # 根据持仓变化判断信号类型
    if latest_positions_used > previous_positions_used:
        signal_type = 'BUY'  # 加仓
    elif latest_positions_used < previous_positions_used:
        signal_type = 'SELL'  # 减仓
    else:
        signal_type = 'HOLD'  # 持仓不变

    # 获取最新信号
    latest_signal = {
        'date': dates[-1] if dates else '',
        'close': prices[-1] if prices else 0,
        'signal_strength': 0,
        'signal_type': signal_type,  # 基于持仓变化
        'positions_used': latest_positions_used,
        'previous_positions_used': previous_positions_used  # 添加前一日持仓
    }

    # 计算MACD指标
    try:
        from strategies.indicators import MACDIndicators
        df_with_macd = MACDIndicators.calculate_macd(df.copy())

        if len(df_with_macd) > 0:
            latest_row = df_with_macd.iloc[-1]
            latest_signal.update({
                'macd_dif': float(latest_row.get('macd_dif', 0)),
                'macd_dea': float(latest_row.get('macd_dea', 0)),
                'macd_hist': float(latest_row.get('macd_hist', 0)),
                'signal_strength': float(latest_row.get('macd_dif', 0) - latest_row.get('macd_dea', 0))
            })
    except Exception as e:
        print(f"计算MACD指标失败: {e}")

    # 计算KDJ指标（用于显示，所有策略都计算）
    try:
        from strategies.indicators import MACDIndicators
        df_with_kdj = MACDIndicators.calculate_kdj(df.copy())

        if len(df_with_kdj) > 0:
            latest_row = df_with_kdj.iloc[-1]
            latest_signal.update({
                'kdj_k': float(latest_row.get('kdj_k', 0)),
                'kdj_d': float(latest_row.get('kdj_d', 0)),
                'kdj_j': float(latest_row.get('kdj_j', 0))
            })
    except Exception as e:
        print(f"计算KDJ指标失败: {e}")

    # 构建返回数据
    return {
        'success': True,
        'data': {
            'latest_date': latest_signal['date'],  # 最新数据日期
            'position_value': metrics['final_capital'],
            'profit': metrics.get('total_return', metrics['final_capital'] - initial_capital),
            'profit_pct': metrics['total_return_pct'],
            'positions_used': latest_positions_used,  # 当前仓位数
            'signal_strength': latest_signal['signal_strength'],
            'next_action': _generate_next_action(latest_positions_used, latest_signal, strategy),
            'latest_data': latest_signal,
            'backtest_summary': {
                'trades': metrics.get('total_trades', metrics.get('trades', 0)),
                'buy_hold_return_pct': metrics.get('buy_hold_return_pct', 0),
                'max_drawdown': metrics.get('max_drawdown', 0),
                'win_rate': metrics.get('win_rate', 0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'initial_capital': metrics.get('initial_capital', initial_capital),  # 添加初始资本信息
                'build_position_date': metrics.get('build_position_date', None)  # 添加建仓日期信息
            },
            'dates': dates,
            'prices': prices,
            'volumes': volumes,  # 添加成交量数据
            'strategy_values': strategy_values,
            'benchmark_values': benchmark_values,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals
        },
        'strategy': strategy
    }


def run_macd_backtest(etf_code: str, start_date: str = '20250101', strategy: str = None,
                       initial_capital: int = 2000, num_positions: int = 10, build_date: str = None,
                       optimized_macd_params: Dict = None) -> Dict:
    """运行MACD回测（便捷函数）

    Args:
        etf_code: ETF代码
        start_date: 开始日期
        strategy: 策略类型
        initial_capital: 初始资金
        num_positions: 仓位数
        build_date: 建仓日期
        optimized_macd_params: 优化后的MACD参数 {'macd_fast': int, 'macd_slow': int, 'macd_signal': int}

    Returns:
        回测结果
    """
    return run_macd_backtest_with_settings(etf_code, start_date, strategy or 'macd_aggressive',
                                            initial_capital, num_positions, build_date,
                                            optimized_macd_params=optimized_macd_params)


def calculate_realtime_signal_macd(etf_code: str, start_date: str = '20250101', etf_settings: Dict = None, strategy: str = 'macd_aggressive') -> Dict:
    """计算MACD策略的实时信号

    Args:
        etf_code: ETF代码
        start_date: 回测开始日期
        etf_settings: ETF设置 {'initial_capital': int, 'total_positions': int, 'build_position_date': str, 'optimized_macd_params': dict}
        strategy: 策略类型（macd_aggressive 或 optimized_t_trading）
    """
    if etf_settings is None:
        etf_settings = {}

    initial_capital = etf_settings.get('initial_capital', 2000)
    total_positions = etf_settings.get('total_positions', 10)
    build_position_date = etf_settings.get('build_position_date', None)
    optimized_macd_params = etf_settings.get('optimized_macd_params', None)

    # 运行回测（传递策略类型和优化参数）
    backtest_result = run_macd_backtest(etf_code, start_date, strategy=strategy,
                                       initial_capital=initial_capital,
                                       num_positions=total_positions,
                                       build_date=build_position_date,
                                       optimized_macd_params=optimized_macd_params)

    if not backtest_result['success']:
        return backtest_result

    # 直接返回数据（已经在 run_macd_backtest_with_settings 中格式化好了）
    return backtest_result


def calculate_realtime_signal_macd_kdj_discrete(etf_code: str, start_date: str = '20250101', etf_settings: Dict = None) -> Dict:
    """计算MACD+KDJ离散仓位系统的实时信号

    Args:
        etf_code: ETF代码
        start_date: 回测开始日期
        etf_settings: ETF设置 {'initial_capital': int, 'total_positions': int, 'build_position_date': str, 'optimized_params': dict}
    """
    if etf_settings is None:
        etf_settings = {}

    initial_capital = etf_settings.get('initial_capital', 2000)
    total_positions = etf_settings.get('total_positions', 10)
    build_position_date = etf_settings.get('build_position_date', None)
    optimized_params = etf_settings.get('optimized_params', None)

    # 加载数据
    data = get_etf_daily_data(etf_code, start_date)
    if not data or len(data) < 60:
        return {
            'success': False,
            'message': f'数据不足（至少需要60天，当前有{len(data) if data else 0}天）',
            'data': None
        }

    df = pd.DataFrame(data)

    # 生成信号（使用优化参数）
    from strategies.macd_kdj_discrete import MACDKDJDiscreteSignalGenerator
    signal_gen = MACDKDJDiscreteSignalGenerator(optimized_params)
    df = signal_gen.generate_signals(df)

    # 运行回测（使用优化参数）
    from strategies.macd_kdj_discrete_backtester import MACDKDJDiscreteBacktester
    backtester = MACDKDJDiscreteBacktester(
        initial_capital=initial_capital,
        total_positions=total_positions
    )

    backtest_result = backtester.run_backtest(etf_code, start_date, strategy_params=optimized_params)

    if not backtest_result['success']:
        return backtest_result

    # 提取数据
    trades = backtest_result.get('trades', [])
    performance = backtest_result.get('performance', [])
    metrics = backtest_result.get('metrics', {})

    if isinstance(performance, list) and len(performance) > 0:
        dates = [p['date'] for p in performance]
        prices = [p['price'] for p in performance]
        strategy_values = [(p['portfolio_value'] - initial_capital) for p in performance]
        initial_price = performance[0]['price']
        benchmark_values = [((p['price'] - initial_price) / initial_price * initial_capital) for p in performance]
        volumes = [p.get('vol', 0) for p in data if p.get('trade_date') in dates]
    else:
        return {
            'success': False,
            'message': '回测数据格式错误',
            'data': None
        }

    # 获取最新信号
    latest = df.iloc[-1]

    # 获取当前仓位（从performance最后一条记录）
    current_positions = performance[-1].get('position_units', 0) if performance else 0

    # 获取前一天的仓位（用于判断信号类型）
    previous_positions = performance[-2].get('position_units', 0) if len(performance) > 1 else 0

    # 根据持仓变化判断信号类型
    if current_positions > previous_positions:
        signal_type = 'BUY'  # 加仓
    elif current_positions < previous_positions:
        signal_type = 'SELL'  # 减仓
    else:
        signal_type = 'HOLD'  # 持仓不变

    # 买卖信号
    buy_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'positions': t.get('units', 0),
            'strength': 0
        }
        for t in trades if t['type'] == 'BUY'
    ]

    sell_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'reason': t.get('reason', 'SIGNAL'),
            'strength': 0,
            'positions_closed': t.get('units', 0)
        }
        for t in trades if t['type'] == 'SELL'
    ]

    latest_signal = {
        'date': str(latest['date']) if 'date' in latest else '',
        'close': float(latest['close']),
        'macd_dif': float(latest.get('macd_dif', 0)),
        'macd_dea': float(latest.get('macd_dea', 0)),
        'macd_hist': float(latest.get('macd_hist', 0)),
        'kdj_k': float(latest.get('kdj_k', 0)),
        'kdj_d': float(latest.get('kdj_d', 0)),
        'kdj_j': float(latest.get('kdj_j', 0)),
        'trend': latest.get('trend', 'UNKNOWN'),
        'target_position': int(latest.get('target_position', 0)),
        'exec_position': int(latest.get('exec_position', 0)),
        'signal_strength': current_positions / 10.0,  # 转换为0-1范围
        'signal_type': signal_type,  # 基于持仓变化
        'positions_used': current_positions,
        'previous_positions_used': previous_positions,  # 添加前一日持仓
        'signal_reason': latest.get('signal_reason', '')
    }

    # 生成操作建议
    next_action = _generate_next_action_macd_kdj_discrete(
        current_positions,
        latest_signal
    )

    return {
        'success': True,
        'data': {
            'latest_date': latest_signal['date'],
            'position_value': metrics.get('final_value', initial_capital),
            'profit': metrics.get('final_value', initial_capital) - initial_capital,
            'profit_pct': metrics.get('total_return_pct', 0),
            'positions_used': current_positions,
            'signal_strength': latest_signal['signal_strength'],
            'next_action': next_action,
            'latest_data': latest_signal,
            'backtest_summary': {
                'trades': metrics.get('total_trades', 0),
                'buy_hold_return_pct': 0,  # TODO: calculate
                'max_drawdown': metrics.get('max_drawdown_pct', 0),
                'win_rate': metrics.get('win_rate_pct', 0),
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'initial_capital': metrics.get('initial_capital', initial_capital),
                'build_position_date': build_position_date
            },
            'summary': {
                'total_return_pct': metrics.get('total_return_pct', 0),
                'benchmark_return_pct': 0,  # TODO: calculate
                'sharpe_ratio': metrics.get('sharpe_ratio', 0),
                'max_drawdown_pct': metrics.get('max_drawdown_pct', 0),
                'win_rate': metrics.get('win_rate_pct', 0),
                'total_trades': metrics.get('total_trades', 0)
            },
            'dates': dates,
            'prices': prices,
            'volumes': volumes,
            'strategy_values': strategy_values,
            'benchmark_values': benchmark_values,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals
        },
        'strategy': 'macd_kdj_discrete'
    }


def _generate_next_action_macd_kdj_discrete(positions_used: int, latest_signal: Dict) -> str:
    """
    生成MACD+KDJ离散仓位系统的操作建议

    Args:
        positions_used: 当前使用的仓位数 (0-10)
        latest_signal: 最新信号数据

    Returns:
        操作建议字符串
    """
    target_position = latest_signal.get('target_position', 0)
    trend = latest_signal.get('trend', 'BEAR')
    kdj_k = latest_signal.get('kdj_k', 50)
    signal_reason = latest_signal.get('signal_reason', '')

    # MACD空头趋势
    if trend == 'BEAR':
        if positions_used > 0:
            return f"⛔ MACD空头趋势，建议清仓（当前{positions_used}成）"
        else:
            return f"⛔ MACD空头趋势，继续空仓观望"

    # MACD多头趋势
    if positions_used == 0:
        # 空仓状态
        if target_position >= 5:
            return f"🔥 {signal_reason}，建议建仓{target_position}成"
        elif target_position >= 3:
            return f"⚡ {signal_reason}，可建仓{target_position}成"
        else:
            return f"👀 观望为主，等待更好时机"

    elif positions_used <= 3:
        # 轻仓状态
        if target_position > positions_used + 2:
            return f"🔥 {signal_reason}，建议加仓至{target_position}成"
        elif target_position > positions_used:
            return f"✅ {signal_reason}，可小幅加仓"
        elif target_position == positions_used:
            return f"ℹ️ {signal_reason}，继续持有"
        else:
            return f"⚠️ {signal_reason}，建议减仓"

    elif positions_used <= 7:
        # 中等仓位
        if target_position >= 8:
            return f"🔥 {signal_reason}，建议加仓至{target_position}成"
        elif target_position > positions_used:
            return f"✅ {signal_reason}，可继续加仓"
        elif target_position == positions_used:
            return f"ℹ️ {signal_reason}，继续持有"
        else:
            return f"⚠️ {signal_reason}，建议减仓至{target_position}成"

    else:
        # 重仓状态
        if target_position >= 8:
            return f"🔥 {signal_reason}，继续持有"
        elif target_position >= 5:
            return f"✅ {signal_reason}，继续持有"
        else:
            return f"⚠️ {signal_reason}，建议减仓至{target_position}成"


def calculate_realtime_signal_rsi_macd_kdj_triple(etf_code: str, start_date: str = '20250101', etf_settings: Dict = None) -> Dict:
    """计算RSI+MACD+KDJ三指标共振策略的实时信号

    Args:
        etf_code: ETF代码
        start_date: 回测开始日期
        etf_settings: ETF设置 {'initial_capital': int, 'total_positions': int, 'build_position_date': str}
    """
    if etf_settings is None:
        etf_settings = {}

    initial_capital = etf_settings.get('initial_capital', 2000)
    total_positions = etf_settings.get('total_positions', 10)
    build_position_date = etf_settings.get('build_position_date', None)

    # 加载数据
    data = get_etf_daily_data(etf_code, start_date)
    if not data or len(data) < 60:
        return {
            'success': False,
            'message': f'数据不足（至少需要60天，当前有{len(data) if data else 0}天）',
            'data': None
        }

    df = pd.DataFrame(data)

    # 辅助函数：安全转换值为JSON兼容类型
    def safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            f = float(value)
            return default if (np.isnan(f) or np.isinf(f)) else f
        except (ValueError, TypeError):
            return default

    def safe_int(value, default=0):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    # 生成信号
    from strategies.rsi_macd_kdj_triple import RSIMACDKDJTripleSignalGenerator
    signal_gen = RSIMACDKDJTripleSignalGenerator()
    df = signal_gen.generate_signals(df)

    # 运行回测
    from strategies.rsi_macd_kdj_triple_backtester import RSIMACDKDJTripleBacktester
    backtester = RSIMACDKDJTripleBacktester(
        initial_capital=initial_capital,
        total_positions=total_positions
    )

    backtest_result = backtester.run_backtest(etf_code, start_date)

    if not backtest_result['success']:
        return backtest_result

    # 提取数据
    trades = backtest_result.get('trades', [])
    performance = backtest_result.get('performance', [])
    metrics = backtest_result.get('metrics', {})

    # 处理performance中的NaN值
    if isinstance(performance, list) and len(performance) > 0:
        # 将所有NaN值替换为None或0
        for p in performance:
            for key, value in p.items():
                if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                    if key in ['macd_trend', 'rsi_zone', 'signal_reason']:
                        p[key] = ''
                    elif key in ['kdj_golden_cross', 'kdj_dead_cross']:
                        p[key] = False
                    else:
                        p[key] = 0
                # 将numpy类型转换为Python原生类型
                if isinstance(value, (np.integer, np.floating)):
                    p[key] = float(value) if isinstance(value, np.floating) else int(value)

    if isinstance(performance, list) and len(performance) > 0:
        dates = [p['date'] for p in performance]
        prices = [safe_float(p['price']) for p in performance]
        strategy_values = [safe_float(p['portfolio_value']) - initial_capital for p in performance]
        initial_price = safe_float(performance[0]['price'])
        # 避免除零
        if initial_price > 0:
            benchmark_values = [safe_float((safe_float(p['price']) - initial_price) / initial_price * initial_capital) for p in performance]
        else:
            benchmark_values = [0.0] * len(performance)
        volumes = [safe_float(p.get('vol', 0)) for p in performance]
    else:
        return {
            'success': False,
            'message': '回测数据格式错误',
            'data': None
        }

    # 获取最新信号
    latest = df.iloc[-1]

    # 获取当前仓位（从performance最后一条记录）
    current_positions = performance[-1].get('position_units', 0) if performance else 0

    # 获取前一天的仓位
    previous_positions = performance[-2].get('position_units', 0) if len(performance) > 1 else 0

    # 根据持仓变化判断信号类型
    if current_positions > previous_positions:
        signal_type = 'BUY'
    elif current_positions < previous_positions:
        signal_type = 'SELL'
    else:
        signal_type = 'HOLD'

    # 买卖信号
    buy_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'positions': t.get('units', 0),
            'strength': 0
        }
        for t in trades if t['type'] == 'BUY'
    ]

    sell_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'reason': t.get('reason', 'SIGNAL'),
            'strength': 0,
            'positions_closed': t.get('units', 0)
        }
        for t in trades if t['type'] == 'SELL'
    ]

    latest_signal = {
        'date': str(latest['date']) if 'date' in latest else '',
        'close': safe_float(latest['close']),
        'ma20': safe_float(latest.get('ma20', 0)),
        'ma60': safe_float(latest.get('ma60', 0)),
        'ma_trend': latest.get('ma_trend', 'UNKNOWN'),
        'trend_type': latest.get('trend_type', 'UNKNOWN'),
        'rsi': safe_float(latest.get('rsi', 50)),
        'macd_dif': safe_float(latest.get('macd_dif', 0)),
        'macd_dea': safe_float(latest.get('macd_dea', 0)),
        'macd_hist': safe_float(latest.get('macd_hist', 0)),
        'macd_above_zero': bool(latest.get('macd_above_zero', False)),
        'kdj_k': safe_float(latest.get('kdj_k', 50)),
        'kdj_d': safe_float(latest.get('kdj_d', 50)),
        'kdj_j': safe_float(latest.get('kdj_j', 50)),
        'kdj_golden_cross': bool(latest.get('kdj_golden_cross', False)),
        'kdj_dead_cross': bool(latest.get('kdj_dead_cross', False)),
        'target_position': safe_int(latest.get('target_position', 0)),
        'exec_position': safe_int(latest.get('exec_position', 0)),
        'signal_strength': safe_float(current_positions / 10.0),
        'signal_type': signal_type,
        'positions_used': safe_int(current_positions),
        'previous_positions_used': safe_int(previous_positions),
        'signal_reason': latest.get('signal_reason', '')
    }

    # 生成操作建议
    next_action = _generate_next_action_rsi_macd_kdj_triple(
        current_positions,
        latest_signal
    )

    return {
        'success': True,
        'data': {
            'latest_date': latest_signal['date'],
            'position_value': safe_float(metrics.get('final_value', initial_capital)),
            'profit': safe_float(metrics.get('final_value', initial_capital)) - initial_capital,
            'profit_pct': safe_float(metrics.get('total_return_pct', 0)),
            'positions_used': safe_int(current_positions),
            'signal_strength': safe_float(latest_signal['signal_strength']),
            'next_action': next_action,
            'latest_data': latest_signal,
            'backtest_summary': {
                'trades': safe_int(metrics.get('total_trades', 0)),
                'buy_hold_return_pct': safe_float(metrics.get('buy_hold_return_pct', 0)),
                'max_drawdown': safe_float(metrics.get('max_drawdown_pct', 0)),
                'win_rate': safe_float(metrics.get('win_rate_pct', 0)),
                'sharpe_ratio': safe_float(metrics.get('sharpe_ratio', 0)),
                'initial_capital': safe_float(metrics.get('initial_capital', initial_capital)),
                'build_position_date': build_position_date
            },
            'summary': {
                'total_return_pct': safe_float(metrics.get('total_return_pct', 0)),
                'benchmark_return_pct': safe_float(metrics.get('buy_hold_return_pct', 0)),
                'sharpe_ratio': safe_float(metrics.get('sharpe_ratio', 0)),
                'max_drawdown_pct': safe_float(metrics.get('max_drawdown_pct', 0)),
                'win_rate': safe_float(metrics.get('win_rate_pct', 0)),
                'total_trades': safe_int(metrics.get('total_trades', 0))
            },
            'dates': dates,
            'prices': prices,
            'volumes': volumes,
            'strategy_values': strategy_values,
            'benchmark_values': benchmark_values,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'performance': performance  # 添加performance数据用于仓位历史图表
        },
        'strategy': 'rsi_macd_kdj_triple'
    }


def _generate_next_action_rsi_macd_kdj_triple(positions_used: int, latest_signal: Dict) -> str:
    """
    生成RSI+MACD+KDJ三指标共振策略的操作建议

    Args:
        positions_used: 当前使用的仓位数 (0-10)
        latest_signal: 最新信号数据

    Returns:
        操作建议字符串
    """
    target_position = latest_signal.get('target_position', 0)
    macd_trend = latest_signal.get('macd_trend', 'BEAR')
    rsi = latest_signal.get('rsi', 50)
    rsi_zone = latest_signal.get('rsi_zone', 'NORMAL')
    kdj_k = latest_signal.get('kdj_k', 50)
    signal_reason = latest_signal.get('signal_reason', '')

    # MACD空头趋势
    if macd_trend == 'BEAR':
        if positions_used > 0:
            return f"⛔ MACD空头趋势，建议清仓（当前{positions_used}成）"
        else:
            return f"⛔ MACD空头趋势，继续空仓观望"

    # MACD多头趋势
    if positions_used == 0:
        # 空仓状态
        if target_position >= 8:
            return f"🔥 {signal_reason}，建议建仓{target_position}成"
        elif target_position >= 5:
            return f"⚡ {signal_reason}，可建仓{target_position}成"
        else:
            return f"👀 观望为主，等待更好时机"

    elif positions_used <= 3:
        # 轻仓状态
        if target_position > positions_used + 2:
            return f"🔥 {signal_reason}，建议加仓至{target_position}成"
        elif target_position > positions_used:
            return f"✅ {signal_reason}，可小幅加仓"
        elif target_position == positions_used:
            return f"ℹ️ {signal_reason}，继续持有"
        else:
            return f"⚠️ {signal_reason}，建议减仓"

    elif positions_used <= 7:
        # 中等仓位
        if target_position >= 8:
            return f"🔥 {signal_reason}，建议加仓至{target_position}成"
        elif target_position > positions_used:
            return f"✅ {signal_reason}，可继续加仓"
        elif target_position == positions_used:
            return f"ℹ️ {signal_reason}，继续持有"
        else:
            return f"⚠️ {signal_reason}，建议减仓至{target_position}成"

    else:
        # 重仓状态
        if target_position >= 8:
            return f"🔥 {signal_reason}，继续持有"
        elif target_position >= 5:
            return f"✅ {signal_reason}，继续持有"
        else:
            return f"⚠️ {signal_reason}，建议减仓至{target_position}成"


def calculate_realtime_signal_pure_rsi(etf_code: str, start_date: str = '20250101', etf_settings: Dict = None) -> Dict:
    """计算纯RSI策略的实时信号

    Args:
        etf_code: ETF代码
        start_date: 回测开始日期
        etf_settings: ETF设置 {'initial_capital': int, 'total_positions': int, 'build_position_date': str}
    """
    if etf_settings is None:
        etf_settings = {}

    initial_capital = etf_settings.get('initial_capital', 2000)
    total_positions = etf_settings.get('total_positions', 10)
    build_position_date = etf_settings.get('build_position_date', None)

    # 加载数据
    data = get_etf_daily_data(etf_code, start_date)
    if not data or len(data) < 60:
        return {
            'success': False,
            'message': f'数据不足（至少需要60天，当前有{len(data) if data else 0}天）',
            'data': None
        }

    df = pd.DataFrame(data)

    # 辅助函数：安全转换值为JSON兼容类型
    def safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            f = float(value)
            return default if (np.isnan(f) or np.isinf(f)) else f
        except (ValueError, TypeError):
            return default

    def safe_int(value, default=0):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    # 生成信号
    from strategies.pure_rsi import PureRSISignalGenerator
    signal_gen = PureRSISignalGenerator()
    df = signal_gen.generate_signals(df)

    # 运行回测
    from strategies.pure_rsi_backtester import PureRSIBacktester
    backtester = PureRSIBacktester(
        initial_capital=initial_capital,
        total_positions=total_positions
    )

    backtest_result = backtester.run_backtest(etf_code, start_date)

    if not backtest_result['success']:
        return {
            'success': False,
            'message': f'回测失败: {backtest_result.get("message", "未知错误")}',
            'data': None
        }

    # 提取数据
    trades = backtest_result.get('trades', [])
    performance = backtest_result.get('performance', [])
    metrics = backtest_result.get('metrics', {})

    # 处理performance中的NaN值
    if isinstance(performance, list) and len(performance) > 0:
        # 将所有NaN值替换为0
        for p in performance:
            for key, value in p.items():
                if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                    p[key] = 0
                # 将numpy类型转换为Python原生类型
                if isinstance(value, (np.integer, np.floating)):
                    p[key] = float(value) if isinstance(value, np.floating) else int(value)

    if isinstance(performance, list) and len(performance) > 0:
        dates = [p['date'] for p in performance]
        prices = [safe_float(p['price']) for p in performance]
        strategy_values = [safe_float(p['portfolio_value']) - initial_capital for p in performance]
        initial_price = safe_float(performance[0]['price'])
        if initial_price > 0:
            benchmark_values = [safe_float((safe_float(p['price']) - initial_price) / initial_price * initial_capital) for p in performance]
        else:
            benchmark_values = [0.0] * len(performance)
        volumes = [safe_float(p.get('vol', 0)) for p in performance]
    else:
        return {
            'success': False,
            'message': '回测数据格式错误',
            'data': None
        }

    # 获取最新信号
    latest = df.iloc[-1]

    # 获取当前仓位（从performance最后一条记录）
    current_positions = performance[-1].get('position_units', 0) if performance else 0

    # 获取前一天的仓位
    previous_positions = performance[-2].get('position_units', 0) if len(performance) > 1 else 0

    # 根据持仓变化判断信号类型
    if current_positions > previous_positions:
        signal_type = 'BUY'
    elif current_positions < previous_positions:
        signal_type = 'SELL'
    else:
        signal_type = 'HOLD'

    # 买卖信号
    buy_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'positions': t.get('units', 0),
            'strength': 0
        }
        for t in trades if t['type'] == 'BUY'
    ]

    sell_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'reason': t.get('reason', 'SIGNAL'),
            'strength': 0,
            'positions_closed': t.get('units', 0)
        }
        for t in trades if t['type'] == 'SELL'
    ]

    latest_signal = {
        'date': str(latest['date']) if 'date' in latest else '',
        'close': safe_float(latest['close']),
        'rsi': safe_float(latest.get('rsi', 50)),
        'rsi_zone': str(latest.get('rsi_zone', '')) if pd.notna(latest.get('rsi_zone', '')) else '',
        'rsi_direction': str(latest.get('rsi_direction', '')) if pd.notna(latest.get('rsi_direction', '')) else '',
        'rsi_consecutive_up': safe_int(latest.get('rsi_consecutive_up', 0)),
        'rsi_slope': safe_float(latest.get('rsi_slope', 0)),
        'target_position': safe_int(latest.get('target_position', 0)),
        'exec_position': safe_int(latest.get('exec_position', 0)),
        'signal_strength': safe_float(current_positions / 10.0),
        'signal_type': signal_type,
        'positions_used': safe_int(current_positions),
        'previous_positions_used': safe_int(previous_positions),
        'position_reason': str(latest.get('position_reason', '')) if pd.notna(latest.get('position_reason', '')) else ''
    }

    # 生成操作建议
    next_action = _generate_next_action_pure_rsi(
        current_positions,
        latest_signal
    )

    return {
        'success': True,
        'data': {
            'latest_date': latest_signal['date'],
            'position_value': safe_float(metrics.get('final_value', initial_capital)),
            'profit': safe_float(metrics.get('final_value', initial_capital)) - initial_capital,
            'profit_pct': safe_float(metrics.get('total_return_pct', 0)),
            'positions_used': safe_int(current_positions),
            'signal_strength': safe_float(latest_signal['signal_strength']),
            'next_action': next_action,
            'latest_data': latest_signal,
            'backtest_summary': {
                'trades': safe_int(metrics.get('total_trades', 0)),
                'total_return_pct': safe_float(metrics.get('total_return_pct', 0)),
                'buy_hold_return_pct': safe_float(metrics.get('buy_hold_return_pct', 0)),
                'max_drawdown': safe_float(metrics.get('max_drawdown_pct', 0)),
                'win_rate': safe_float(metrics.get('win_rate_pct', 0)),
                'sharpe_ratio': safe_float(metrics.get('sharpe_ratio', 0)),
                'initial_capital': safe_float(metrics.get('initial_capital', initial_capital)),
                'build_position_date': build_position_date
            },
            'summary': {
                'total_return_pct': safe_float(metrics.get('total_return_pct', 0)),
                'benchmark_return_pct': safe_float(metrics.get('buy_hold_return_pct', 0)),
                'sharpe_ratio': safe_float(metrics.get('sharpe_ratio', 0)),
                'max_drawdown_pct': safe_float(metrics.get('max_drawdown_pct', 0)),
                'win_rate': safe_float(metrics.get('win_rate_pct', 0)),
                'total_trades': safe_int(metrics.get('total_trades', 0))
            },
            'dates': dates,
            'prices': prices,
            'volumes': volumes,
            'strategy_values': strategy_values,
            'benchmark_values': benchmark_values,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'performance': performance
        },
        'strategy': 'pure_rsi'
    }


def _generate_next_action_pure_rsi(positions_used: int, latest_signal: Dict) -> str:
    """
    生成纯RSI策略的操作建议

    Args:
        positions_used: 当前使用的仓位数 (0-10)
        latest_signal: 最新信号数据

    Returns:
        操作建议字符串
    """
    target_position = latest_signal.get('target_position', 0)
    rsi = latest_signal.get('rsi', 50)
    rsi_zone = latest_signal.get('rsi_zone', '')
    rsi_direction = latest_signal.get('rsi_direction', '')
    signal_reason = latest_signal.get('position_reason', '')

    if positions_used == 0:
        # 空仓状态
        if target_position >= 5:
            return f"🔥 {signal_reason}，建议建仓{target_position}成"
        elif target_position >= 3:
            return f"⚡ {signal_reason}，可建仓{target_position}成"
        elif target_position >= 1:
            return f"👀 {signal_reason}，可小仓位试错"
        else:
            return f"⛔ RSI={rsi:.1f}({rsi_zone})，空仓观望"

    elif positions_used <= 3:
        # 轻仓状态
        if target_position > positions_used + 2:
            return f"🔥 {signal_reason}，建议加仓至{target_position}成"
        elif target_position > positions_used:
            return f"✅ {signal_reason}，可小幅加仓"
        elif target_position == positions_used:
            return f"ℹ️ {signal_reason}，继续持有"
        else:
            return f"⚠️ {signal_reason}，建议减仓"

    elif positions_used <= 7:
        # 中等仓位
        if target_position >= 8:
            return f"🔥 {signal_reason}，建议加仓至{target_position}成"
        elif target_position > positions_used:
            return f"✅ {signal_reason}，可继续加仓"
        elif target_position == positions_used:
            return f"ℹ️ {signal_reason}，继续持有"
        else:
            return f"⚠️ {signal_reason}，建议减仓至{target_position}成"

    else:
        # 重仓状态
        if target_position >= 8:
            return f"🔥 {signal_reason}，继续持有"
        elif target_position >= 5:
            return f"✅ {signal_reason}，继续持有"
        else:
            return f"⚠️ {signal_reason}，建议减仓至{target_position}成"


def calculate_realtime_signal_rsi_triple_lines(etf_code: str, start_date: str = '20250101', etf_settings: Dict = None) -> Dict:
    """计算RSI三线金叉死叉策略的实时信号

    Args:
        etf_code: ETF代码
        start_date: 回测开始日期
        etf_settings: ETF设置 {'initial_capital': int, 'total_positions': int, 'build_position_date': str}
    """
    if etf_settings is None:
        etf_settings = {}

    initial_capital = etf_settings.get('initial_capital', 2000)
    total_positions = etf_settings.get('total_positions', 10)
    build_position_date = etf_settings.get('build_position_date', None)
    optimized_params = etf_settings.get('optimized_params', None)

    # 加载数据
    data = get_etf_daily_data(etf_code, start_date)
    if not data or len(data) < 60:
        return {
            'success': False,
            'message': f'数据不足（至少需要60天，当前有{len(data) if data else 0}天）',
            'data': None
        }

    df = pd.DataFrame(data)

    # 辅助函数：安全转换值为JSON兼容类型
    def safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            f = float(value)
            return default if (np.isnan(f) or np.isinf(f)) else f
        except (ValueError, TypeError):
            return default

    def safe_int(value, default=0):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return default

    # 生成信号（使用优化参数）
    from strategies.rsi_triple_lines import RSITripleLinesSignalGenerator
    signal_gen = RSITripleLinesSignalGenerator(optimized_params)
    df = signal_gen.generate_signals(df)

    # 运行回测
    from strategies.rsi_triple_lines_backtester import RSITripleLinesBacktester
    backtester = RSITripleLinesBacktester(
        initial_capital=initial_capital,
        total_positions=total_positions
    )

    backtest_result = backtester.run_backtest(etf_code, start_date)

    if not backtest_result['success']:
        return {
            'success': False,
            'message': f'回测失败: {backtest_result.get("message", "未知错误")}',
            'data': None
        }

    # 提取数据
    trades = backtest_result.get('trades', [])
    performance = backtest_result.get('performance', [])
    metrics = backtest_result.get('metrics', {})

    # 处理performance中的NaN值
    if isinstance(performance, list) and len(performance) > 0:
        for p in performance:
            for key, value in p.items():
                if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                    p[key] = 0
                if isinstance(value, (np.integer, np.floating)):
                    p[key] = float(value) if isinstance(value, np.floating) else int(value)

    if isinstance(performance, list) and len(performance) > 0:
        dates = [p['date'] for p in performance]
        prices = [safe_float(p['price']) for p in performance]
        strategy_values = [safe_float(p['portfolio_value']) - initial_capital for p in performance]
        initial_price = safe_float(performance[0]['price'])
        if initial_price > 0:
            benchmark_values = [safe_float((safe_float(p['price']) - initial_price) / initial_price * initial_capital) for p in performance]
        else:
            benchmark_values = [0.0] * len(performance)
        volumes = [safe_float(p.get('vol', 0)) for p in performance]
    else:
        return {
            'success': False,
            'message': '回测数据格式错误',
            'data': None
        }

    # 获取最新信号
    latest = df.iloc[-1]

    # 获取当前仓位
    current_positions = performance[-1].get('position_units', 0) if performance else 0
    previous_positions = performance[-2].get('position_units', 0) if len(performance) > 1 else 0

    # 根据持仓变化判断信号类型
    if current_positions > previous_positions:
        signal_type = 'BUY'
    elif current_positions < previous_positions:
        signal_type = 'SELL'
    else:
        signal_type = 'HOLD'

    # 买卖信号
    buy_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'positions': t.get('units', 0),
            'strength': 0
        }
        for t in trades if t['type'] == 'BUY'
    ]

    sell_signals = [
        {
            'date': t['date'],
            'price': t['price'],
            'reason': t.get('reason', 'SIGNAL'),
            'strength': 0,
            'positions_closed': t.get('units', 0)
        }
        for t in trades if t['type'] == 'SELL'
    ]

    latest_signal = {
        'date': str(latest['date']) if 'date' in latest else '',
        'close': safe_float(latest['close']),
        'rsi1': safe_float(latest.get('rsi1', 50)),
        'rsi2': safe_float(latest.get('rsi2', 50)),
        'rsi3': safe_float(latest.get('rsi3', 50)),
        'triple_alignment': str(latest.get('triple_alignment', '')) if pd.notna(latest.get('triple_alignment', '')) else '',
        'rsi1_direction': str(latest.get('rsi1_direction', '')) if pd.notna(latest.get('rsi1_direction', '')) else '',
        'rsi1_consecutive_up': safe_int(latest.get('rsi1_consecutive_up', 0)),
        'rsi1_cross_above_rsi2': bool(latest.get('rsi1_cross_above_rsi2', False)),
        'rsi1_cross_above_rsi3': bool(latest.get('rsi1_cross_above_rsi3', False)),
        'target_position': safe_int(latest.get('target_position', 0)),
        'exec_position': safe_int(latest.get('exec_position', 0)),
        'signal_strength': safe_float(current_positions / 10.0),
        'signal_type': signal_type,
        'positions_used': safe_int(current_positions),
        'previous_positions_used': safe_int(previous_positions),
        'position_reason': str(latest.get('position_reason', '')) if pd.notna(latest.get('position_reason', '')) else ''
    }

    # 生成操作建议
    next_action = _generate_next_action_rsi_triple_lines(
        current_positions,
        latest_signal
    )

    return {
        'success': True,
        'data': {
            'latest_date': latest_signal['date'],
            'position_value': safe_float(metrics.get('final_value', initial_capital)),
            'profit': safe_float(metrics.get('final_value', initial_capital)) - initial_capital,
            'profit_pct': safe_float(metrics.get('total_return_pct', 0)),
            'positions_used': safe_int(current_positions),
            'signal_strength': safe_float(latest_signal['signal_strength']),
            'next_action': next_action,
            'latest_data': latest_signal,
            'backtest_summary': {
                'trades': safe_int(metrics.get('total_trades', 0)),
                'total_return_pct': safe_float(metrics.get('total_return_pct', 0)),
                'buy_hold_return_pct': safe_float(metrics.get('buy_hold_return_pct', 0)),
                'max_drawdown': safe_float(metrics.get('max_drawdown_pct', 0)),
                'win_rate': safe_float(metrics.get('win_rate_pct', 0)),
                'sharpe_ratio': safe_float(metrics.get('sharpe_ratio', 0)),
                'initial_capital': safe_float(metrics.get('initial_capital', initial_capital)),
                'build_position_date': build_position_date
            },
            'summary': {
                'total_return_pct': safe_float(metrics.get('total_return_pct', 0)),
                'benchmark_return_pct': safe_float(metrics.get('buy_hold_return_pct', 0)),
                'sharpe_ratio': safe_float(metrics.get('sharpe_ratio', 0)),
                'max_drawdown_pct': safe_float(metrics.get('max_drawdown_pct', 0)),
                'win_rate': safe_float(metrics.get('win_rate_pct', 0)),
                'total_trades': safe_int(metrics.get('total_trades', 0))
            },
            'dates': dates,
            'prices': prices,
            'volumes': volumes,
            'strategy_values': strategy_values,
            'benchmark_values': benchmark_values,
            'buy_signals': buy_signals,
            'sell_signals': sell_signals,
            'performance': performance
        },
        'strategy': 'rsi_triple_lines'
    }


def _generate_next_action_rsi_triple_lines(positions_used: int, latest_signal: Dict) -> str:
    """生成RSI三线策略的操作建议"""
    target_position = latest_signal.get('target_position', 0)
    rsi1 = latest_signal.get('rsi1', 50)
    rsi2 = latest_signal.get('rsi2', 50)
    rsi3 = latest_signal.get('rsi3', 50)
    triple_alignment = latest_signal.get('triple_alignment', '')
    rsi1_direction = latest_signal.get('rsi1_direction', '')
    signal_reason = latest_signal.get('position_reason', '')

    # 空头排列
    if triple_alignment == 'BEARISH':
        if positions_used > 0:
            return f"⛔ 三线空头排列，建议清仓（当前{positions_used}成）"
        else:
            return f"⛔ 三线空头排列，继续空仓观望"

    # 多头排列
    if triple_alignment == 'BULLISH':
        if positions_used == 0:
            if target_position >= 5:
                return f"🔥 {signal_reason}，建议建仓{target_position}成"
            elif target_position >= 3:
                return f"⚡ {signal_reason}，可建仓{target_position}成"
            else:
                return f"👀 多头排列初期，等待更好时机"
        elif positions_used <= 4:
            if target_position > positions_used + 2:
                return f"🔥 {signal_reason}，建议加仓至{target_position}成"
            elif target_position > positions_used:
                return f"✅ {signal_reason}，可小幅加仓"
            elif target_position == positions_used:
                return f"ℹ️ {signal_reason}，继续持有"
            else:
                return f"⚠️ {signal_reason}，建议减仓"
        else:
            if target_position >= 8:
                return f"🔥 多头排列强势，继续持有"
            elif target_position >= 5:
                return f"✅ {signal_reason}，继续持有"
            else:
                return f"⚠️ {signal_reason}，建议减仓至{target_position}成"

    # 默认处理
    if positions_used == 0:
        if target_position >= 1:
            return f"👀 {signal_reason}，可小仓位试错"
        else:
            return f"⛔ RSI1={rsi1:.1f}，等待金叉信号"
    else:
        return f"ℹ️ {signal_reason}，当前持仓{positions_used}成"


def run_backtest(etf_code: str, start_date: str = '20250101', strategy: str = None) -> Dict:
    """运行回测

    Args:
        etf_code: ETF代码
        start_date: 开始日期
        strategy: 策略类型（如果不指定，从watchlist读取）

    Returns:
        回测结果
    """
    # 从watchlist读取ETF设置（包括优化参数）
    watchlist = load_watchlist()
    optimized_macd_params = None
    initial_capital = 2000
    num_positions = 10
    build_date = None

    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            if strategy is None:
                strategy = etf.get('strategy', 'macd_aggressive')
            # 读取优化参数
            optimized_macd_params = etf.get('optimized_macd_params', None)
            # 读取其他设置
            initial_capital = etf.get('initial_capital', 2000)
            num_positions = etf.get('total_positions', 10)
            build_date = etf.get('build_position_date', None)
            break
    else:
        if strategy is None:
            strategy = 'macd_aggressive'

    # 根据策略类型调用不同的回测函数
    if strategy == 'macd_aggressive':
        # MACD激进策略
        return run_macd_backtest(etf_code, start_date, strategy=strategy,
                                  initial_capital=initial_capital,
                                  num_positions=num_positions,
                                  build_date=build_date,
                                  optimized_macd_params=optimized_macd_params)
    elif strategy == 'macd_kdj_discrete':
        # MACD+KDJ离散仓位系统
        return calculate_realtime_signal_macd_kdj_discrete(etf_code, start_date, {
            'initial_capital': initial_capital,
            'total_positions': num_positions,
            'build_position_date': build_date
        })
    elif strategy == 'rsi_macd_kdj_triple':
        # RSI+MACD+KDJ三指标共振策略
        return calculate_realtime_signal_rsi_macd_kdj_triple(etf_code, start_date, {
            'initial_capital': initial_capital,
            'total_positions': num_positions,
            'build_position_date': build_date
        })
    elif strategy == 'pure_rsi':
        # 纯RSI 0-10仓策略
        return calculate_realtime_signal_pure_rsi(etf_code, start_date, {
            'initial_capital': initial_capital,
            'total_positions': num_positions,
            'build_position_date': build_date
        })
    elif strategy == 'rsi_triple_lines':
        # RSI三线金叉死叉策略
        return calculate_realtime_signal_rsi_triple_lines(etf_code, start_date, {
            'initial_capital': initial_capital,
            'total_positions': num_positions,
            'build_position_date': build_date
        })
    else:
        return {
            'success': False,
            'message': f'不支持的策略类型: {strategy}',
            'data': None
        }


def load_batch_signals_optimized(use_realtime: bool = False) -> list:
    """批量加载信号（优化版）

    Args:
        use_realtime: 是否使用实时优化模式（只计算当天）

    Returns:
        list: 信号数据列表
    """
    watchlist = load_watchlist()
    etf_list = watchlist.get('etfs', [])

    results = []

    for etf in etf_list:
        etf_code = etf['code']
        strategy_type = etf.get('strategy', 'macd_aggressive')
        strategy_params = etf.get('optimized_macd_params', {})

        if use_realtime:
            # 实时模式：只计算当天信号（快速）
            from strategies.signals import get_latest_signal_optimized
            signal_data = get_latest_signal_optimized(etf_code, strategy_type, strategy_params)

            # 转换为统一格式
            etf_info = get_etf_info(etf_code)
            if etf_info:
                results.append({
                    'code': etf_code,
                    'name': etf_info.get('extname', etf_code),
                    'strategy': strategy_type,
                    'signal': signal_data['signal'].upper(),
                    'action': signal_data['action'],
                    'macd_dif': signal_data.get('macd_dif', 0),
                    'macd_dea': signal_data.get('macd_dea', 0),
                    'macd_hist': signal_data.get('macd_hist', 0),
                    'kdj_k': signal_data.get('kdj_k', 0),
                    'kdj_d': signal_data.get('kdj_d', 0),
                    'kdj_j': signal_data.get('kdj_j', 0),
                    'close': signal_data.get('close', 0),
                    'trade_date': signal_data.get('trade_date', '')
                })
        else:
            # 普通模式：完整回测（用于详情页）
            signal_result = calculate_realtime_signal(etf_code, '20240101', strategy_type)
            if signal_result['success']:
                results.append(signal_result)

    return results


