"""
每日自动更新ETF数据脚本

功能：
1. 增量下载最新交易日数据
2. 更新SQLite数据库
3. 清理过期缓存
4. 记录更新日志
5. 可选：发送通知

使用方法：
1. 手动运行：python scripts/auto_update_data.py
2. 定时任务：使用cron或schedule库
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tushare as ts
import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta
import config

# ==================== 配置 ====================

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, 'auto_update.log')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# 收盘时间（下午3点）
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 5


# ==================== 辅助函数 ====================

def get_tushare_token():
    """获取Tushare Token（从config.json读取）"""
    # 从config读取
    if config.TUSHARE_TOKEN:
        logger.info("✅ 从config读取Tushare Token")
        return config.TUSHARE_TOKEN

    return None

# 等待时间（收盘后多少分钟开始更新）
WAIT_MINUTES_AFTER_CLOSE = 10


# ==================== 工具函数 ====================

def get_latest_trade_date():
    """获取最近的交易日

    如果今天是交易日且已收盘，返回今天
    否则返回上一个交易日
    """
    now = datetime.now()
    current_time = now.time()
    close_time = now.time().replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0, microsecond=0)

    # 判断是否是交易日（周一到周五）
    is_weekday = now.weekday() < 5  # 0-4 表示周一到周五

    # 判断是否已收盘
    is_after_close = current_time >= close_time

    # 如果是工作日且已收盘，尝试获取今天的数据
    if is_weekday and is_after_close:
        today_str = now.strftime('%Y%m%d')
        logger.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}, 已收盘，尝试更新 {today_str} 的数据")
        return today_str
    else:
        # 返回上一个交易日
        if is_weekday and not is_after_close:
            # 今天还没收盘，获取上周五或昨天的数据
            if now.weekday() == 0:  # 周一
                last_trade_day = (now - timedelta(days=3)).strftime('%Y%m%d')
            else:
                last_trade_day = (now - timedelta(days=1)).strftime('%Y%m%d')
            logger.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}, 未收盘，获取 {last_trade_day} 的数据")
            return last_trade_day
        else:
            # 周末，获取上周五的数据
            last_trade_day = (now - timedelta(days=now.weekday() - 4)).strftime('%Y%m%d')
            logger.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}, 周末，获取 {last_trade_day} 的数据")
            return last_trade_day


def get_latest_date_in_db(etf_code):
    """获取数据库中某ETF的最新数据日期"""
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(trade_date) FROM etf_daily WHERE ts_code = ?",
            (etf_code,)
        )
        result = cursor.fetchone()
        conn.close()

        if result and result[0]:
            return result[0]
        return None
    except Exception as e:
        logger.error(f"查询数据库失败: {e}")
        return None


def get_etf_list_from_watchlist():
    """从watchlist获取需要更新的ETF列表"""
    try:
        from core.watchlist import load_watchlist
        watchlist = load_watchlist()
        etfs = [etf['code'] for etf in watchlist.get('etfs', [])]
        logger.info(f"从watchlist获取到 {len(etfs)} 个ETF")
        return etfs
    except Exception as e:
        logger.error(f"获取watchlist失败: {e}")
        # 如果watchlist加载失败，使用config中的函数读取
        from config import get_etf_list
        return get_etf_list()[:20]  # 限制前20个


def download_latest_data(etf_code, target_date):
    """下载ETF的最新数据

    Args:
        etf_code: ETF代码
        target_date: 目标日期（YYYYMMDD格式）

    Returns:
        DataFrame or None
    """
    token = get_tushare_token()
    if not token:
        logger.error("❌ TUSHARE_TOKEN 未配置（请到设置页面配置）")
        return None

    try:
        # 获取数据库中最新的日期
        latest_db_date = get_latest_date_in_db(etf_code)

        # 确定下载的起始日期（从数据库最新日期的下一天开始）
        if latest_db_date:
            latest_dt = datetime.strptime(latest_db_date, '%Y%m%d')
            start_date = (latest_dt + timedelta(days=1)).strftime('%Y%m%d')
            logger.info(f"{etf_code}: 数据库最新日期 {latest_db_date}，将从 {start_date} 开始下载")
        else:
            # 数据库没有数据，下载最近30天
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
            logger.info(f"{etf_code}: 数据库无数据，将从 {start_date} 开始下载")

        # 如果起始日期已经大于目标日期，说明数据已经是最新的
        if start_date > target_date:
            logger.info(f"{etf_code}: ✅ 数据已是最新（数据库最新日期 {latest_db_date}）")
            return None

        # 下载数据
        ts.set_token(token)
        pro = ts.pro_api()

        # 使用代理API
        pro._DataApi__token = token
        pro._DataApi__http_url = 'http://lianghua.nanyangqiankun.top'

        logger.info(f"{etf_code}: 正在下载 {start_date} ~ {target_date} 的数据...")
        df = pro.fund_daily(ts_code=etf_code, start_date=start_date, end_date=target_date)

        if df.empty:
            logger.warning(f"{etf_code}: ⚠️  无新数据")
            return None

        logger.info(f"{etf_code}: ✅ 下载到 {len(df)} 条新数据")
        return df

    except Exception as e:
        logger.error(f"{etf_code}: ❌ 下载失败 - {e}")
        return None


def save_to_database(etf_code, df):
    """保存数据到数据库

    注意：本脚本使用fund_daily接口，单位已经是"手"和"千元"，无需转换
    """
    try:
        conn = sqlite3.connect(config.DATABASE_PATH)
        df.to_sql('etf_daily', conn, if_exists='append', index=False)
        conn.close()

        logger.info(f"{etf_code}: ✅ 数据已保存到数据库")
        return True
    except Exception as e:
        logger.error(f"{etf_code}: ❌ 保存失败 - {e}")
        return False


def clear_cache():
    """清理批量缓存"""
    try:
        from core.database import get_batch_cache_db
        import json

        cache_db = get_batch_cache_db()
        cursor = cache_db.cursor()

        # 删除所有缓存
        cursor.execute("DELETE FROM batch_cache")
        cache_db.commit()
        cache_db.close()

        logger.info("✅ 批量缓存已清理")
        return True
    except Exception as e:
        logger.error(f"❌ 清理缓存失败: {e}")
        return False


def update_summary(start_time, success_list, fail_list, skip_list):
    """输出更新摘要"""
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    logger.info("=" * 60)
    logger.info("📊 更新摘要")
    logger.info("=" * 60)
    logger.info(f"开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"耗时: {duration:.1f} 秒")
    logger.info("")
    logger.info(f"总数: {len(success_list) + len(fail_list) + len(skip_list)}")
    logger.info(f"✅ 成功: {len(success_list)}")
    logger.info(f"❌ 失败: {len(fail_list)}")
    logger.info(f"⏭️  跳过: {len(skip_list)}")

    if success_list:
        logger.info("")
        logger.info("成功更新的ETF:")
        for code in success_list[:10]:
            logger.info(f"  - {code}")
        if len(success_list) > 10:
            logger.info(f"  ... 还有 {len(success_list) - 10} 个")

    if fail_list:
        logger.info("")
        logger.info("失败的ETF:")
        for code in fail_list:
            logger.info(f"  - {code}")

    logger.info("=" * 60)


# ==================== 主函数 ====================

def run_auto_update(force=False):
    """运行自动更新

    Args:
        force: 是否强制更新（忽略时间检查）
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("🚀 开始每日自动更新")
    logger.info("=" * 60)

    # 检查Tushare Token
    token = get_tushare_token()
    if not token:
        logger.error("❌ TUSHARE_TOKEN 未配置")
        logger.error("   获取Token: https://tushare.pro/register")
        logger.error("   配置方法: 访问系统设置页面 (http://localhost:8000/settings)")
        return False

    # 获取目标日期
    target_date = get_latest_trade_date()
    logger.info(f"目标日期: {target_date}")

    # 获取需要更新的ETF列表
    etf_list = get_etf_list_from_watchlist()
    if not etf_list:
        logger.error("❌ 没有找到需要更新的ETF")
        return False

    # 逐个更新
    success_list = []
    fail_list = []
    skip_list = []

    for i, etf_code in enumerate(etf_list, 1):
        logger.info(f"\n[{i}/{len(etf_list)}] 处理 {etf_code}...")

        # 下载数据
        df = download_latest_data(etf_code, target_date)

        if df is None:
            # 无新数据，跳过
            skip_list.append(etf_code)
            continue
        elif df.empty:
            # 下载失败
            fail_list.append(etf_code)
            continue
        else:
            # 保存到数据库
            if save_to_database(etf_code, df):
                success_list.append(etf_code)
            else:
                fail_list.append(etf_code)

    # 清理缓存
    logger.info("\n清理缓存...")
    clear_cache()

    # 输出摘要
    update_summary(start_time, success_list, fail_list, skip_list)

    # 返回结果
    all_success = len(fail_list) == 0
    if all_success:
        logger.info("✅ 自动更新完成！")
    else:
        logger.warning(f"⚠️  部分ETF更新失败（{len(fail_list)}/{len(etf_list)}）")

    return all_success


