"""
ETF预测系统API
专注于策略回测和信号生成
"""
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from starlette.middleware.sessions import SessionMiddleware
from typing import Optional, List
import sys
import os
import logging
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core.database import get_etf_info
from core.auth import router as auth_router, require_auth

app = FastAPI(title=config.API_TITLE, version=config.API_VERSION)

# 导入必要的模块
from starlette.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

# 定义认证中间件类
class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件

    处理所有路由的认证检查：
    - 静态文件: 无需认证
    - 登录路由: 无需认证
    - 页面路由: 需要认证，未认证则重定向
    - API路由: 需要认证，未认证则401
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1. 静态文件 - 不需要认证
        if path.startswith("/static/"):
            return await call_next(request)

        # 2. 登录相关路由 - 不需要认证
        if path in ["/login", "/logout"] or path.startswith("/login") or path.startswith("/logout"):
            return await call_next(request)

        # 3. 检查session是否可用
        if "session" not in request.scope:
            # Session未配置，允许继续（可能有其他中间件处理）
            return await call_next(request)

        # 4. 页面路由 - 需要认证，未认证则重定向
        page_routes = ["/", "/macd-watchlist", "/profit", "/settings"]
        if path in page_routes or path.endswith("/"):
            if not request.session.get("authenticated"):
                # 保存原始URL用于登录后跳转
                request.session["redirect_after_login"] = path
                # 使用 RedirectResponse
                from starlette.responses import RedirectResponse
                return RedirectResponse(url="/login", status_code=302)
            return await call_next(request)

        # 5. API路由 - 需要认证，未认证则返回401
        if path.startswith("/api/"):
            if not request.session.get("authenticated"):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "未认证",
                        "message": "请先登录系统",
                        "code": "UNAUTHORIZED"
                    }
                )
            return await call_next(request)

        # 6. 其他路由 - 正常处理
        return await call_next(request)

# 添加中间件（注意顺序：后添加的先执行）
# 1. 先添加认证中间件（会后执行）
app.add_middleware(AuthMiddleware)

# 2. 最后添加SessionMiddleware（会先执行，确保session可用）
app.add_middleware(
    SessionMiddleware,
    secret_key=config.SESSION_SECRET_KEY,
    max_age=None,  # 浏览器关闭时过期
    same_site="lax",  # CSRF保护
    https_only=False  # 生产环境建议设置为True
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 将templates保存到config中供auth模块使用
config.templates = templates

# 注册认证路由
app.include_router(auth_router, tags=["认证"])


def get_signal_name(signal_type: str) -> str:
    """将信号类型转换为中文名称"""
    signal_map = {
        'BUY': '买入',
        'SELL': '卖出',
        'HOLD': '持有'
    }
    return signal_map.get(signal_type, '持有')


def get_kdj_status(k_value: float, j_value: float) -> str:
    """将 KDJ 值转换为状态描述"""
    if k_value > 85 or j_value > 110:
        return '严重超买'
    elif k_value > 80 or j_value > 100:
        return '超买'
    elif k_value < 20:
        return '超卖'
    else:
        return '正常'


def _get_macd_params_display(etf: dict) -> dict:
    """获取ETF的MACD参数显示信息

    Args:
        etf: ETF信息字典

    Returns:
        {
            'fast': int,
            'slow': int,
            'signal': int,
            'is_optimized': bool
        }
    """
    optimized_params = etf.get('optimized_macd_params', None)

    if optimized_params:
        return {
            'fast': optimized_params.get('macd_fast', 8),
            'slow': optimized_params.get('macd_slow', 17),
            'signal': optimized_params.get('macd_signal', 5),
            'is_optimized': True
        }
    else:
        # 默认参数
        return {
            'fast': 8,
            'slow': 17,
            'signal': 5,
            'is_optimized': False
        }


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Home page - 批量展示策略、持仓、下个交易日操作"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/macd-watchlist", response_class=HTMLResponse)
async def macd_watchlist_page(request: Request):
    """MACD Strategy watchlist page with split-view layout."""
    return templates.TemplateResponse("macd_watchlist.html", {"request": request})


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """System settings page."""
    return templates.TemplateResponse("settings.html", {"request": request})


@app.get("/profit", response_class=HTMLResponse)
async def profit_page(request: Request):
    """Profit summary page - 所有ETF汇总收益"""
    auth_check = await require_auth(request)
    if auth_check:
        return auth_check
    return templates.TemplateResponse("profit.html", {"request": request})


# ==================== 批量数据端点 ====================

