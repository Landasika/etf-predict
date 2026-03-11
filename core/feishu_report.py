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

        # 获取ETF数据
        etfs = self.watchlist.get('etfs', [])
        for etf in etfs:
            code = etf['code']
            name = etf['name']
            strategy = etf.get('strategy', 'macd_aggressive')

            # 获取最新行情数据
            conn = get_etf_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT close, pct_chg, trade_date
                    FROM etf_daily
                    WHERE ts_code = ?
                    ORDER BY trade_date DESC
                    LIMIT 2
                """, (code,))
                results = cursor.fetchall()
                conn.close()

                if len(results) >= 1:
                    current = results[0]
                    prev = results[1] if len(results) > 1 else None

                    self.etf_data[code] = {
                        'name': name,
                        'close': current[0],
                        'pct_chg': current[1],
                        'trade_date': current[2],
                        'prev_close': prev[0] if prev else None
                    }

        return True

    def generate_markdown_report(self) -> str:
        """生成Markdown格式的报告"""
        lines = []

        # 标题
        lines.append("# 🎯 ETF 操作建议")
        lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 持仓统计
        lines.append("## 📊 持仓统计\n")
        lines.append("| 项目 | 数值 |")
        lines.append("| --- | --- |")

        stats = self._calculate_stats()
        lines.append(f"| 昨日总仓位 | {stats.get('total_positions', 0)}仓 |")
        lines.append(f"| 昨日总资金 | ¥{stats.get('total_capital', 0):,.0f} |")
        lines.append(f"| 今日总收益 | ¥{stats.get('total_return', 0):+,.2f} |\n")

        # 分类显示操作建议
        buy_list = self._get_buy_list()
        sell_list = self._get_sell_list()
        hold_list = self._get_hold_list()

        # 建议买入
        if buy_list:
            lines.append("## 🟢 建议买入\n")
            lines.append("| ETF名称 | 操作 | 基金名称 | 代码 | 涨跌 | 价格 | 仓位 |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")

            for item in buy_list[:10]:  # 最多显示10个
                lines.append(
                    f"| {item['name']} | "
                    f"买入{item['suggested_positions']}份 | "
                    f"{item['fund_name']} | "
                    f"`{item['code']}` | "
                    f"{item['change_pct']}% | "
                    f"¥{item['price']:.3f} | "
                    f"{item.get('current_positions', 0)}/{item.get('total_positions', 10)} |"
                )
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
        """计算统计数据"""
        etfs = self.watchlist.get('etfs', [])

        total_positions = 0
        total_capital = 0
        total_return = 0

        for etf in etfs:
            code = etf['code']
            if code not in self.etf_data:
                continue

            data = self.etf_data[code]
            total_positions += etf.get('total_positions', 10)
            total_capital += etf.get('position_value', 2000)

            # 计算当日收益
            pct_chg = data['pct_chg'] or 0
            position_value = etf.get('position_value', 2000)
            daily_return = position_value * pct_chg / 100
            total_return += daily_return

        return {
            'total_positions': total_positions,
            'total_capital': total_capital,
            'total_return': total_return
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