# ==================== 定时任务 ====================

def run_scheduler():
    """运行定时调度器

    每天收盘后（15:05）开始执行
    """
    import schedule
    import time

    # 设置定时任务：每个工作日的15:05执行
    schedule.every().monday.at("15:05").do(run_auto_update)
    schedule.every().tuesday.at("15:05").do(run_auto_update)
    schedule.every().wednesday.at("15:05").do(run_auto_update)
    schedule.every().thursday.at("15:05").do(run_auto_update)
    schedule.every().friday.at("15:05").do(run_auto_update)

    logger.info("=" * 60)
    logger.info("📅 定时任务已启动")
    logger.info("=" * 60)
    logger.info("执行时间: 每个交易日 15:05")
    logger.info("按 Ctrl+C 停止")
    logger.info("=" * 60)

    # 持续运行
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次


# ==================== 入口 ====================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='ETF数据自动更新工具')
    parser.add_argument('--schedule', action='store_true',
                       help='启动定时任务（持续运行）')
    parser.add_argument('--once', action='store_true',
                       help='立即执行一次更新')
    parser.add_argument('--force', action='store_true',
                       help='强制更新（忽略时间检查）')

    args = parser.parse_args()

    if args.schedule:
        # 启动定时任务
        try:
            run_scheduler()
        except KeyboardInterrupt:
            logger.info("\n👋 定时任务已停止")
    else:
        # 执行一次更新
        run_auto_update(force=args.force)