@app.get("/api/watchlist/batch-signals")
async def get_batch_signals(refresh: bool = False, realtime: bool = False):
    """批量获取所有自选ETF的策略、持仓、下个交易日操作

    Args:
        refresh: 是否强制刷新缓存
        realtime: 是否使用实时模式（只计算当天，不回测历史）
    """
    from core.watchlist import load_watchlist, calculate_realtime_signal
    from core.database import get_batch_cache, set_batch_cache, get_latest_data_date, clear_batch_cache
    from datetime import datetime, timedelta

    # 如果是实时模式，强制清除缓存
    if realtime:
        clear_batch_cache()

    # 获取最新数据日期
    data_date = get_latest_data_date()
    if not data_date:
        return {
            'success': False,
            'message': '无法获取数据日期'
        }

    # 计算一年前的日期（YYYYMMDD格式）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    start_date_str = start_date.strftime('%Y%m%d')

    # 如果不强制刷新且不是实时模式，尝试从缓存获取
    if not refresh and not realtime:
        cached = get_batch_cache('signals', data_date)
        if cached:
            return {
                'success': True,
                'data': cached.get('data', []),
                'count': cached.get('count', 0),
                'cached': True,
                'data_date': data_date
            }

    # 缓存不存在或需要刷新，重新计算
    watchlist = load_watchlist()
    results = []

    for etf in watchlist.get('etfs', []):
        etf_code = etf['code']
        strategy = etf.get('strategy', 'macd_aggressive')

        # 获取ETF信息
        etf_info = get_etf_info(etf_code)
        if not etf_info:
            continue

        # 获取实时信号（使用近一年数据）
        signal_result = calculate_realtime_signal(etf_code, start_date_str, strategy)
        if not signal_result['success']:
            continue

        signal_data = signal_result['data']

        # 提取关键信息
        latest_data = signal_data.get('latest_data', {})
        backtest_summary = signal_data.get('backtest_summary', {})

        # 计算当日涨幅
        daily_change_pct = 0.0
        try:
            from core.database import get_etf_daily_data
            # 获取最近两天的数据（通过设置最近的时间范围）
            recent_data = get_etf_daily_data(etf_code)
            if recent_data and len(recent_data) >= 2:
                # 数据按日期升序排列，最后两条是最新的
                today_close = float(recent_data[-1].get('close', 0))
                yesterday_close = float(recent_data[-2].get('close', 0))
                if yesterday_close > 0:
                    daily_change_pct = ((today_close - yesterday_close) / yesterday_close) * 100
        except Exception as e:
            daily_change_pct = 0.0

        # 计算今日收益（基于昨天持仓）
        # 今日收益 = 昨天持仓数 × 200 × (今日涨幅/100)
        # 注意：今天的买卖是按收盘价执行的，不计入今日收益
        yesterday_positions = latest_data.get('previous_positions_used', 0)
        daily_profit = yesterday_positions * 200 * (daily_change_pct / 100)

        # 提取 KDJ 数据
        kdj_k = latest_data.get('kdj_k', 0)
        kdj_d = latest_data.get('kdj_d', 0)
        kdj_j = latest_data.get('kdj_j', 0)
        kdj_data = {
            'k': kdj_k,
            'd': kdj_d,
            'j': kdj_j,
            'status': get_kdj_status(kdj_k, kdj_j),
            'fusion_level': latest_data.get('fusion_level', 0),
            'position_cap': latest_data.get('kdj_position_cap', 10)
        }

        # 计算今日操作
        current_positions = signal_data.get('positions_used', 0)
        previous_positions = latest_data.get('previous_positions_used', 0)
        today_action = current_positions - previous_positions

        # 确定操作原因
        action_reason = ''
        if today_action > 0:
            # 买入
            if latest_data.get('signal_type') == 'BUY':
                strength = latest_data.get('signal_strength', 0)
                if strength >= 10:
                    action_reason = '回踩MA60未破+MACD金叉，最强买入信号'
                elif strength >= 9:
                    action_reason = '正鸭嘴形态，强烈看多'
                elif strength >= 8:
                    action_reason = '零轴上方金叉，上升趋势明确'
                else:
                    action_reason = 'MACD金叉买入'
            else:
                action_reason = '加仓买入'
        elif today_action < 0:
            # 卖出
            macd_dif = latest_data.get('macd_dif', 0)
            macd_dea = latest_data.get('macd_dea', 0)
            kdj_k = latest_data.get('kdj_k', 0)
            kdj_status = '严重超买' if kdj_k > 80 else ('超买' if kdj_k > 70 else '正常')

            if kdj_status == '严重超买':
                action_reason = f'KDJ{kdj_status}，止盈减仓'
            elif macd_dif < macd_dea:
                action_reason = 'MACD死叉，减仓避险'
            elif current_positions > 7:
                action_reason = '涨幅较大，分批止盈'
            else:
                action_reason = '信号转弱，减仓保住利润'
        else:
            # 持有
            action_reason = '保持现有仓位'

        if today_action > 0:
            today_operation = f'买入{today_action}仓'
        elif today_action < 0:
            today_operation = f'卖出{abs(today_action)}仓'
        else:
            today_operation = '持有'

        results.append({
            'code': etf_code,
            'name': etf_info.get('extname', etf_code),
            'strategy': strategy,
            'strategy_name': etf.get('strategy_name', strategy),
            'signal': latest_data.get('signal_type', 'HOLD'),
            'signal_name': get_signal_name(latest_data.get('signal_type', 'HOLD')),
            'signal_strength': latest_data.get('signal_strength', 0),  # 添加信号强度
            'today_operation': today_operation,  # 今日操作
            'today_action_count': today_action,  # 今日操作数量（正数买入，负数卖出）
            'action_reason': action_reason,  # 操作原因
            'profit_value': signal_data.get('profit', 0),
            'profit_pct': signal_data.get('profit_pct', 0),
            'benchmark_return': backtest_summary.get('buy_hold_return_pct', 0) or 0,
            'positions_used': signal_data.get('positions_used', 0),
            'total_positions': etf.get('total_positions', 10),  # 从配置读取
            'next_action': signal_data.get('next_action', '--'),
            'macd': {
                'dif': latest_data.get('macd_dif', 0),
                'dea': latest_data.get('macd_dea', 0),
                'hist': latest_data.get('macd_hist', 0)
            },
            'macd_params': _get_macd_params_display(etf),
            'kdj': kdj_data,
            'price': latest_data.get('close', 0),
            'daily_change_pct': daily_change_pct,  # 当日涨幅
            'daily_profit': daily_profit,  # 今日收益
            'latest_data': latest_data,  # 添加完整的 latest_data（包含 previous_positions_used）
            'position_value': etf.get('position_value', 0),
            'data_date': signal_data.get('latest_date', data_date),  # 该ETF的数据更新日期
            'remark': etf.get('remark', '')  # 用户自定义备注
        })

    # 保存到缓存（仅在非实时模式下）
    if not realtime:
        cache_data = {
            'data': results,
            'count': len(results)
        }
        set_batch_cache('signals', data_date, cache_data)

    return {
        'success': True,
        'data': results,
        'count': len(results),
        'cached': False,
        'data_date': data_date
    }


@app.get("/api/watchlist/batch-backtest")
async def get_batch_backtest(refresh: bool = False):
    """批量获取所有自选ETF的回测结果

    Args:
        refresh: 是否强制刷新缓存
    """
    from core.watchlist import load_watchlist, run_backtest
    from core.database import get_batch_cache, set_batch_cache, get_latest_data_date

    # 获取最新数据日期
    data_date = get_latest_data_date()
    if not data_date:
        return {
            'success': False,
            'message': '无法获取数据日期'
        }

    # 如果不强制刷新，尝试从缓存获取
    if not refresh:
        cached = get_batch_cache('backtest', data_date)
        if cached:
            return {
                'success': True,
                'data': cached.get('data', []),
                'count': cached.get('count', 0),
                'cached': True,
                'data_date': data_date
            }

    # 缓存不存在或需要刷新，重新计算
    watchlist = load_watchlist()
    results = []

    for etf in watchlist.get('etfs', []):
        etf_code = etf['code']
        strategy = etf.get('strategy', 'macd_aggressive')

        # 获取回测结果
        backtest_result = run_backtest(etf_code, '20240101', strategy)
        if not backtest_result['success']:
            continue

        backtest_data = backtest_result['data']
        summary = backtest_data.get('summary', {})

        results.append({
            'code': etf_code,
            'name': etf.get('name', etf_code),
            'strategy': strategy,
            'total_return': summary.get('total_return_pct', 0),
            'benchmark_return': summary.get('benchmark_return_pct', 0),
            'sharpe_ratio': summary.get('sharpe_ratio', 0),
            'max_drawdown': summary.get('max_drawdown_pct', 0),
            'win_rate': summary.get('win_rate', 0),
            'trade_count': summary.get('total_trades', 0)
        })

    # 保存到缓存
    cache_data = {
        'data': results,
        'count': len(results)
    }
    set_batch_cache('backtest', data_date, cache_data)

    return {
        'success': True,
        'data': results,
        'count': len(results),
        'cached': False,
        'data_date': data_date
    }


@app.post("/api/watchlist/refresh-cache")
async def refresh_cache():
    """刷新批量数据缓存

    清除现有缓存并重新计算所有数据
    """
    from core.database import clear_batch_cache

    # 清除缓存
    clear_batch_cache()

    # 重新计算并缓存
    signals_result = await get_batch_signals(refresh=True)
    backtest_result = await get_batch_backtest(refresh=True)

    return {
        'success': True,
        'message': '缓存刷新成功',
        'signals_count': signals_result.get('count', 0),
        'backtest_count': backtest_result.get('count', 0),
        'data_date': signals_result.get('data_date')
    }


@app.post("/api/watchlist/remark")
async def update_etf_remark(request: Request):
    """更新ETF备注

    Body: {
        "etf_code": "510330.SH",
        "remark": "自定义备注内容"
    }
    """
    from core.watchlist import update_etf_remark

    data = await request.json()
    etf_code = data.get('etf_code')
    remark = data.get('remark', '')

    if not etf_code:
        raise HTTPException(status_code=400, detail="etf_code is required")

    result = update_etf_remark(etf_code, remark)
    return result


# ==================== MACD Strategy Endpoints ====================

@app.get("/api/macd/strategies")
async def list_macd_strategies():
    """List available MACD strategy configurations."""
    from strategies.strategies import get_strategy_params

    strategies = [
        {"name": "default", "params": get_strategy_params('default')},
        {"name": "aggressive", "params": get_strategy_params('aggressive')},
        {"name": "optimized_t_trading", "params": get_strategy_params('optimized_t_trading')},
        {"name": "conservative", "params": get_strategy_params('conservative')},
        {"name": "trend_following", "params": get_strategy_params('trend_following')},
        {"name": "reversal", "params": get_strategy_params('reversal')}
    ]

    return {"strategies": strategies}


