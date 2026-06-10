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
from core.profit_calculator import (
    calculate_monthly_profit_from_rows as _shared_calculate_monthly_profit_from_rows,
    calculate_slot_profit_series as _shared_calculate_slot_profit_series,
    normalize_trade_date as _shared_normalize_trade_date,
)
from core.auth import router as auth_router, require_auth
from api.data_service import (
    DataServiceAuthError,
    data_service_auth_exception_handler,
    router as data_service_router,
)

app = FastAPI(title=config.API_TITLE, version=config.API_VERSION)
logger = logging.getLogger(__name__)
app.add_exception_handler(DataServiceAuthError, data_service_auth_exception_handler)


def _normalize_trade_date(value) -> str:
    return _shared_normalize_trade_date(value)


def _calculate_monthly_profit_from_rows(
    daily_rows,
    snapshot_positions,
    fallback_positions: int = 0,
    data_date: str = '',
) -> float:
    return _shared_calculate_monthly_profit_from_rows(
        daily_rows=daily_rows,
        snapshot_positions=snapshot_positions,
        fallback_positions=fallback_positions,
        data_date=data_date,
    )


def _calculate_slot_profit_series(
    daily_rows,
    snapshot_positions,
    fallback_positions: int = 0,
    start_date: str = '',
) -> list:
    return _shared_calculate_slot_profit_series(
        daily_rows=daily_rows,
        snapshot_positions=snapshot_positions,
        fallback_positions=fallback_positions,
        start_date=start_date,
    )


