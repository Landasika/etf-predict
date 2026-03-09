"""
实时数据更新器 - 每分钟获取最新行情

使用 minishare SDK 获取ETF实时行情数据
"""

import time
import threading
import logging
from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入统一的日志配置
from core.logging_config import setup_logger

# 配置日志
LOG_DIR = Path(__file__).parent.parent / 'logs'
LOG_DIR.mkdir(exist_ok=True)

# 使用轮转日志：单个文件最大10MB，保留5个备份
logger = setup_logger(
    name='realtime_updater',
    log_file=LOG_DIR / 'realtime_updater.log',
    max_bytes=10 * 1024 * 1024,  # 10MB
    backup_count=5
)


class RealtimeDataUpdater:
    """实时数据更新器 - 使用 minishare SDK 获取实时行情"""

    def __init__(self):
        self.is_running = False
        self.updater_thread = None
        self.update_interval = 60  # 每分钟更新一次
        self.start_time = "09:25"  # 默认开始时间（可配置）
        self.end_time = "15:05"    # 默认结束时间（可配置）
        self.update_status = {
            'is_updating': False,
            'last_update': None,
            'next_update': None,
            'etf_count': 0,
            'success_count': 0,
            'fail_count': 0,
            'message': ''
        }
        self.minishare_pro = None

    def _init_minishare(self):
        """初始化 minishare SDK"""
        if self.minishare_pro is None:
            try:
                import minishare as ms
                import config
                token = config.MINISHARE_TOKEN
                if not token:
                    logger.error("MINISHARE_TOKEN 未配置")
                    return False
                self.minishare_pro = ms.pro_api(token)
                logger.info("✅ minishare SDK 初始化成功")
                return True
            except ImportError:
                logger.error("minishare SDK 未安装，请运行: pip install minishare --upgrade")
                return False
            except Exception as e:
                logger.error(f"minishare SDK 初始化失败: {e}")
                return False
        return True

    def set_time_range(self, start_time: str, end_time: str):
        """设置监控时间范围

        Args:
            start_time: 开始时间 "HH:MM" 格式
            end_time: 结束时间 "HH:MM" 格式
        """
        try:
            # 验证时间格式
            datetime.strptime(start_time, '%H:%M')
            datetime.strptime(end_time, '%H:%M')

            self.start_time = start_time
            self.end_time = end_time
            logger.info(f"监控时间范围设置为: {start_time} - {end_time}")
            return True
        except ValueError:
            logger.error(f"无效的时间格式: {start_time} 或 {end_time}")
            return False

    def start(self):
        """启动实时更新"""
        if self.is_running:
            logger.warning("实时更新器已在运行")
            return False

        # 初始化 minishare SDK
        if not self._init_minishare():
            logger.error("无法启动实时更新器：minishare SDK 初始化失败")
            return False

        self.is_running = True
        self.updater_thread = threading.Thread(target=self._run_updater, daemon=True)
        self.updater_thread.start()
        logger.info("✅ 实时数据更新器已启动")
        return True

    def stop(self):
        """停止实时更新"""
        if not self.is_running:
            logger.warning("实时更新器未运行")
            return False

        self.is_running = False
        logger.info("⏹️  实时数据更新器已停止")
        return True

    def _run_updater(self):
        """更新器主循环"""
        logger.info("📅 实时更新器线程已启动")

        while self.is_running:
            try:
                now = datetime.now()
                current_time = now.strftime('%H:%M')

                # 检查是否在监控时间段
                if self._is_trading_time(now):
                    logger.info(f"🔄 [{current_time}] 开始更新实时数据...")

                    # 执行更新
                    self.update_status['is_updating'] = True
                    self.update_status['message'] = '正在获取实时行情...'
                    result = self._update_all_etfs()
                    self.update_status['is_updating'] = False

                    # 更新状态
                    self.update_status['last_update'] = now.strftime('%Y-%m-%d %H:%M:%S')
                    self.update_status['success_count'] = result['success']
                    self.update_status['fail_count'] = result['failed']
                    self.update_status['etf_count'] = result['total']
                    self.update_status['message'] = f'更新完成: {result["success"]}个成功'

                    logger.info(f"✅ 更新完成: 成功{result['success']}个, 失败{result['failed']}个")

                    # 交易时间内：每分钟检查一次
                    sleep_time = self.update_interval
                else:
                    # 非交易时间：智能休眠到下次开市前
                    sleep_time = self._calculate_sleep_time(now)
                    if sleep_time > 3600:  # 超过1小时
                        logger.info(f"😴 非交易时间，休眠 {sleep_time // 3600} 小时 {(sleep_time % 3600) // 60} 分钟")
                    else:
                        logger.info(f"😴 非交易时间，休眠 {sleep_time // 60} 分钟")

                    self.update_status['message'] = f'休市中，等待开市'

                # 等待下一次更新
                time.sleep(sleep_time)

            except Exception as e:
                logger.error(f"❌ 更新失败: {e}")
                self.update_status['is_updating'] = False
                self.update_status['message'] = f'更新失败: {str(e)}'

                # 出错后等待5分钟再重试
                time.sleep(300)

        logger.info("📅 实时更新器线程已停止")

    def _calculate_sleep_time(self, now: datetime) -> int:
        """计算距离下次开市的等待时间（秒）

        Args:
            now: 当前时间

        Returns:
            int: 等待秒数
        """
        weekday = now.weekday()
        current_time = now.time()
        today_date = now.date()

        # 解析监控时间范围
        start = datetime.strptime(self.start_time, "%H:%M").time()
        end = datetime.strptime(self.end_time, "%H:%M").time()

        # 周末：休眠到周一早上
        if weekday >= 5:  # 周六、周日
            # 下周一早上 start_time
            days_to_monday = 7 - weekday  # 周六=1, 周日=2
            next_monday = today_date + timedelta(days=days_to_monday)
            next_run = datetime.combine(next_monday, start)
            sleep_seconds = int((next_run - now).total_seconds())
            return max(sleep_seconds, 60)

        # 工作日早上：还没到开市时间，休眠到开市
        if current_time < start:
            # 今天早上 start_time
            next_run = datetime.combine(today_date, start)
            sleep_seconds = int((next_run - now).total_seconds())
            return max(sleep_seconds, 60)

        # 工作日收市后：已过交易时间
        if current_time > end:
            # 明天早上 start_time
            tomorrow = today_date + timedelta(days=1)
            next_run = datetime.combine(tomorrow, start)
            sleep_seconds = int((next_run - now).total_seconds())
            return max(sleep_seconds, 60)

        # 不应该在非交易时间到达这里，但如果到了，就休眠1分钟
        return 60

    def _is_trading_time(self, dt: datetime) -> bool:
        """判断是否为监控时间（使用自定义时间范围）

        注意：需要排除午休时间 (11:30-13:00)
        """
        current_time = dt.time()
        weekday = dt.weekday()

        # 周末不监控
        if weekday >= 5:  # 周六、周日
            return False

        # 解析监控时间范围
        start = datetime.strptime(self.start_time, "%H:%M").time()
        end = datetime.strptime(self.end_time, "%H:%M").time()

        # 检查是否在监控时间段内
        if not (start <= current_time <= end):
            return False

        # 排除午休时间 (11:30-13:00)
        lunch_start = datetime.strptime("11:30", "%H:%M").time()
        lunch_end = datetime.strptime("13:00", "%H:%M").time()
        if lunch_start <= current_time <= lunch_end:
            return False

        return True

    def _calculate_sleep_time(self, now: datetime) -> int:
        """计算距离下次开市的等待时间（秒）

        考虑午休时间：11:30-13:00

        Args:
            now: 当前时间

        Returns:
            int: 等待秒数
        """
        weekday = now.weekday()
        current_time = now.time()
        today_date = now.date()

        # 解析监控时间范围
        start = datetime.strptime(self.start_time, "%H:%M").time()
        end = datetime.strptime(self.end_time, "%H:%M").time()

        # 午休时间
        lunch_start = datetime.strptime("11:30", "%H:%M").time()
        lunch_end = datetime.strptime("13:00", "%H:%M").time()

        # 周末：休眠到周一早上
        if weekday >= 5:  # 周六、周日
            # 下周一早上 start_time
            days_to_monday = 7 - weekday  # 周六=1, 周日=2
            next_monday = today_date + timedelta(days=days_to_monday)
            next_run = datetime.combine(next_monday, start)
            sleep_seconds = int((next_run - now).total_seconds())
            return max(sleep_seconds, 60)

        # 工作日早上：还没到开市时间
        if current_time < start:
            # 今天早上 start_time
            next_run = datetime.combine(today_date, start)
            sleep_seconds = int((next_run - now).total_seconds())
            return max(sleep_seconds, 60)

        # 午休时间：休眠到下午开市
        if lunch_start <= current_time <= lunch_end:
            # 下午13:00
            next_run = datetime.combine(today_date, lunch_end)
            sleep_seconds = int((next_run - now).total_seconds())
            return max(sleep_seconds, 60)

        # 工作日收市后：已过交易时间
        if current_time > end:
            # 明天早上 start_time
            tomorrow = today_date + timedelta(days=1)
            next_run = datetime.combine(tomorrow, start)
            sleep_seconds = int((next_run - now).total_seconds())
            return max(sleep_seconds, 60)

        # 不应该在非交易时间到达这里，但如果到了，就休眠1分钟
        return 60

    def _update_all_etfs(self) -> Dict:
        """更新所有自选ETF的实时数据

        使用 minishare SDK 获取实时行情
        """
        from core.watchlist import load_watchlist
        from core.database import clear_batch_cache

        # 动态读取ETF列表（支持自选变化）
        watchlist = load_watchlist()
        etf_list = watchlist.get('etfs', [])

        if not etf_list:
            logger.warning("自选列表为空")
            return {'success': 0, 'failed': 0, 'total': 0}

        # 获取所有自选ETF的代码
        etf_codes = [etf['code'] for etf in etf_list]

        # 按交易所分组（SH 和 SZ）
        sh_codes = [code for code in etf_codes if code.endswith('.SH')]
        sz_codes = [code for code in etf_codes if code.endswith('.SZ')]

        success_count = 0
        fail_count = 0

        logger.info(f"准备更新 {len(etf_codes)} 个ETF: SH={len(sh_codes)}, SZ={len(sz_codes)}")

        # 分别获取 SH 和 SZ 的实时数据
        if sh_codes:
            result = self._fetch_market_data('SH', sh_codes)
            success_count += result['success']
            fail_count += result['failed']

        if sz_codes:
            result = self._fetch_market_data('SZ', sz_codes)
            success_count += result['success']
            fail_count += result['failed']

        # 清除缓存，强制前端重新计算
        clear_batch_cache()
        logger.info("🧹 缓存已清除，前端将重新计算信号")

        return {
            'success': success_count,
            'failed': fail_count,
            'total': len(etf_codes)
        }

    def _fetch_market_data(self, market: str, etf_codes: List[str]) -> Dict:
        """获取指定市场的ETF实时数据

        Args:
            market: 市场代码 ('SH' 或 'SZ')
            etf_codes: ETF代码列表

        Returns:
            dict: {'success': int, 'failed': int}
        """
        if not self.minishare_pro:
            return {'success': 0, 'failed': len(etf_codes)}

        success_count = 0
        fail_count = 0
        today_str = datetime.now().strftime('%Y%m%d')

        try:
            # 调用 minishare API 获取实时行情
            # ts_code 格式: '*.SH' 或 '*.SZ' 表示获取该市场所有ETF
            ts_code_pattern = f'*.{market}'
            logger.info(f"正在获取 {market} 市场的实时行情...")

            df = self.minishare_pro.rt_etf_k_ms(ts_code=ts_code_pattern)

            if df is None or df.empty:
                logger.warning(f"{market} 市场无数据返回")
                return {'success': 0, 'failed': len(etf_codes)}

            logger.info(f"{market} 市场返回 {len(df)} 条数据")

            # minishare 返回的列: ts_code, name, pre_close, high, open, low, close, vol, amount, change, pct_chg, sell_volume, buy_volume, vr, turnover

            # 按代码处理每个ETF
            for etf_code in etf_codes:
                try:
                    # 查找该ETF的数据
                    etf_df = df[df['ts_code'] == etf_code]

                    if etf_df.empty:
                        logger.warning(f"未找到 {etf_code} 的实时数据")
                        fail_count += 1
                        continue

                    # 获取最新的一条数据
                    latest = etf_df.iloc[-1]

                    # 保存到数据库（添加 trade_date）
                    self._save_to_database(latest, today_str)
                    success_count += 1

                    # 记录价格变化
                    close_price = float(latest.get('close', 0))
                    pct_change = float(latest.get('pct_chg', 0))
                    logger.info(f"  ✅ {etf_code}: 价格={close_price:.3f}, 涨跌={pct_change:+.2f}%")

                except Exception as e:
                    logger.error(f"处理 {etf_code} 数据失败: {e}")
                    fail_count += 1

        except Exception as e:
            logger.error(f"获取 {market} 市场数据失败: {e}")
            import traceback
            traceback.print_exc()
            return {'success': 0, 'failed': len(etf_codes)}

        return {'success': success_count, 'failed': fail_count}

    def _save_to_database(self, data_row: pd.Series, trade_date: str):
        """保存实时数据到数据库（自动转换单位）

        Minishare rt_etf_k_ms 接口返回的数据：
        - vol单位：股 → 需要除以100转为手
        - amount单位：元 → 需要除以1000转为千元

        Args:
            data_row: 单行数据（Series）
            trade_date: 交易日期（YYYYMMDD格式）
        """
        import sqlite3
        import config

        conn = sqlite3.connect(config.DATABASE_PATH)
        cursor = conn.cursor()

        try:
            # 准备数据并转换单位
            ts_code = str(data_row.get('ts_code', ''))

            # Minishare rt_etf_k_ms 接口：vol是"股"，需要除以100
            vol_lots = float(data_row.get('vol', 0)) / 100

            # Minishare rt_etf_k_ms 接口：amount是"元"，需要除以1000
            amount_thousand = float(data_row.get('amount', 0)) / 1000

            cursor.execute('''
                INSERT OR REPLACE INTO etf_daily
                (ts_code, trade_date, open, high, low, close, vol, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ts_code,
                trade_date,
                float(data_row.get('open', 0)),
                float(data_row.get('high', 0)),
                float(data_row.get('low', 0)),
                float(data_row.get('close', 0)),
                vol_lots,       # 已转换为"手"
                amount_thousand  # 已转换为"千元"
            ))

            conn.commit()
        except Exception as e:
            logger.error(f"保存数据到数据库失败: {e}")
        finally:
            conn.close()

    def get_status(self) -> Dict:
        """获取更新器状态"""
        return {
            'is_running': self.is_running,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'update_interval': self.update_interval,
            'update_status': self.update_status.copy()
        }


# 全局实例
realtime_updater = RealtimeDataUpdater()


def get_realtime_updater():
    """获取实时更新器实例"""
    return realtime_updater


if __name__ == '__main__':
    # 测试代码
    print("🧪 实时数据更新器测试")
    print("=" * 60)

    updater = get_realtime_updater()

    print("1. 设置时间范围为 09:25 - 15:05...")
    updater.set_time_range("09:25", "15:05")

    print("2. 测试交易时间判断...")
    now = datetime.now()
    print(f"   当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   是否交易时间: {updater._is_trading_time(now)}")

    print("\n3. 启动实时更新器...")
    if updater.start():
        print("   ✅ 实时更新器启动成功")

        # 运行一次更新测试
        print("\n4. 执行一次数据更新测试...")
        result = updater._update_all_etfs()
        print(f"   更新结果: 总计{result['total']}个, 成功{result['success']}个, 失败{result['failed']}个")

        # 停止
        print("\n5. 停止更新器...")
        updater.stop()
        print("   ✅ 已停止")
    else:
        print("   ❌ 实时更新器启动失败")