@app.post("/api/macd/backtest")
async def run_macd_backtest(request: Request):
    """Run MACD strategy backtest."""
    from strategies.backtester import MACDBacktester
    from strategies.strategies import get_strategy_params

    data = await request.json()
    etf_code = data.get('etf_code')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    strategy_name = data.get('strategy', 'default')
    custom_params = data.get('params', {})

    if not etf_code:
        raise HTTPException(status_code=400, detail="etf_code is required")

    # Get strategy params and merge with any custom params
    params = get_strategy_params(strategy_name)
    params.update(custom_params)

    # Run backtest
    try:
        backtester = MACDBacktester()
        result = backtester.run_backtest(etf_code, params, start_date, end_date)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/macd/optimize-params/{etf_code}")
async def optimize_macd_parameters(etf_code: str, request: Request):
    """
    优化MACD参数

    使用两阶段网格搜索优化MACD参数（macd_fast, macd_slow, macd_signal）
    以最大化近一年收益率为目标

    Args:
        etf_code: ETF代码 (如 '510330.SH')

    Request Body:
        lookback_days: 优化回溯天数（默认365天）
        method: 优化方法（目前仅支持 'grid_search'）

    Returns:
        优化结果，包含最优参数和性能指标
    """
    from strategies.macd_param_optimizer import MACDParamOptimizer

    data = await request.json()
    lookback_days = data.get('lookback_days', 365)
    method = data.get('method', 'grid_search')

    if method != 'grid_search':
        raise HTTPException(
            status_code=400,
            detail=f"不支持的优化方法: {method}，目前仅支持 'grid_search'"
        )

    try:
        # 创建优化器并执行优化
        optimizer = MACDParamOptimizer(etf_code, lookback_days)
        result = optimizer.optimize()

        return {
            'success': True,
            'etf_code': etf_code,
            'optimization_result': result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"优化失败: {str(e)}")


@app.post("/api/macd-kdj-discrete/optimize-params/{etf_code}")
async def optimize_macd_kdj_discrete_parameters(etf_code: str, request: Request):
    """
    优化MACD+KDJ离散仓位系统参数

    使用两阶段网格搜索优化MACD和KDJ参数
    以最大化近一年收益率为目标

    Args:
        etf_code: ETF代码 (如 '510330.SH')

    Request Body:
        lookback_days: 优化回溯天数（默认365天）
        optimize_kdj: 是否优化KDJ参数（默认true）

    Returns:
        优化结果，包含最优参数和性能指标
    """
    from strategies.macd_kdj_discrete_param_optimizer import MACDKDJDiscreteParamOptimizer

    data = await request.json()
    lookback_days = data.get('lookback_days', 365)
    optimize_kdj = data.get('optimize_kdj', True)

    try:
        # 创建优化器并执行优化
        optimizer = MACDKDJDiscreteParamOptimizer(etf_code, lookback_days)
        result = optimizer.optimize(optimize_kdj)

        return {
            'success': True,
            'etf_code': etf_code,
            'optimization_result': result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"优化失败: {str(e)}")


@app.post("/api/rsi-triple-lines/optimize-params/{etf_code}")
async def optimize_rsi_triple_lines_parameters(etf_code: str, request: Request):
    """
    优化RSI三线金叉死叉策略参数

    使用网格搜索优化RSI三线参数
    以最大化近一年夏普比率为目标

    Args:
        etf_code: ETF代码 (如 '510330.SH')

    Returns:
        优化结果，包含最优参数和性能指标
    """
    from optimization.optimize_rsi_triple_lines import RSITripleLinesOptimizer, save_optimized_params

    try:
        # 创建优化器并执行优化
        optimizer = RSITripleLinesOptimizer(etf_code)
        result = optimizer.optimize(n_workers=4)

        if not result['success']:
            raise HTTPException(status_code=400, detail=result.get('message', '优化失败'))

        # 保存优化参数到watchlist
        from core.watchlist import load_watchlist, save_watchlist
        watchlist = load_watchlist()

        for etf in watchlist['etfs']:
            if etf['code'] == etf_code:
                etf['optimized_params'] = {
                    'rsi1_period': result['best_params']['rsi1_period'],
                    'rsi2_period': result['best_params']['rsi2_period'],
                    'rsi3_period': result['best_params']['rsi3_period'],
                }
                break

        save_watchlist(watchlist)

        return {
            'success': True,
            'etf_code': etf_code,
            'optimization_result': result
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"优化失败: {str(e)}")


# ==================== Watchlist Endpoints ====================

@app.get("/api/watchlist")
async def get_watchlist():
    """获取自选ETF列表"""
    from core.watchlist import load_watchlist

    watchlist = load_watchlist()
    return watchlist


@app.post("/api/watchlist/add")
async def add_etf_to_watchlist(request: Request):
    """添加ETF到自选"""
    from core.watchlist import add_to_watchlist

    data = await request.json()
    etf_code = data.get('etf_code')
    strategy = data.get('strategy', 'macd_aggressive')  # 默认MACD激进策略

    if not etf_code:
        raise HTTPException(status_code=400, detail="etf_code is required")

    result = add_to_watchlist(etf_code, strategy)
    return result


@app.put("/api/watchlist/{etf_code}/strategy")
async def update_etf_strategy(etf_code: str, request: Request):
    """更新ETF的策略"""
    from core.watchlist import update_etf_strategy

    data = await request.json()
    strategy = data.get('strategy')

    if not strategy:
        raise HTTPException(status_code=400, detail="strategy is required")

    result = update_etf_strategy(etf_code, strategy)
    return result


@app.put("/api/watchlist/{etf_code}/settings")
async def update_etf_settings(etf_code: str, request: Request):
    """更新ETF的高级设置"""
    from core.watchlist import update_etf_settings

    data = await request.json()
    total_positions = data.get('total_positions')
    build_position_date = data.get('build_position_date')

    result = update_etf_settings(etf_code, total_positions, build_position_date)
    return result


@app.delete("/api/watchlist/{etf_code}")
async def remove_etf_from_watchlist(etf_code: str):
    """从自选删除ETF"""
    from core.watchlist import remove_from_watchlist

    result = remove_from_watchlist(etf_code)
    return result


@app.get("/api/watchlist/{etf_code}/signal")
async def get_etf_realtime_signal(etf_code: str, start_date: Optional[str] = '20250101', strategy: Optional[str] = None):
    """获取ETF实时信号和持仓状态"""
    from core.watchlist import calculate_realtime_signal

    result = calculate_realtime_signal(etf_code, start_date, strategy)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@app.get("/api/macd/backtest/watchlist/{etf_code}")
async def run_backtest_for_watchlist(etf_code: str, start_date: Optional[str] = '20250101', strategy: Optional[str] = None):
    """为自选ETF运行回测"""
    from core.watchlist import run_backtest

    result = run_backtest(etf_code, start_date, strategy)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@app.get("/api/profit/all-etfs-daily")
