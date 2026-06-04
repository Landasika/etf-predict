"""Nightly Feishu review report generation."""
from datetime import datetime

from core.position_signal_service import build_feishu_operation_rows


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return default


def _format_money(value: float) -> str:
    return f"¥{value:+,.2f}"


def _format_params(params: dict | None) -> str:
    params = params or {}
    values = [
        params.get("macd_fast", "-"),
        params.get("macd_slow", "-"),
        params.get("macd_signal", "-"),
    ]
    return "/".join(str(value) for value in values)


def _operation_sort_key(row: dict) -> tuple[int, int, str]:
    action = _safe_int(row.get("today_action_count", 0))
    if action < 0:
        return (0, -abs(action), str(row.get("code", "")))
    if action > 0:
        return (1, -abs(action), str(row.get("code", "")))
    return (2, 0, str(row.get("code", "")))


def _load_rows() -> tuple[str, list[dict]]:
    result = build_feishu_operation_rows()
    if not result.get("success"):
        return result.get("data_date", ""), []

    rows = result.get("data") or []
    if not isinstance(rows, list):
        return result.get("data_date", ""), []

    return result.get("data_date", ""), rows


def generate_nightly_review_report(optimization_status: dict | None = None) -> str:
    """Generate the 23:00 nightly review report for Feishu."""
    optimization_status = optimization_status or {}
    data_date, rows = _load_rows()
    buy_rows = [row for row in rows if _safe_int(row.get("today_action_count")) > 0]
    sell_rows = [row for row in rows if _safe_int(row.get("today_action_count")) < 0]
    hold_rows = [row for row in rows if _safe_int(row.get("today_action_count")) == 0]
    focus_rows = sorted(buy_rows + sell_rows, key=_operation_sort_key)

    total_daily_profit = sum(_safe_float(row.get("daily_profit")) for row in rows)
    total_previous_positions = sum(_safe_int(row.get("previous_positions_used")) for row in rows)
    total_target_positions = sum(_safe_int(row.get("positions_used")) for row in rows)
    total_buy_positions = sum(_safe_int(row.get("today_action_count")) for row in buy_rows)
    total_sell_positions = sum(abs(_safe_int(row.get("today_action_count"))) for row in sell_rows)

    lines = [
        "# 🌙 ETF 夜间复盘",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    if data_date:
        lines.append(f"**数据日期**: {data_date}")
    lines.append("")

    lines.extend([
        "## 📊 今日复盘",
        "",
        "| 项目 | 数值 | 说明 |",
        "| --- | --- | --- |",
        f"| 今日总收益 | {_format_money(total_daily_profit)} | 按昨日仓位计算 |",
        f"| 昨日总仓位 | {total_previous_positions}仓 | 今日盈亏计算仓位 |",
        f"| 今日目标仓位 | {total_target_positions}仓 | 今日信号目标 |",
        f"| 卖出 | {len(sell_rows)}个 | 共{total_sell_positions}仓 |",
        f"| 买入 | {len(buy_rows)}个 | 共{total_buy_positions}仓 |",
        f"| 持有 | {len(hold_rows)}个 | 仓位不变 |",
        "",
    ])

    lines.extend([
        "## 🔧 参数更新",
        "",
        "| 项目 | 数值 |",
        "| --- | --- |",
        f"| 优化结果 | {optimization_status.get('last_result') or '未执行'} |",
        f"| 成功/总数 | {_safe_int(optimization_status.get('completed_etfs'))}/{_safe_int(optimization_status.get('total_etfs'))} |",
        f"| 失败 | {_safe_int(optimization_status.get('failed_etfs'))} |",
        "",
    ])

    changed_params = optimization_status.get("changed_params") or []
    if changed_params:
        lines.extend([
            "| ETF | 代码 | MACD参数 | 优化收益 |",
            "| --- | --- | --- | --- |",
        ])
        for item in changed_params[:20]:
            old_text = _format_params(item.get("old_params"))
            new_text = _format_params(item.get("new_params"))
            return_pct = _safe_float(item.get("return_pct"))
            lines.append(
                f"| {item.get('name') or item.get('code')} | "
                f"`{item.get('code', '')}` | "
                f"{old_text} -> {new_text} | "
                f"{return_pct:.2f}% |"
            )
        lines.append("")
    else:
        lines.extend(["参数无变化", ""])

    lines.extend(["## 🔭 明日重点关注", ""])
    if focus_rows:
        lines.extend([
            "| ETF | 操作 | 仓位 | 涨跌 | 今日收益 |",
            "| --- | --- | --- | --- | --- |",
        ])
        for row in focus_rows[:12]:
            previous_positions = _safe_int(row.get("previous_positions_used"))
            target_positions = _safe_int(row.get("positions_used"))
            lines.append(
                f"| {row.get('name') or row.get('code')} | "
                f"{row.get('today_operation') or '持有'} | "
                f"{previous_positions}->{target_positions} | "
                f"{_safe_float(row.get('pct_chg')):.2f}% | "
                f"{_format_money(_safe_float(row.get('daily_profit')))} |"
            )
    else:
        lines.append("今日无调仓建议")

    lines.extend(["", "---", "💡 *夜间复盘用于收盘后校准参数和明日关注，不替代盘中操作纪律*"])
    return "\n".join(lines)