def _get_position_snapshots_for_profit(etf_code: str, data_date: str) -> dict:
    from core.position_manager import _get_conn

    cutoff = _normalize_trade_date(data_date)
    if not cutoff:
        return {}

    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT trade_date, positions
        FROM position_snapshots
        WHERE etf_code = ? AND trade_date <= ?
        ORDER BY trade_date
        """,
        (etf_code, cutoff),
    ).fetchall()
    conn.close()
    return {row['trade_date']: row['positions'] for row in rows}


def calculate_monthly_profit(etf_code: str, data_date: str, fallback_positions: int = 0) -> float:
    try:
        from core.database import get_etf_daily_data

        daily_rows = get_etf_daily_data(etf_code)
        snapshots = _get_position_snapshots_for_profit(etf_code, data_date)
        return _calculate_monthly_profit_from_rows(
            daily_rows=daily_rows,
            snapshot_positions=snapshots,
            fallback_positions=fallback_positions,
            data_date=data_date,
        )
    except Exception:
        return 0.0

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

        # 3. 数据服务路由 - 跳过 session 认证，路由依赖中处理 API Key
        if path == "/api/data-service" or path.startswith("/api/data-service/"):
            return await call_next(request)

        # 4. 检查session是否可用
        if "session" not in request.scope:
            # Session未配置，允许继续（可能有其他中间件处理）
            return await call_next(request)

        # 5. 页面路由 - 需要认证，未认证则重定向
        page_routes = ["/", "/macd-watchlist", "/profit", "/settings"]
        if path in page_routes or path.endswith("/"):
            if not request.session.get("authenticated"):
                # 保存原始URL用于登录后跳转
                request.session["redirect_after_login"] = path
                # 使用 RedirectResponse
                from starlette.responses import RedirectResponse
                return RedirectResponse(url="/login", status_code=302)
            return await call_next(request)

        # 6. API路由 - 需要认证，未认证则返回401
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

        # 7. 其他路由 - 正常处理
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
app.include_router(data_service_router, tags=["Data Service"])


@app.on_event("startup")
async def restore_scheduler_on_startup():
    """应用启动时恢复调度器配置"""
    try:
        from core.data_update_scheduler import get_scheduler

        scheduler = get_scheduler()
        scheduler.restore_from_config(config.get_config())

        status = scheduler.get_status()
        logger.info(
            "调度器启动恢复完成: data_update=%s, feishu=%s, running=%s",
            status['enabled'],
            status['feishu_notification']['enabled'],
            status['is_running']
        )
    except Exception as e:
        logger.error(f"调度器启动恢复失败: {e}")


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


@app.get("/health")
async def health_check():
    """健康检查端点 - 用于 Docker 容器健康检查"""
    return {
        "status": "healthy",
        "service": config.API_TITLE,
        "version": config.API_VERSION
    }


@app.get("/", response_class=HTMLResponse)
async def index_page(request: Request):
    """Home page - 批量展示策略、持仓、下个交易日操作"""
    return templates.TemplateResponse(request, "index.html")


@app.get("/macd-watchlist", response_class=HTMLResponse)
async def macd_watchlist_page(request: Request):
    """MACD Strategy watchlist page with split-view layout."""
    return templates.TemplateResponse(request, "macd_watchlist.html")


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """System settings page."""
    return templates.TemplateResponse(request, "settings.html")


@app.get("/profit", response_class=HTMLResponse)
async def profit_page(request: Request):
    """Profit summary page - 所有ETF汇总收益"""
    auth_check = await require_auth(request)
    if auth_check:
        return auth_check
    return templates.TemplateResponse(request, "profit.html")


# ==================== 批量数据端点 ====================

@app.get("/api/watchlist/batch-signals")
async def get_batch_signals(refresh: bool = False, realtime: bool = False):
    """批量获取所有自选ETF的策略、持仓、下个交易日操作

    Args:
        refresh: 是否强制刷新缓存
        realtime: 是否使用实时模式（只计算当天，不回测历史）
    """
    from core.position_signal_service import build_position_signal_rows

    return build_position_signal_rows(refresh=refresh, realtime=realtime)


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

    cache_data_date = f"{data_date}_{config.DEFAULT_START_DATE}"

    # 如果不强制刷新，尝试从缓存获取
    if not refresh:
        cached = get_batch_cache('backtest', cache_data_date)
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
        backtest_result = run_backtest(etf_code, config.DEFAULT_START_DATE, strategy)
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
    set_batch_cache('backtest', cache_data_date, cache_data)

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
async def get_etf_realtime_signal(etf_code: str, start_date: Optional[str] = config.DEFAULT_START_DATE, strategy: Optional[str] = None):
    """获取ETF实时信号和持仓状态"""
    from core.watchlist import calculate_realtime_signal

    result = calculate_realtime_signal(etf_code, start_date, strategy)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@app.get("/api/macd/backtest/watchlist/{etf_code}")
async def run_backtest_for_watchlist(etf_code: str, start_date: Optional[str] = config.DEFAULT_START_DATE, strategy: Optional[str] = None):
    """为自选ETF运行回测"""
    from core.watchlist import run_backtest

    result = run_backtest(etf_code, start_date, strategy)
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['message'])

    return result


@app.get("/api/profit/all-etfs-daily")
async def get_all_etfs_daily_profit(start_date: Optional[str] = '20260603'):
    """获取所有自选ETF的每日汇总收益（用于收益日历和图表）

    返回所有ETF每天的总收益/亏损金额、仓位变化、累计收益曲线

    从 2026-06-03（position_snapshots 表创建后）开始有真实仓位数据。
    """
    from core.watchlist import load_watchlist
    from core.database import get_etf_daily_data
    from collections import defaultdict

    watchlist = load_watchlist()
    etfs = watchlist.get('etfs', [])

    # 规范化 start_date 用于 snapshot 查找
    _start_date_clean = start_date.replace('-', '') if start_date else '20260603'

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
    total_initial_capital = 0

    for etf in etfs:
        etf_code = etf['code']

        try:
            daily_rows = get_etf_daily_data(etf_code, start_date=start_date)
            if not daily_rows:
                continue

            snapshots = _get_position_snapshots_for_profit(etf_code, '99999999')
            # 用 start_date 当天的 snapshot 仓位作为起点（而非当前 DB 仓位）
            start_snapshot_positions = int(snapshots.get(_start_date_clean, 0) or 0)
            total_initial_capital += start_snapshot_positions * 200

            profit_series = _calculate_slot_profit_series(
                daily_rows=daily_rows,
                snapshot_positions=snapshots,
                fallback_positions=start_snapshot_positions,
                start_date=start_date,
            )

            for p in profit_series:
                date_str = str(p['date'])

                # 初始化该日期的数据
                if date_str not in timeline_data:
                    timeline_data[date_str] = {
                        'date': date_str,
                        'total_value': 0,
                        'total_positions': 0,
                        'active_etf_count': 0
                    }

                daily_profit = p.get('daily_profit', 0)
                positions_used = p.get('positions', 0)

                daily_data_map[date_str]['total_profit'] += daily_profit
                daily_data_map[date_str]['total_positions'] += positions_used
                daily_data_map[date_str]['total_value'] += daily_profit
                daily_data_map[date_str]['active_etfs'].add(etf_code)
                daily_data_map[date_str]['etf_profits'].append({
                    'code': etf_code,
                    'name': etf.get('name', etf_code),
                    'profit': daily_profit,
                    'positions': positions_used
                })

                # 累加到时间线数据
                timeline_data[date_str]['total_value'] += daily_profit
                timeline_data[date_str]['total_positions'] += positions_used
                if positions_used > 0:
                    timeline_data[date_str]['active_etf_count'] += 1

        except Exception as e:
            print(f"Error processing {etf_code}: {e}")
            continue

    # 初始资本已在循环中按 start_date snapshot 仓位累加
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
        cumulative_value += data['total_profit']

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
async def get_etf_kline_data(etf_code: str, start_date: Optional[str] = config.DEFAULT_START_DATE):
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
        'message': '数据更新功能需要配置 tinyshare 授权码',
        'note': '首次使用请执行 pip install tinyshare --upgrade，并在 config.json 中配置 tinyshare.token 后运行: python scripts/download_etf_data.py'
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
    """检查 tinyshare 授权码配置状态（优先读取 tinyshare.token）"""
    token = config.TINYSHARE_TOKEN or ''
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
            'message': '已配置 tinyshare 授权码' if token_configured else '未配置 tinyshare 授权码'
        }
    }


@app.get("/api/data-update/scheduler/status")
async def get_scheduler_status():
    """获取调度器状态"""
    try:
        from core.scheduler_settings_service import get_scheduler_settings_status
        return get_scheduler_settings_status()
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
        data = await request.json()
        enabled = data.get('enabled', False)
        update_time = data.get('update_time', '15:05')

        from core.scheduler_settings_service import configure_data_update_schedule
        return configure_data_update_schedule(enabled, update_time)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
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


@app.post("/api/feishu/notification/configure")
async def configure_feishu_notification(request: Request):
    """配置飞书消息定时发送

    Body:
        enabled: bool 是否启用
        times: list 发送时间列表 ["HH:MM", "HH:MM", ...]
    """
    try:
        data = await request.json()
        enabled = data.get('enabled', False)
        times = data.get('times', ["09:40", "10:40", "11:40", "13:40", "14:40"])

        from core.scheduler_settings_service import configure_feishu_notification_schedule
        return configure_feishu_notification_schedule(enabled, times)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/feishu/notification/trigger")
async def trigger_feishu_notification():
    """立即触发一次飞书消息发送"""
    try:
        from core.data_update_scheduler import get_scheduler
        scheduler = get_scheduler()

        if scheduler.feishu_notification_status['is_sending']:
            return {
                'success': False,
                'message': '飞书消息正在发送中，请稍后再试'
            }

        # 在新线程中执行发送
        import threading
        thread = threading.Thread(target=scheduler._send_feishu_notification, daemon=True)
        thread.start()

        return {
            'success': True,
            'message': '已启动飞书消息发送任务'
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/macd/optimization/schedule/configure")
async def configure_macd_optimization_schedule(request: Request):
    """配置MACD参数优化定时任务

    Body:
        enabled: bool 是否启用
        time: str 优化时间 "HH:MM"
        notify_feishu: bool 优化完成后是否发送飞书操作建议
    """
    try:
        data = await request.json()
        enabled = data.get('enabled', False)
        opt_time = data.get('time', '23:00')
        notify_feishu = data.get('notify_feishu') if 'notify_feishu' in data else None

        from core.scheduler_settings_service import configure_macd_optimization_schedule
        return configure_macd_optimization_schedule(enabled, opt_time, notify_feishu)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/macd/optimization/schedule/trigger")
async def trigger_macd_optimization():
    """立即触发一次MACD参数优化"""
    try:
        from core.data_update_scheduler import get_scheduler
        scheduler = get_scheduler()

        if scheduler.macd_optimization_status['is_running']:
            return {
                'success': False,
                'message': 'MACD参数优化任务正在进行中，请稍后再试'
            }

        if scheduler.trigger_macd_optimization_now():
            return {
                'success': True,
                'message': '已启动MACD参数优化任务'
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
# 注意：旧的 /api/settings 端点已被 /api/config 替代
# 以下是保留的数据源状态检查端点

@app.get("/api/settings/data-source/status")
async def get_data_source_status():
    """获取当前数据源状态（从config.json读取）"""
    import config

    sources = []

    # Tushare状态
    tushare_token = bool(config.TUSHARE_TOKEN)
    sources.append({
        'name': 'Tushare',
        'active': tushare_token,
        'token_configured': tushare_token
    })

    # Minishare状态
    minishare_token = bool(config.MINISHARE_TOKEN)
    sources.append({
        'name': 'Minishare',
        'active': minishare_token,
        'token_configured': minishare_token
    })

    # 确定活跃数据源（Minishare优先）
    active_source = 'Minishare' if minishare_token else ('Tushare' if tushare_token else '无')

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
        proxy_url = data.get('proxy_url', '').strip()  # 获取代理 URL

        if not source or not token:
            raise HTTPException(status_code=400, detail='缺少必要参数')

        if source == 'tushare':
            # 测试Tushare Token
            try:
                import tushare as ts
                pro = ts.pro_api(token)

                # ⭐ 设置代理 URL（如果提供）
                if proxy_url:
                    pro._DataApi__http_url = proxy_url
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
                global TUSHARE_TOKEN, TUSHARE_PROXY_URL
                TUSHARE_TOKEN = data['tushare']['token']
                TUSHARE_PROXY_URL = data['tushare'].get('proxy_url', '')

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


# ==================== 持仓管理 API ====================

@app.get("/api/positions")
async def list_positions():
    """获取所有ETF的当前持仓"""
    from core.position_manager import get_all_positions

    positions = get_all_positions()
    return {
        'success': True,
        'data': positions,
        'count': len(positions),
    }


@app.get("/api/positions/{etf_code}")
async def get_etf_position(etf_code: str):
    """获取单个ETF的当前持仓"""
    from core.position_manager import get_position

    pos = get_position(etf_code)
    if not pos:
        return {
            'success': True,
            'data': None,
            'message': f'{etf_code} 暂无持仓记录',
        }
    return {
        'success': True,
        'data': pos,
    }


@app.get("/api/positions/{etf_code}/suggestion")
async def get_position_suggestion(etf_code: str, strategy: Optional[str] = None):
    """获取ETF持仓调整建议

    对比信号target_position与DB当前仓位，返回操作建议。
    """
    from core.position_manager import get_position_suggestion as pos_suggestion
    from core.watchlist import load_watchlist, calculate_realtime_signal

    # 从信号获取 target_position
    signal_result = calculate_realtime_signal(etf_code, config.DEFAULT_START_DATE, strategy)
    if not signal_result['success']:
        raise HTTPException(status_code=400, detail=signal_result.get('message', '信号计算失败'))

    target_position = signal_result['data'].get('positions_used', 0)
    latest_price = signal_result['data'].get('latest_data', {}).get('close', None)

    suggestion = pos_suggestion(etf_code, target_position, latest_price)

    # 附加快照信息
    watchlist = load_watchlist()
    etf_entry = next((e for e in watchlist.get('etfs', []) if e['code'] == etf_code), None)
    strategy_used = strategy or (etf_entry.get('strategy', 'macd_aggressive') if etf_entry else 'macd_aggressive')

    return {
        'success': True,
        'data': {
            **suggestion,
            'strategy': strategy_used,
            'signal_date': signal_result['data'].get('latest_date'),
        },
    }


@app.post("/api/positions/{etf_code}/execute")
async def execute_position_change(etf_code: str, request: Request):
    """执行持仓变更

    Body: {
        "action": "BUY" | "SELL",
        "price": 1.234,
        "positions_before": 3,
        "positions_after": 5,
        "strategy": "macd_aggressive"
    }
    """
    from core.position_manager import execute_position_change as exec_change

    data = await request.json()
    action = data.get('action')
    price = data.get('price')
    positions_before = data.get('positions_before')
    positions_after = data.get('positions_after')
    strategy = data.get('strategy')

    if not all([action, price is not None, positions_before is not None, positions_after is not None]):
        raise HTTPException(status_code=400, detail='缺少必要参数: action, price, positions_before, positions_after')

    if action not in ('BUY', 'SELL'):
        raise HTTPException(status_code=400, detail='action 必须是 BUY 或 SELL')

    result = exec_change(
        etf_code=etf_code,
        action=action,
        price=float(price),
        positions_before=int(positions_before),
        positions_after=int(positions_after),
        strategy=strategy,
    )

    if not result.get('success'):
        return {
            'success': True,
            'data': result,
            'message': result.get('message', '无需操作'),
        }

    return {
        'success': True,
        'data': result,
        'message': f'{etf_code} {action} {result["shares"]}股 @ {price}',
    }


@app.get("/api/trades")
async def list_trades(
    etf_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 200,
):
    """查询交易记录"""
    from core.position_manager import get_trades

    trades = get_trades(etf_code=etf_code, start_date=start_date, end_date=end_date, limit=limit)
    return {
        'success': True,
        'data': trades,
        'count': len(trades),
    }


@app.get("/api/positions/{etf_code}/pnl")
async def get_etf_pnl(etf_code: str):
    """获取ETF的实际盈亏（基于交易记录FIFO计算）"""
    from core.position_manager import calculate_pnl

    pnl = calculate_pnl(etf_code)
    return {
        'success': True,
        'data': pnl,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT)