async def get_all_etfs_daily_profit(start_date: Optional[str] = '20240101'):
    """获取所有自选ETF的每日汇总收益（用于收益日历和图表）

    返回所有ETF每天的总收益/亏损金额、仓位变化、累计收益曲线
    """
    from core.watchlist import load_watchlist, run_backtest
    from collections import defaultdict
    from datetime import datetime

    watchlist = load_watchlist()
    etfs = watchlist.get('etfs', [])

    # 按日期汇总数据
    daily_data_map = defaultdict(lambda: {
        'total_profit': 0,
        'total_positions': 0,
        'total_value': 0,
        'etf_profits': [],
        'active_etfs': set()
    })

    # 存储所有日期的总资产和仓位数据
    timeline_data = {}

    for etf in etfs:
        etf_code = etf['code']
        strategy = etf.get('strategy', 'macd_aggressive')
        initial_capital = etf.get('initial_capital', 2000)

        try:
            # 获取该ETF的回测数据
            result = run_backtest(etf_code, start_date, strategy)

            if not result['success'] or not result.get('data'):
                continue

            performance = result['data'].get('performance', [])
            if not performance or len(performance) == 0:
                continue

            # 处理每天的回测数据
            for i in range(len(performance)):
                p = performance[i]
                date_str = str(p['date'])

                # 初始化该日期的数据
                if date_str not in timeline_data:
                    timeline_data[date_str] = {
                        'date': date_str,
                        'total_value': 0,
                        'total_positions': 0,
                        'active_etf_count': 0
                    }

                # 计算单日收益（使用实际的portfolio_value，而不是假设等于initial_capital）
                curr_value = p.get('portfolio_value', initial_capital)
                if i == 0:
                    # 第一天收益为0，但current_value使用实际的portfolio_value
                    daily_profit = 0
                    current_value = curr_value
                else:
                    prev_value = performance[i-1].get('portfolio_value', initial_capital)
                    daily_profit = curr_value - prev_value
                    current_value = curr_value

                positions_used = p.get('positions_used', 0)

                daily_data_map[date_str]['total_profit'] += daily_profit
                daily_data_map[date_str]['total_positions'] += positions_used
                daily_data_map[date_str]['total_value'] += current_value
                daily_data_map[date_str]['active_etfs'].add(etf_code)
                daily_data_map[date_str]['etf_profits'].append({
                    'code': etf_code,
                    'name': etf.get('name', etf_code),
                    'profit': daily_profit,
                    'positions': positions_used
                })

                # 累加到时间线数据
                timeline_data[date_str]['total_value'] += current_value
                timeline_data[date_str]['total_positions'] += positions_used

        except Exception as e:
            print(f"Error processing {etf_code}: {e}")
            continue

    # 计算总初始资本
    total_initial_capital = sum([etf.get('initial_capital', 2000) for etf in etfs])
    total_positions_max = sum([etf.get('total_positions', 10) for etf in etfs])

    # 转换为列表格式
    daily_profit_list = []
    timeline_list = []
    cumulative_value = total_initial_capital

    for date_str in sorted(timeline_data.keys()):
        data = daily_data_map[date_str]

        # 计算该日期涉及的ETF数量
        etf_count = len(data['active_etfs'])

        # 构建每日收益数据
        daily_profit_list.append({
            'date': date_str,
            'daily_profit': data['total_profit'],
            'etf_count': etf_count,
            'etf_profits': data['etf_profits']
        })

        # 计算累计收益
        cumulative_value = data['total_value']

        # 构建时间线数据
        timeline_list.append({
            'date': date_str,
            'total_value': cumulative_value,
            'total_positions': timeline_data[date_str]['total_positions'],
            'cumulative_profit': cumulative_value - total_initial_capital,
            'active_etf_count': timeline_data[date_str]['active_etf_count']
        })

    return {
        'success': True,
        'data': {
            'daily_profits': daily_profit_list,
            'timeline': timeline_list,
            'total_initial_capital': total_initial_capital,
            'total_positions_max': total_positions_max,
            'etf_count': len(etfs)
        }
    }


@app.put("/api/watchlist/{etf_code}/position")
async def update_etf_position(etf_code: str, request: Request):
    """更新ETF的当前持仓金额"""
    from core.watchlist import update_etf_position

    data = await request.json()
    position_value = data.get('position_value')

    if position_value is None:
        raise HTTPException(status_code=400, detail="position_value is required")

    result = update_etf_position(etf_code, position_value)
    return result


