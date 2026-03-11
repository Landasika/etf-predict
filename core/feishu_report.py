#!/usr/bin/env python3
"""
ETF操作建议报告生成器
生成飞书消息格式的ETF操作建议
"""
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from core.database import get_etf_connection
from core.watchlist import load_watchlist


class ETFOperationReport:
    """ETF操作建议报告生成器"""

    def __init__(self):
        self.watchlist = None
        self.etf_data = {}
        self.signals = {}

    def load_data(self):
        """加载所需数据"""
        # 加载自选列表
        self.watchlist = load_watchlist()
        if not self.watchlist or not self.watchlist.get('etfs'):
            return False

        # 从API获取信号数据（包含previous_positions_used）
        try:
            import requests
            # 尝试多个端口
            api_urls = [
                "http://127.0.0.1:8000/api/watchlist/batch-signals",
                "http://127.0.0.1:8001/api/watchlist/batch-signals"
            ]

            for api_url in api_urls:
                try:
                    response = requests.get(api_url, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if data.get('success'):
                            # 从API数据中提取所需信息
                            items = data.get('data', [])
                            for item in items:
                                code = item['code']
                                latest_data = item.get('latest_data', {})

                                self.etf_data[code] = {
                                    'name': item.get('name', code),
                                    'close': latest_data.get('close', 0),
                                    'pct_chg': latest_data.get('pct_chg', 0) or latest_data.get('change_pct', 0),
                                    'previous_positions_used': latest_data.get('previous_positions_used', 0),
                                    'positions_used': latest_data.get('positions_used', 0),
                                    'daily_profit': item.get('daily_profit', 0)
                                }

                            print(f"✓ 从API获取数据成功: {api_url}")
                            return True
                except requests.exceptions.ConnectionError:
                    continue
                except Exception as e:
                    print(f"API调用失败 ({api_url}): {e}")
                    continue

            print("❌ 所有API端点连接失败")

        except Exception as e:
            print(f"从API获取数据失败: {e}")

        # 如果API调用失败，使用数据库数据（fallback）
        # 获取ETF数据
        etfs = self.watchlist.get('etfs', [])
        for etf in etfs:
            code = etf['code']
            name = etf['name']
            strategy = etf.get('strategy', 'macd_aggressive')

            # 获取最新行情数据和ETF基本信息
            conn = get_etf_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT d.close, d.pct_chg, d.trade_date, b.extname
                    FROM etf_daily d
                    LEFT JOIN etf_basic b ON d.ts_code = b.ts_code
                    WHERE d.ts_code = ?
                    ORDER BY d.trade_date DESC
                    LIMIT 1
                """, (code,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    close, pct_chg, trade_date, extname = result

                    # 尝试从extname中解析持仓信息（格式：ETF名称 [X仓]）
                    previous_positions_used = 0
                    if extname and '[' in extname and '仓]' in extname:
                        try:
                            import re
                            match = re.search(r'\[(\d+)仓\]', extname)
                            if match:
                                previous_positions_used = int(match.group(1))
                        except:
                            pass

                    self.etf_data[code] = {
                        'name': extname.split(' [')[0] if extname and '[' in extname else name,
                        'close': close,
                        'pct_chg': pct_chg,
                        'trade_date': trade_date,
                        'previous_positions_used': previous_positions_used,
                        'positions_used': previous_positions_used,
                        'daily_profit': 0
                    }

        return True

    def generate_markdown_report(self) -> str:
        """生成Markdown格式的报告"""
        lines = []

        # 标题
        lines.append("# 🎯 ETF 操作建议")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 获取操作建议列表
        buy_list = self._get_buy_list()
        sell_list = self._get_sell_list()
        hold_list = self._get_hold_list()

        # 计算统计数据
        stats = self._calculate_stats()
        etf_count = len(self.watchlist.get('etfs', []))

        # 持仓统计
        lines.append("## 📊 持仓统计\n")
        lines.append("| 项目 | 数值 | 说明 |")
        lines.append("| --- | --- | --- |")

        lines.append(f"| 监控ETF | {etf_count}个 | 自选列表总数 |")
        lines.append(f"| 有持仓ETF | {stats.get('active_etf_count', 0)}个 | 昨日实际有持仓 |")
        lines.append(f"| 昨日总仓位 | {stats.get('total_positions', 0)}仓 | 实际持仓总和 |")
        lines.append(f"| 昨日总资金 | ¥{stats.get('total_capital', 0):,.0f} | 持仓总价值（200元/仓）|")
        lines.append(f"| 今日总收益 | ¥{stats.get('total_return', 0):+,.2f} | 当日浮动盈亏 |\n")

        # 今日操作建议总结
        lines.append("## 📋 今日操作建议\n")
        lines.append("| 操作类型 | 数量 | 说明 |")
        lines.append("| --- | --- | --- |")

        if sell_list:
            total_sell_positions = sum(item.get('suggested_positions', 0) for item in sell_list)
            lines.append(f"| 🔴 卖出 | {len(sell_list)}个 | 共{total_sell_positions}份 |")
        else:
            lines.append("| 🔴 卖出 | 0个 | 暂无卖出建议 |")

        if buy_list:
            total_buy_positions = sum(item.get('suggested_positions', 0) for item in buy_list)
            lines.append(f"| 🟢 买入 | {len(buy_list)}个 | 共{total_buy_positions}份 |")
        else:
            lines.append("| 🟢 买入 | 0个 | 暂无买入建议 |")

        if hold_list:
            lines.append(f"| 🟡 持有 | {len(hold_list)}个 | 观望待涨 |")
        else:
            lines.append("| 🟡 持有 | 0个 | 暂无持仓 |")

        lines.append("")

        # 建议卖出
        if sell_list:
            lines.append("## 🔴 建议卖出\n")
            lines.append("| ETF名称 | 操作 | 基金名称 | 代码 | 涨跌 | 价格 | 今日收益 | 仓位 |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")

            for item in sell_list[:10]:  # 最多显示10个
                daily_return = item.get('daily_return', 0)
                lines.append(
                    f"| {item['name']} | "
                    f"卖出{item['suggested_positions']}份 | "
                    f"{item['fund_name']} | "
                    f"`{item['code']}` | "
                    f"{item['change_pct']}% | "
                    f"¥{item['price']:.3f} | "
                    f"¥{daily_return:+,.2f} | "
                    f"{item.get('current_positions', 0)}/{item.get('total_positions', 10)} |"
                )
            lines.append("")

        # 建议买入
        if buy_list:
            lines.append("## 🟢 建议买入\n")
            lines.append("| ETF名称 | 操作 | 基金名称 | 代码 | 涨跌 | 价格 | 建议仓位 |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")

            for item in buy_list[:10]:  # 最多显示10个
                lines.append(
                    f"| {item['name']} | "
                    f"买入{item['suggested_positions']}份 | "
                    f"{item['fund_name']} | "
                    f"`{item['code']}` | "
                    f"{item['change_pct']}% | "
                    f"¥{item['price']:.3f} | "
                    f"{item.get('total_positions', 10)}份 |"
                )
            lines.append("")

        # 建议持有
        if hold_list:
            lines.append("## 🟡 建议持有\n")
            lines.append("| ETF名称 | 基金名称 | 代码 | 涨跌 | 价格 | 今日收益 | 仓位 |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")

            for item in hold_list[:5]:  # 最多显示5个
                daily_return = item.get('daily_return', 0)
                lines.append(
                    f"| {item['name']} | "
                    f"{item['fund_name']} | "
                    f"`{item['code']}` | "
                    f"{item['change_pct']}% | "
                    f"¥{item['price']:.3f} | "
                    f"¥{daily_return:+,.2f} | "
                    f"{item.get('current_positions', 0)}/{item.get('total_positions', 10)} |"
                )
            lines.append("")

        lines.append("---\n")
        lines.append("💡 *以上建议仅供参考，投资需谨慎*")

        return "\n".join(lines)

    def _calculate_stats(self) -> Dict:
        """计算统计数据（使用实际持仓数据）"""
        etfs = self.watchlist.get('etfs', [])

        total_positions = 0  # 昨日总仓位（实际持仓）
        total_capital = 0  # 昨日总资金（实际持仓 × 200元/仓）
        total_return = 0  # 今日总收益
        active_etf_count = 0  # 有持仓的ETF数量

        for etf in etfs:
            code = etf['code']
            if code not in self.etf_data:
                continue

            data = self.etf_data[code]

            # 使用实际持仓数据（从API获取）
            previous_positions_used = data.get('previous_positions_used', 0)

            # 只统计有持仓的ETF
            if previous_positions_used > 0:
                active_etf_count += 1

                # 每仓200元
                investment = previous_positions_used * 200

                total_positions += previous_positions_used
                total_capital += investment

                # 使用API返回的daily_profit（如果有的话）
                daily_profit = data.get('daily_profit', 0)
                if daily_profit == 0:
                    # 如果API没有返回，手动计算
                    pct_chg = data.get('pct_chg') or 0
                    daily_profit = investment * (pct_chg / 100)

                total_return += daily_profit

        return {
            'total_positions': total_positions,
            'total_capital': total_capital,
            'total_return': total_return,
            'active_etf_count': active_etf_count
        }

    def _get_buy_list(self) -> List[Dict]:
        """获取建议买入列表"""
        buy_list = []
        etfs = self.watchlist.get('etfs', [])

        for etf in etfs:
            code = etf['code']
            if code not in self.etf_data:
                continue

            data = self.etf_data[code]

            # 简单的买入信号判断
            # 这里应该从策略信号获取，暂时用涨跌判断
            if data['pct_chg'] and data['pct_chg'] < -1:  # 跌幅超过1%建议买入
                buy_list.append({
                    'name': etf.get('sector', etf['name']),
                    'code': code,
                    'fund_name': data['name'],
                    'price': data['close'],
                    'change_pct': f"{data['pct_chg']:.2f}",
                    'suggested_positions': etf.get('total_positions', 10),
                    'total_positions': etf.get('total_positions', 10),
                    'current_positions': 0  # 假设新建仓位
                })

        return buy_list

    def _get_sell_list(self) -> List[Dict]:
        """获取建议卖出列表"""
        sell_list = []
        etfs = self.watchlist.get('etfs', [])

        for etf in etfs:
            code = etf['code']
            if code not in self.etf_data:
                continue

            data = self.etf_data[code]

            # 简单的卖出信号判断
            if data['pct_chg'] and data['pct_chg'] > 1:  # 涨幅超过1%建议卖出
                position_value = etf.get('position_value', 2000)
                pct_chg = data['pct_chg']
                daily_return = position_value * pct_chg / 100

                sell_list.append({
                    'name': etf.get('sector', etf['name']),
                    'code': code,
                    'fund_name': data['name'],
                    'price': data['close'],
                    'change_pct': f"{pct_chg:.2f}",
                    'suggested_positions': etf.get('total_positions', 10),
                    'daily_return': daily_return,
                    'total_positions': etf.get('total_positions', 10),
                    'current_positions': etf.get('total_positions', 10)
                })

        return sorted(sell_list, key=lambda x: x['daily_return'], reverse=True)

    def _get_hold_list(self) -> List[Dict]:
        """获取建议持有列表"""
        hold_list = []
        etfs = self.watchlist.get('etfs', [])

        for etf in etfs:
            code = etf['code']
            if code not in self.etf_data:
                continue

            data = self.etf_data[code]

            # 持有信号：涨跌幅在-1%到1%之间
            if data['pct_chg'] and -1 <= data['pct_chg'] <= 1:
                position_value = etf.get('position_value', 2000)
                pct_chg = data['pct_chg']
                daily_return = position_value * pct_chg / 100

                hold_list.append({
                    'name': etf.get('sector', etf['name']),
                    'code': code,
                    'fund_name': data['name'],
                    'price': data['close'],
                    'change_pct': f"{pct_chg:.2f}",
                    'daily_return': daily_return,
                    'total_positions': etf.get('total_positions', 10),
                    'current_positions': etf.get('total_positions', 10)
                })

        return hold_list


def generate_etf_operation_report() -> Optional[str]:
    """生成ETF操作建议报告

    Returns:
        Markdown格式的报告文本
    """
    report = ETFOperationReport()

    if not report.load_data():
        return None

    return report.generate_markdown_report()
