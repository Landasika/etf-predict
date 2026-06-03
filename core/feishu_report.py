#!/usr/bin/env python3
"""
ETF操作建议报告生成器
生成飞书消息格式的ETF操作建议
"""
from typing import Dict, List, Optional
from datetime import datetime

from core.database import get_etf_connection
from core.watchlist import load_watchlist
from core.position_signal_service import build_feishu_operation_rows
from core.profit_calculator import SLOT_VALUE, calculate_daily_profit


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

        try:
            shared_result = build_feishu_operation_rows()
        except Exception as e:
            print(f"❌ 获取共享信号数据失败: {e}")
            import traceback
            traceback.print_exc()
            return False

        if shared_result and shared_result.get('success') and shared_result.get('data'):
            try:
                self.etf_data = {}
                for row in shared_result.get('data', []):
                    if not isinstance(row, dict):
                        raise ValueError(f"共享信号行格式无效: {row!r}")
                    code = row.get('code')
                    if not code:
                        raise ValueError(f"共享信号行缺少code: {row!r}")
                    self.etf_data[code] = {
                        'name': row.get('name', code),
                        'close': row.get('close', 0),
                        'pct_chg': row.get('pct_chg', 0),
                        'previous_positions_used': row.get('previous_positions_used', 0),
                        'positions_used': row.get('positions_used', 0),
                        'daily_profit': row.get('daily_profit', 0),
                        'today_action_count': row.get('today_action_count', 0),
                        'today_operation': row.get('today_operation', '持有'),
                        'action_reason': row.get('action_reason', ''),
                        'next_action': row.get('next_action', '--'),
                        'signal_type': row.get('signal_type', 'HOLD'),
                        'signal_strength': row.get('signal_strength', 0),
                        'total_positions': row.get('total_positions', 10),
                    }
                if self.etf_data:
                    print(f"✓ 成功获取 {len(self.etf_data)} 个ETF的数据")
                    return True
            except Exception as e:
                print(f"❌ 解析共享信号数据失败: {e}")
                import traceback
                traceback.print_exc()
                return False

        # 如果共享信号数据不可用，使用数据库数据（fallback）
        # 获取ETF数据
        etfs = self.watchlist.get('etfs', [])
        for etf in etfs:
            code = etf['code']
            name = etf['name']

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
        lines.append(f"| 昨日总资金 | ¥{stats.get('total_capital', 0):,.0f} | 持仓总价值（{SLOT_VALUE}元/仓）|")
        lines.append(f"| 今日总收益 | ¥{stats.get('total_return', 0):+,.2f} | 当日浮动盈亏 |\n")

        # 今日操作建议总结
        lines.append("## 📋 今日操作建议\n")
        lines.append("| 操作类型 | 数量 | 说明 |")
        lines.append("| --- | --- | --- |")

        if sell_list:
            total_sell_positions = sum(item.get('suggested_positions', 0) for item in sell_list)
            lines.append(f"| 🔴 卖出 | {len(sell_list)}个 | 共{total_sell_positions}仓 |")
        else:
            lines.append("| 🔴 卖出 | 0个 | 暂无卖出建议 |")

        if buy_list:
            total_buy_positions = sum(item.get('suggested_positions', 0) for item in buy_list)
            lines.append(f"| 🟢 买入 | {len(buy_list)}个 | 共{total_buy_positions}仓 |")
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
            lines.append("| ETF名称 | 操作 | 基金名称 | 代码 | 涨跌 | 价格 | 今日收益 | 仓位(昨->今) |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")

            for item in sell_list[:10]:  # 最多显示10个
                daily_return = item.get('daily_return', 0)
                lines.append(
                    f"| {item['name']} | "
                    f"卖出{item['suggested_positions']}仓 | "
                    f"{item['fund_name']} | "
                    f"`{item['code']}` | "
                    f"{item['change_pct']}% | "
                    f"¥{item['price']:.3f} | "
                    f"¥{daily_return:+,.2f} | "
                    f"{item.get('previous_positions', 0)}->{item.get('current_positions', 0)}/{item.get('total_positions', 10)} |"
                )
            lines.append("")

        # 建议买入
        if buy_list:
            lines.append("## 🟢 建议买入\n")
            lines.append("| ETF名称 | 操作 | 基金名称 | 代码 | 涨跌 | 价格 | 仓位(昨->今) |")
            lines.append("| --- | --- | --- | --- | --- | --- | --- |")

            for item in buy_list[:10]:  # 最多显示10个
                lines.append(
                    f"| {item['name']} | "
                    f"买入{item['suggested_positions']}仓 | "
                    f"{item['fund_name']} | "
                    f"`{item['code']}` | "
                    f"{item['change_pct']}% | "
                    f"¥{item['price']:.3f} | "
                    f"{item.get('previous_positions', 0)}->{item.get('current_positions', 0)}/{item.get('total_positions', 10)} |"
                )
            lines.append("")

        # 建议持有
        if hold_list:
            lines.append("## 🟡 建议持有\n")
            lines.append("| ETF名称 | 基金名称 | 代码 | 涨跌 | 价格 | 今日收益 | 仓位(昨->今) |")
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
                    f"{item.get('previous_positions', 0)}->{item.get('current_positions', 0)}/{item.get('total_positions', 10)} |"
                )
            lines.append("")

        lines.append("---\n")
        lines.append("💡 *以上建议仅供参考，投资需谨慎*")

        return "\n".join(lines)

    def _calculate_stats(self) -> Dict:
        """计算统计数据（使用实际持仓数据）"""
        etfs = self.watchlist.get('etfs', [])

        total_positions = 0  # 昨日总仓位（实际持仓）
        total_capital = 0  # 昨日总资金（实际持仓 × 每仓资金）
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

                investment = previous_positions_used * SLOT_VALUE

                total_positions += previous_positions_used
                total_capital += investment

                # 使用API返回的daily_profit（如果有的话）
                daily_profit = data.get('daily_profit', 0)
                if daily_profit == 0:
                    pct_chg = data.get('pct_chg') or 0
                    daily_profit = calculate_daily_profit(previous_positions_used, pct_chg)

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

            if data.get('today_action_count', 0) > 0:
                buy_list.append({
                    'name': etf.get('sector', etf['name']),
                    'code': code,
                    'fund_name': data['name'],
                    'price': data['close'],
                    'change_pct': f"{data['pct_chg']:.2f}",
                    'suggested_positions': abs(data.get('today_action_count', 0)),
                    'previous_positions': data.get('previous_positions_used', 0),
                    'total_positions': data.get('total_positions', etf.get('total_positions', 10)),
                    'current_positions': data.get('positions_used', 0),
                    'action_reason': data.get('action_reason', ''),
                    'next_action': data.get('next_action', '--')
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

            if data.get('today_action_count', 0) < 0:
                sell_list.append({
                    'name': etf.get('sector', etf['name']),
                    'code': code,
                    'fund_name': data['name'],
                    'price': data['close'],
                    'change_pct': f"{data['pct_chg']:.2f}",
                    'suggested_positions': abs(data.get('today_action_count', 0)),
                    'daily_return': data.get('daily_profit', 0),
                    'previous_positions': data.get('previous_positions_used', 0),
                    'total_positions': data.get('total_positions', etf.get('total_positions', 10)),
                    'current_positions': data.get('positions_used', 0),
                    'action_reason': data.get('action_reason', ''),
                    'next_action': data.get('next_action', '--')
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

            if data.get('today_action_count', 0) == 0:
                hold_list.append({
                    'name': etf.get('sector', etf['name']),
                    'code': code,
                    'fund_name': data['name'],
                    'price': data['close'],
                    'change_pct': f"{data['pct_chg']:.2f}",
                    'daily_return': data.get('daily_profit', 0),
                    'previous_positions': data.get('previous_positions_used', 0),
                    'total_positions': data.get('total_positions', etf.get('total_positions', 10)),
                    'current_positions': data.get('positions_used', 0),
                    'action_reason': data.get('action_reason', ''),
                    'next_action': data.get('next_action', '--')
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