@app.get("/api/watchlist/{etf_code}/weight-status")
async def get_etf_weight_status(etf_code: str):
    """获取ETF权重状态"""
    from core.weight_manager import check_weight_status

    try:
        status = check_weight_status(etf_code)
        return {
            'success': True,
            'status': status
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/watchlist/{etf_code}/kline-data")
async def get_etf_kline_data(etf_code: str, start_date: Optional[str] = '20240101'):
    """获取ETF K线数据（OHLCV）"""
    from core.database import get_etf_daily_data

    data = get_etf_daily_data(etf_code, start_date)
    if not data:
        raise HTTPException(status_code=404, detail="无法获取ETF数据")

    # 限制数据量
    max_data_points = 500
    if len(data) > max_data_points:
        data = data[-max_data_points:]

    return {
        'success': True,
        'data': {
            'dates': [d['trade_date'] for d in data],
            'open': [d['open'] for d in data],
            'high': [d['high'] for d in data],
            'low': [d['low'] for d in data],
            'close': [d['close'] for d in data],
            'volume': [d['vol'] for d in data]
        }
    }


@app.post("/api/watchlist/{etf_code}/optimize-weights")
async def optimize_etf_weights(etf_code: str, background_tasks: BackgroundTasks):
    """手动触发权重优化（后台运行）"""
    import subprocess
    from pathlib import Path

    # 创建优化脚本
    script_content = f'''#!/usr/bin/env python3
import sys
sys.path.append('{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}')

from optimization.optimize_etf_advanced import AdvancedETFOptimizer

optimizer = AdvancedETFOptimizer(
    etf_code='{etf_code}',
    start_date='20240101',
    end_date=None,
    cv_folds=2,
    test_size=0.2
)

result = optimizer.run_optimization()

if result:
    print(f"✅ {{etf_code}} 权重优化完成")
else:
    print(f"❌ {{etf_code}} 权重优化失败")
'''

    # 写入临时脚本
    script_file = Path(f'/tmp/optimize_{etf_code.replace(".", "_")}.py')
    script_file.write_text(script_content)

    # 后台运行
    log_file = Path(f'/tmp/optimize_{etf_code.replace(".", "_")}.log')
    process = subprocess.Popen(
        ['python3', str(script_file)],
        stdout=open(log_file, 'w'),
        stderr=subprocess.STDOUT
    )

    return {
        'success': True,
        'message': f'权重优化已启动（后台运行）',
        'log_file': str(log_file),
        'pid': process.pid
    }


# ==================== 数据更新端点 ====================

@app.get("/api/data/latest-date")
async def get_latest_data_date():
    """获取数据库中最新的交易日期"""
    from core.database import get_etf_connection

    conn = get_etf_connection()
    if not conn:
        return {
            'success': False,
            'latest_date': None
        }

    cursor = conn.cursor()

    # 获取所有ETF中最新的交易日期
    cursor.execute('''
        SELECT MAX(trade_date) as latest_date
        FROM etf_daily
    ''')

    result = cursor.fetchone()
    conn.close()

    latest_date = result['latest_date'] if result else None

    return {
        'success': True,
        'latest_date': latest_date
    }


@app.post("/api/data/update")
async def update_market_data(background_tasks: BackgroundTasks):
    """更新市场数据（后台运行）"""
    # 返回提示信息
    return {
        'success': True,
        'message': '数据更新功能需要配置TUSHARE_TOKEN',
        'note': '如需更新数据，请在config.py中配置TUSHARE_TOKEN后运行: python scripts/download_etf_data.py'
    }


# ==================== MACD 参数管理 ====================

@app.post("/api/watchlist/{etf_code}/macd-params")
async def save_macd_params(etf_code: str, request: Request):
    """保存优化后的MACD参数到自选列表

    Body: {
        "macd_fast": 8,
        "macd_slow": 17,
        "macd_signal": 5
    }
    """
    from core.watchlist import load_watchlist, save_watchlist

    data = await request.json()

    # 验证参数
    required_params = ['macd_fast', 'macd_slow', 'macd_signal']
    for param in required_params:
        if param not in data:
            raise HTTPException(status_code=400, detail=f"缺少参数: {param}")

    # 验证参数范围
    if not (5 <= data['macd_fast'] <= 20):
        raise HTTPException(status_code=400, detail="macd_fast 必须在 5-20 之间")
    if not (15 <= data['macd_slow'] <= 40):
        raise HTTPException(status_code=400, detail="macd_slow 必须在 15-40 之间")
    if not (3 <= data['macd_signal'] <= 12):
        raise HTTPException(status_code=400, detail="macd_signal 必须在 3-12 之间")
    if data['macd_slow'] <= data['macd_fast'] + 5:
        raise HTTPException(status_code=400, detail="macd_slow 必须大于 macd_fast + 5")
    if data['macd_signal'] >= data['macd_fast']:
        raise HTTPException(status_code=400, detail="macd_signal 必须小于 macd_fast")

    # 加载自选列表
    watchlist = load_watchlist()

    # 查找并更新ETF的优化参数
    etf_found = False
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            etf['optimized_macd_params'] = {
                'macd_fast': data['macd_fast'],
                'macd_slow': data['macd_slow'],
                'macd_signal': data['macd_signal']
            }
            etf_found = True
            break

    if not etf_found:
        raise HTTPException(status_code=404, detail=f"ETF {etf_code} 不在自选列表中")

    # 保存自选列表
    if save_watchlist(watchlist):
        # 清除缓存，确保下次加载时使用新参数
        from core.database import clear_batch_cache
        clear_batch_cache()

        return {
            'success': True,
            'message': f'成功保存 {etf_code} 的MACD参数',
            'params': data
        }
    else:
        raise HTTPException(status_code=500, detail='保存失败')


@app.delete("/api/watchlist/{etf_code}/macd-params")
async def delete_macd_params(etf_code: str):
    """删除优化后的MACD参数，恢复默认参数"""
    from core.watchlist import load_watchlist, save_watchlist

    # 加载自选列表
    watchlist = load_watchlist()

    # 查找并删除ETF的优化参数
    etf_found = False
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            if 'optimized_macd_params' in etf:
                del etf['optimized_macd_params']
            etf_found = True
            break

    if not etf_found:
        raise HTTPException(status_code=404, detail=f"ETF {etf_code} 不在自选列表中")

    # 保存自选列表
    if save_watchlist(watchlist):
        # 清除缓存，确保下次加载时使用新参数
        from core.database import clear_batch_cache
        clear_batch_cache()

        return {
            'success': True,
            'message': f'已恢复 {etf_code} 的默认MACD参数'
        }
    else:
        raise HTTPException(status_code=500, detail='保存失败')


# ==================== MACD+KDJ离散策略参数管理 ====================

@app.post("/api/watchlist/{etf_code}/macd-kdj-discrete-params")
async def save_macd_kdj_discrete_params(etf_code: str, request: Request):
    """保存优化后的MACD+KDJ离散策略参数到自选列表

    Body: {
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "kdj_n": 9,
        "kdj_m1": 3,
        "kdj_m2": 3
    }
    """
    from core.watchlist import load_watchlist, save_watchlist

    data = await request.json()

    # 验证MACD参数
    macd_required = ['macd_fast', 'macd_slow', 'macd_signal']
    for param in macd_required:
        if param not in data:
            raise HTTPException(status_code=400, detail=f"缺少MACD参数: {param}")

    # 验证KDJ参数
    kdj_required = ['kdj_n', 'kdj_m1', 'kdj_m2']
    for param in kdj_required:
        if param not in data:
            raise HTTPException(status_code=400, detail=f"缺少KDJ参数: {param}")

    # 验证MACD参数范围
    if not (5 <= data['macd_fast'] <= 25):
        raise HTTPException(status_code=400, detail="macd_fast 必须在 5-25 之间")
    if not (15 <= data['macd_slow'] <= 50):
        raise HTTPException(status_code=400, detail="macd_slow 必须在 15-50 之间")
    if not (3 <= data['macd_signal'] <= 15):
        raise HTTPException(status_code=400, detail="macd_signal 必须在 3-15 之间")
    if data['macd_slow'] <= data['macd_fast'] + 5:
        raise HTTPException(status_code=400, detail="macd_slow 必须大于 macd_fast + 5")
    # 注意：signal可以大于或等于fast，不同的MACD变体有不同的规则
    # 所以这里移除 signal < fast 的限制

    # 验证KDJ参数范围
    if not (3 <= data['kdj_n'] <= 20):
        raise HTTPException(status_code=400, detail="kdj_n 必须在 3-20 之间")
    if not (2 <= data['kdj_m1'] <= 6):
        raise HTTPException(status_code=400, detail="kdj_m1 必须在 2-6 之间")
    if not (2 <= data['kdj_m2'] <= 6):
        raise HTTPException(status_code=400, detail="kdj_m2 必须在 2-6 之间")

    # 加载自选列表
    watchlist = load_watchlist()

    # 查找并更新ETF的优化参数
    etf_found = False
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            etf['optimized_params'] = {
                'macd_fast': data['macd_fast'],
                'macd_slow': data['macd_slow'],
                'macd_signal': data['macd_signal'],
                'kdj_n': data['kdj_n'],
                'kdj_m1': data['kdj_m1'],
                'kdj_m2': data['kdj_m2']
            }
            etf_found = True
            break

    if not etf_found:
        raise HTTPException(status_code=404, detail=f"ETF {etf_code} 不在自选列表中")

    # 保存自选列表
    if save_watchlist(watchlist):
        # 清除缓存，确保下次加载时使用新参数
        from core.database import clear_batch_cache
        clear_batch_cache()

        return {
            'success': True,
            'message': f'成功保存 {etf_code} 的MACD+KDJ离散策略参数',
            'params': data
        }
    else:
        raise HTTPException(status_code=500, detail='保存失败')


@app.delete("/api/watchlist/{etf_code}/macd-kdj-discrete-params")
async def delete_macd_kdj_discrete_params(etf_code: str):
    """删除优化后的MACD+KDJ离散策略参数，恢复默认参数"""
    from core.watchlist import load_watchlist, save_watchlist

    # 加载自选列表
    watchlist = load_watchlist()

    # 查找并删除ETF的优化参数
    etf_found = False
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            if 'optimized_params' in etf:
                del etf['optimized_params']
            etf_found = True
            break

    if not etf_found:
        raise HTTPException(status_code=404, detail=f"ETF {etf_code} 不在自选列表中")

    # 保存自选列表
    if save_watchlist(watchlist):
        # 清除缓存，确保下次加载时使用新参数
        from core.database import clear_batch_cache
        clear_batch_cache()

        return {
            'success': True,
            'message': f'已恢复 {etf_code} 的默认MACD+KDJ离散策略参数'
        }
    else:
        raise HTTPException(status_code=500, detail='保存失败')


@app.get("/api/watchlist/{etf_code}/macd-kdj-discrete-params")
async def get_macd_kdj_discrete_params(etf_code: str):
    """获取ETF的MACD+KDJ离散策略优化参数"""
    from core.watchlist import load_watchlist

    watchlist = load_watchlist()

    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            optimized_params = etf.get('optimized_params', None)

            if optimized_params:
                return {
                    'success': True,
                    'has_optimized': True,
                    'params': {
                        'macd_fast': optimized_params.get('macd_fast', 12),
                        'macd_slow': optimized_params.get('macd_slow', 26),
                        'macd_signal': optimized_params.get('macd_signal', 9),
                        'kdj_n': optimized_params.get('kdj_n', 9),
                        'kdj_m1': optimized_params.get('kdj_m1', 3),
                        'kdj_m2': optimized_params.get('kdj_m2', 3)
                    }
                }
            else:
                return {
                    'success': True,
                    'has_optimized': False,
                    'params': {
                        'macd_fast': 12,
                        'macd_slow': 26,
                        'macd_signal': 9,
                        'kdj_n': 9,
                        'kdj_m1': 3,
                        'kdj_m2': 3
                    }
                }

    raise HTTPException(status_code=404, detail=f"ETF {etf_code} 不在自选列表中")


@app.post("/api/watchlist/{etf_code}/rsi-triple-lines-params")
async def save_rsi_triple_lines_params(etf_code: str, request: Request):
    """保存优化后的RSI三线参数到自选列表"""
    from core.watchlist import load_watchlist, save_watchlist

    data = await request.json()

    # 验证参数
    if 'rsi1_period' not in data:
        raise HTTPException(status_code=400, detail="缺少参数: rsi1_period")
    if 'rsi2_period' not in data:
        raise HTTPException(status_code=400, detail="缺少参数: rsi2_period")
    if 'rsi3_period' not in data:
        raise HTTPException(status_code=400, detail="缺少参数: rsi3_period")

    rsi1 = data['rsi1_period']
    rsi2 = data['rsi2_period']
    rsi3 = data['rsi3_period']

    # 验证参数范围
    if not (3 <= rsi1 <= 12):
        raise HTTPException(status_code=400, detail="rsi1_period 必须在 3-12 之间")
    if not (6 <= rsi2 <= 20):
        raise HTTPException(status_code=400, detail="rsi2_period 必须在 6-20 之间")
    if not (15 <= rsi3 <= 35):
        raise HTTPException(status_code=400, detail="rsi3_period 必须在 15-35 之间")

    # 验证满足 rsi1 < rsi2 < rsi3
    if not (rsi1 < rsi2 < rsi3):
        raise HTTPException(status_code=400, detail="参数必须满足 rsi1 < rsi2 < rsi3")

    # 加载自选列表
    watchlist = load_watchlist()

    # 查找并更新ETF的优化参数
    etf_found = False
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            etf['optimized_params'] = {
                'rsi1_period': rsi1,
                'rsi2_period': rsi2,
                'rsi3_period': rsi3
            }
            etf_found = True
            break

    if not etf_found:
        raise HTTPException(status_code=404, detail=f"ETF {etf_code} 不在自选列表中")

    # 保存
    if save_watchlist(watchlist):
        return {
            'success': True,
            'message': f'RSI三线参数已保存',
            'params': {
                'rsi1_period': rsi1,
                'rsi2_period': rsi2,
                'rsi3_period': rsi3
            }
        }
    else:
        raise HTTPException(status_code=500, detail='保存失败')


@app.get("/api/watchlist/{etf_code}/rsi-triple-lines-params")
async def get_rsi_triple_lines_params(etf_code: str):
    """获取ETF的RSI三线参数（优化后的或默认的）"""
    from core.watchlist import load_watchlist

    watchlist = load_watchlist()

    # 默认参数
    default_params = {
        'rsi1_period': 6,
        'rsi2_period': 12,
        'rsi3_period': 24
    }

    # 查找ETF的优化参数
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            optimized_params = etf.get('optimized_params', {})
            if optimized_params:
                # 验证优化参数是否完整
                if all(k in optimized_params for k in ['rsi1_period', 'rsi2_period', 'rsi3_period']):
                    return {
                        'success': True,
                        'params': optimized_params,
                        'has_optimized': True
                    }

            return {
                'success': True,
                'params': default_params,
                'has_optimized': False
            }

    # ETF不在自选列表中
    return {
        'success': True,
        'params': default_params,
        'has_optimized': False
    }


@app.post("/api/watchlist/{etf_code}/reset-params")
async def reset_optimized_params(etf_code: str, request: Request):
    """清除ETF的优化参数，恢复默认值"""
    from core.watchlist import load_watchlist, save_watchlist

    watchlist = load_watchlist()

    # 查找并删除优化参数
    etf_found = False
    for etf in watchlist['etfs']:
        if etf['code'] == etf_code:
            if 'optimized_params' in etf:
                del etf['optimized_params']
            etf_found = True
            break

    if not etf_found:
        raise HTTPException(status_code=404, detail=f"ETF {etf_code} 不在自选列表中")

    # 保存
    if save_watchlist(watchlist):
        return {
            'success': True,
            'message': '已恢复默认参数'
        }
    else:
        raise HTTPException(status_code=500, detail='保存失败')


# ==================== 数据更新调度器 API ====================

@app.get("/api/data-update/token-status")
async def get_token_status():
    """检查Tushare Token配置状态（优先从settings读取）"""
    from core.settings_manager import get_settings_manager

    # 优先从settings读取
    settings_mgr = get_settings_manager()
    token = settings_mgr.settings.get('tushare', {}).get('token', '')

    # Fallback到config
    if not token:
        token = config.TUSHARE_TOKEN or ''

    token_configured = bool(token)
    token_preview = None

    if token_configured:
        # 只显示前10个字符
        token_preview = token[:10] + '...'

    return {
        'success': True,
        'data': {
            'configured': token_configured,
            'token_preview': token_preview,
            'message': '已配置' if token_configured else '未配置'
        }
    }


@app.get("/api/data-update/scheduler/status")
async def get_scheduler_status():
    """获取调度器状态"""
    try:
        from core.data_update_scheduler import get_scheduler
        scheduler = get_scheduler()
        status = scheduler.get_status()

        return {
            'success': True,
            'data': status
        }
    except Exception as e:
        # 返回默认状态而不是错误
        return {
            'success': True,
            'data': {
                'enabled': False,
                'is_running': False,
                'update_time': '15:05',
                'next_run': None,
                'update_status': {
                    'is_updating': False,
                    'message': f'调度器初始化失败: {str(e)}'
                },
                'error': str(e)
            }
        }


@app.post("/api/data-update/scheduler/configure")
async def configure_scheduler(request: Request):
    """配置调度器

    Body:
        enabled: bool 是否启用
        update_time: str 更新时间 "HH:MM"
    """
    try:
        from core.data_update_scheduler import get_scheduler
        scheduler = get_scheduler()

        data = await request.json()
        enabled = data.get('enabled', False)
        update_time = data.get('update_time', '15:05')

        # 设置更新时间
        if not scheduler.set_update_time(update_time):
            raise HTTPException(status_code=400, detail='无效的时间格式，请使用 HH:MM 格式')

        # 启用/禁用调度器
        scheduler.set_enabled(enabled)

        return {
            'success': True,
            'message': f'调度器已{"启用" if enabled else "禁用"}，更新时间: {update_time}',
            'data': scheduler.get_status()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data-update/scheduler/trigger")
async def trigger_update():
    """立即触发一次数据更新"""
    try:
        from core.data_update_scheduler import get_scheduler
        scheduler = get_scheduler()

        if scheduler.update_status['is_updating']:
            return {
                'success': False,
                'message': '更新任务正在进行中，请稍后再试'
            }

        if scheduler.trigger_now():
            return {
                'success': True,
                'message': '已启动数据更新任务'
            }
        else:
            return {
                'success': False,
                'message': '启动失败'
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/data-update/trigger")
async def trigger_data_update(background_tasks: BackgroundTasks):
    """手动触发数据更新（独立API，不依赖调度器）

    在后台线程中执行更新任务
    """
    def run_update():
        try:
            from scripts.auto_update_data import run_auto_update
            run_auto_update(force=False)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"数据更新失败: {e}")

    background_tasks.add_task(run_update)

    return {
        'success': True,
        'message': '数据更新任务已启动（后台执行）'
    }


# ==================== 实时监控 API ====================

@app.get("/api/realtime/minishare-status")
async def get_minishare_status():
    """检查 minishare 配置状态"""
    token_configured = bool(config.MINISHARE_TOKEN)
    token_preview = None

    if token_configured:
        # 只显示前10个字符
        token_preview = config.MINISHARE_TOKEN[:10] + '...'

    # 检查 SDK 是否安装
    sdk_installed = False
    try:
        import minishare
        sdk_installed = True
    except ImportError:
        pass

    return {
        'success': True,
        'data': {
            'configured': token_configured,
            'token_preview': token_preview,
            'sdk_installed': sdk_installed,
            'message': '已配置' if token_configured else '未配置',
            'sdk_message': '已安装' if sdk_installed else '未安装 (运行: pip install minishare --upgrade)'
        }
    }

@app.get("/api/realtime/status")
async def get_realtime_status():
    """获取实时更新状态"""
    from core.data_update_scheduler import get_scheduler
    from datetime import datetime

    scheduler = get_scheduler()
    status = scheduler.get_realtime_status()

    # 判断当前是否为交易时间
    now = datetime.now()
    current_time = now.time()
    weekday = now.weekday()

    # 默认交易时间：09:25-15:05
    start = datetime.strptime("09:25", "%H:%M").time()
    end = datetime.strptime("15:05", "%H:%M").time()

    is_trading_time = (
        weekday < 5 and  # 工作日
        start <= current_time <= end
    )

    return {
        'success': True,
        'data': {
            'enabled': status.get('enabled', False),
            'is_trading_time': is_trading_time,
            'updater_status': status
        }
    }


@app.post("/api/realtime/toggle")
async def toggle_realtime(request: Request):
    """切换实时更新状态"""
    from core.data_update_scheduler import get_scheduler
    from datetime import datetime

    data = await request.json()
    enabled = data.get('enabled', False)

    scheduler = get_scheduler()
    scheduler.set_realtime_enabled(enabled)

    # 判断当前是否为交易时间
    now = datetime.now()
    current_time = now.time()
    weekday = now.weekday()

    start = datetime.strptime("09:25", "%H:%M").time()
    end = datetime.strptime("15:05", "%H:%M").time()

    is_trading_time = (
        weekday < 5 and
        start <= current_time <= end
    )

    return {
        'success': True,
        'message': f"实时更新已{'启用' if enabled else '禁用'}",
        'data': {
            'enabled': enabled,
            'is_trading_time': is_trading_time
        }
    }


@app.get("/api/realtime/settings")
async def get_realtime_settings():
    """获取实时更新设置"""
    from core.data_update_scheduler import get_scheduler

    scheduler = get_scheduler()
    status = scheduler.get_realtime_status()

    return {
        'success': True,
        'data': {
            'start_time': status.get('start_time', '09:25'),
            'end_time': status.get('end_time', '15:05'),
            'update_interval': status.get('update_interval', 60)
        }
    }


@app.post("/api/realtime/settings")
async def update_realtime_settings(request: Request):
    """更新实时更新设置"""
    from core.data_update_scheduler import get_scheduler

    data = await request.json()
    start_time = data.get('start_time', '09:25')
    end_time = data.get('end_time', '15:05')
    update_interval = data.get('update_interval', 60)

    scheduler = get_scheduler()

    # 验证时间格式
    try:
        from datetime import datetime
        datetime.strptime(start_time, '%H:%M')
        datetime.strptime(end_time, '%H:%M')
    except ValueError:
        raise HTTPException(status_code=400, detail='无效的时间格式，请使用 HH:MM 格式')

    # 验证时间范围
    if start_time >= end_time:
        raise HTTPException(status_code=400, detail='开始时间必须早于结束时间')

    # 验证更新间隔
    if not (10 <= update_interval <= 600):
        raise HTTPException(status_code=400, detail='更新间隔必须在10-600秒之间')

    # 设置新的时间范围和更新间隔
    success = scheduler.set_realtime_settings(start_time, end_time, update_interval)

    if success:
        return {
            'success': True,
            'message': '设置已保存',
            'data': {
                'start_time': start_time,
                'end_time': end_time,
                'update_interval': update_interval
            }
        }
    else:
        return {
            'success': False,
            'message': '设置失败（实时更新器未初始化）'
        }


# ==================== 系统设置API ====================

@app.get("/api/settings")
async def get_settings():
    """获取系统设置"""
    from core.settings_manager import get_settings_manager

    settings_mgr = get_settings_manager()
    return {
        'success': True,
        'data': settings_mgr.get_settings()
    }


@app.post("/api/settings")
async def update_settings(request: Request):
    """更新系统设置"""
    from core.settings_manager import get_settings_manager

    try:
        data = await request.json()

        # 过滤敏感字段的验证
        settings_mgr = get_settings_manager()
        result = settings_mgr.update_settings(data)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'更新设置失败: {str(e)}')


@app.post("/api/settings/tokens")
async def update_tokens(request: Request):
    """更新API Tokens"""
    from core.settings_manager import get_settings_manager

    try:
        data = await request.json()

        tushare_token = data.get('tushare_token', '').strip()
        minishare_token = data.get('minishare_token', '').strip()

        settings_mgr = get_settings_manager()
        result = settings_mgr.update_tokens(
            tushare_token=tushare_token if tushare_token else None,
            minishare_token=minishare_token if minishare_token else None
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'更新Token失败: {str(e)}')


@app.post("/api/settings/data-source")
async def update_data_source(request: Request):
    """更新数据源配置"""
    from core.settings_manager import get_settings_manager

    try:
        data = await request.json()

        settings_mgr = get_settings_manager()

        # 更新数据源优先级
        if 'priority' in data:
            if isinstance(data['priority'], list):
                # 验证优先级
                valid_sources = ['minishare', 'tushare', 'fund_daily', 'rt_etf_k']
                if not all(s in valid_sources for s in data['priority']):
                    raise HTTPException(status_code=400, detail='无效的数据源类型')

                updates = {
                    'data_source': {
                        'priority': data['priority']
                    }
                }

                # 根据优先级自动启用/禁用数据源
                enabled_data = {}
                for source in data['priority']:
                    if source in ['minishare', 'rt_etf_k']:
                        enabled_data[source] = True
                    elif source in ['tushare', 'fund_daily']:
                        enabled_data[source] = True

                # 更新各个数据源的启用状态
                if 'minishare' in enabled_data:
                    updates['minishare'] = {'enabled': enabled_data['minishare']}
                if 'tushare' in enabled_data:
                    updates['tushare'] = {'enabled': enabled_data['tushare']}

                settings_mgr.update_settings(updates)

                return {
                    'success': True,
                    'message': f"数据源优先级已更新: {' → '.join(data['priority'])}",
                    'data': {
                        'priority': data['priority']
                    }
                }

        raise HTTPException(status_code=400, detail='无效的请求参数')
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'更新数据源失败: {str(e)}')


@app.get("/api/settings/data-source/status")
async def get_data_source_status():
    """获取当前数据源状态"""
    from core.settings_manager import get_settings_manager
    import config

    settings_mgr = get_settings_manager()

    # 检查各个数据源的状态
    active_source = settings_mgr.get_active_data_source()

    sources = []

    # Tushare状态
    tushare_enabled = settings_mgr.settings.get('tushare', {}).get('enabled', False)
    tushare_token = bool(settings_mgr.settings.get('tushare', {}).get('token'))
    sources.append({
        'name': 'Tushare',
        'active': tushare_enabled and tushare_token,
        'token_configured': tushare_token
    })

    # Minishare状态
    minishare_enabled = settings_mgr.settings.get('minishare', {}).get('enabled', False)
    minishare_token = bool(settings_mgr.settings.get('minishare', {}).get('token'))
    sources.append({
        'name': 'Minishare',
        'active': minishare_enabled and minishare_token,
        'token_configured': minishare_token
    })

    status = {
        'active_source': active_source,
        'sources': sources
    }

    return {
        'success': True,
        'data': status
    }


@app.post("/api/settings/test-token")
async def test_token(request: Request):
    """测试API Token连接"""
    try:
        data = await request.json()
        source = data.get('source')
        token = data.get('token', '').strip()

        if not source or not token:
            raise HTTPException(status_code=400, detail='缺少必要参数')

        if source == 'tushare':
            # 测试Tushare Token
            try:
                import tushare as ts
                ts.set_token(token)
                pro = ts.pro_api()

                # 尝试获取一条数据验证连接
                df = pro.trade_cal(exchange='SSE', start_date='20240101', end_date='20240101')

                if df is not None:
                    return {
                        'success': True,
                        'message': 'Tushare连接成功',
                        'data': {'source': 'tushare', 'valid': True}
                    }
                else:
                    return {
                        'success': False,
                        'message': 'Tushare Token无效或无权限'
                    }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Tushare连接失败: {str(e)}'
                }

        elif source == 'minishare':
            # 测试Minishare Token
            try:
                import minishare as ms
                pro = ms.pro_api(token)

                # 尝试获取一条数据验证连接
                df = pro.trade_cal(exchange='SSE', start_date='20240101', end_date='20240101')

                if df is not None and not df.empty:
                    return {
                        'success': True,
                        'message': 'Minishare连接成功',
                        'data': {'source': 'minishare', 'valid': True}
                    }
                else:
                    return {
                        'success': False,
                        'message': 'Minishare Token无效或无权限'
                    }
            except Exception as e:
                return {
                    'success': False,
                    'message': f'Minishare连接失败: {str(e)}'
                }

        else:
            raise HTTPException(status_code=400, detail=f'不支持的数据源: {source}')

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'测试Token失败: {str(e)}')


# ==================== 飞书通知配置 ====================

@app.get("/api/feishu/config")
async def get_feishu_config():
    """获取飞书通知配置（从 conf.json）"""
    try:
        import json
        conf_path = os.path.join(config.BASE_DIR, 'conf.json')

        if not os.path.exists(conf_path):
            return {
                'success': True,
                'data': {
                    'enabled': False,
                    'default_bot': 'bot_1',
                    'bots': [],
                    'notifications': {}
                }
            }

        with open(conf_path, 'r', encoding='utf-8') as f:
            full_config = json.load(f)

        feishu_config = full_config.get('feishu', {})

        # 隐藏app_secret
        if 'bots' in feishu_config:
            for bot in feishu_config['bots']:
                if bot.get('app_secret'):
                    bot['app_secret'] = '******' if bot['app_secret'] else ''

        return {
            'success': True,
            'data': feishu_config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取飞书配置失败: {str(e)}')


@app.post("/api/feishu/config")
async def update_feishu_config(request: Request):
    """更新飞书通知配置（保存到 conf.json）"""
    try:
        import json
        conf_path = os.path.join(config.BASE_DIR, 'conf.json')

        data = await request.json()

        # 读取完整配置
        if os.path.exists(conf_path):
            with open(conf_path, 'r', encoding='utf-8') as f:
                full_config = json.load(f)
        else:
            full_config = {}

        # 保留app_secret（如果前端发送的是******）
        if 'bots' in data:
            if 'feishu' in full_config:
                for new_bot in data['bots']:
                    for old_bot in full_config['feishu'].get('bots', []):
                        if (new_bot.get('id') == old_bot.get('id') and
                            new_bot.get('app_secret') == '******'):
                            new_bot['app_secret'] = old_bot.get('app_secret', '')

        # 更新飞书配置
        full_config['feishu'] = data

        # 保存到 conf.json
        with open(conf_path, 'w', encoding='utf-8') as f:
            json.dump(full_config, f, ensure_ascii=False, indent=2)

        # 重新加载飞书通知器配置
        from core.feishu_notifier import get_feishu_notifier
        notifier = get_feishu_notifier()
        notifier.load_config()

        return {
            'success': True,
            'message': '飞书配置已更新'
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'更新飞书配置失败: {str(e)}')


@app.post("/api/feishu/test")
async def test_feishu_connection(request: Request):
    """测试飞书连接"""
    from core.feishu_notifier import get_feishu_notifier

    try:
        data = await request.json()
        bot_id = data.get('bot_id')
        test_message = data.get('message', '这是一条测试消息')

        notifier = get_feishu_notifier()
        success = await notifier.send_message(f"🔔 飞书连接测试\n\n{test_message}", bot_id)

        if success:
            return {
                'success': True,
                'message': '测试消息发送成功'
            }
        else:
            return {
                'success': False,
                'message': '发送失败，请检查配置'
            }
    except Exception as e:
        return {
            'success': False,
            'message': f'测试失败: {str(e)}'
        }


@app.post("/api/feishu/send")
async def send_feishu_message(request: Request):
    """手动发送飞书消息"""
    from core.feishu_notifier import get_feishu_notifier

    try:
        data = await request.json()
        message = data.get('message', '')
        bot_id = data.get('bot_id')

        if not message:
            raise HTTPException(status_code=400, detail='消息内容不能为空')

        notifier = get_feishu_notifier()
        success = await notifier.send_message(message, bot_id)

        if success:
            return {
                'success': True,
                'message': '消息发送成功'
            }
        else:
            return {
                'success': False,
                'message': '发送失败'
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'发送消息失败: {str(e)}')


# ==================== 配置文件API ====================

@app.get("/api/config")
async def get_system_config():
    """获取系统配置（config.json）"""
    try:
        config_data = config.get_config()

        # 隐藏敏感信息
        safe_config = config_data.copy()

        # 隐藏大部分token
        if safe_config.get('tushare', {}).get('token'):
            token = safe_config['tushare']['token']
            safe_config['tushare']['token'] = token[:8] + "..." if token and len(token) > 8 else (token or "")

        if safe_config.get('minishare', {}).get('token'):
            token = safe_config['minishare']['token']
            safe_config['minishare']['token'] = token[:8] + "..." if token and len(token) > 8 else (token or "")

        # 隐藏session key
        if safe_config.get('auth', {}).get('session_secret_key'):
            key = safe_config['auth']['session_secret_key']
            if key and len(key) > 20:
                safe_config['auth']['session_secret_key'] = key[:20] + "..."

        return {
            'success': True,
            'data': safe_config
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'获取配置失败: {str(e)}')


@app.post("/api/config")
async def update_system_config(request: Request):
    """更新系统配置（config.json）"""
    try:
        data = await request.json()

        # 读取当前配置
        current_config = config.get_config()

        # 保留敏感字段（如果前端发送的是隐藏值）
        if 'auth' in data:
            if data['auth'].get('session_secret_key', '').endswith('...'):
                data['auth']['session_secret_key'] = current_config['auth']['session_secret_key']
            if data['auth'].get('auth_key', '') == '******':
                data['auth']['auth_key'] = current_config['auth']['auth_key']

        if 'tushare' in data:
            if data['tushare'].get('token', '').endswith('...'):
                data['tushare']['token'] = current_config['tushare']['token']

        if 'minishare' in data:
            if data['minishare'].get('token', '').endswith('...'):
                data['minishare']['token'] = current_config['minishare']['token']

        # 更新配置
        success = config.update_config(data)

        if success:
            # 重新加载认证配置
            if 'auth' in data:
                import hashlib
                global AUTH_KEY, AUTH_KEY_HASH, SESSION_SECRET_KEY
                AUTH_KEY = data['auth']['auth_key']
                AUTH_KEY_HASH = hashlib.sha256(AUTH_KEY.encode()).hexdigest()
                SESSION_SECRET_KEY = data['auth']['session_secret_key']

            # 重新加载token
            if 'tushare' in data:
                global TUSHARE_TOKEN
                TUSHARE_TOKEN = data['tushare']['token']

            if 'minishare' in data:
                global MINISHARE_TOKEN
                MINISHARE_TOKEN = data['minishare']['token']

            return {
                'success': True,
                'message': '配置已更新，重启后生效'
            }
        else:
            raise HTTPException(status_code=500, detail='更新配置失败')

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'更新配置失败: {str(e)}')


@app.post("/api/config/reload")
async def reload_system_config():
    """重新加载配置文件"""
    try:
        config.reload_config()
        return {
            'success': True,
            'message': '配置已重新加载'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'重新加载配置失败: {str(e)}')


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
