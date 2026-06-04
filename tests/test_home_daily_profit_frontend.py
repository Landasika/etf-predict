from pathlib import Path
import subprocess
import textwrap


ROOT = Path(__file__).resolve().parents[1]
HOME_JS = ROOT / "static" / "js" / "home.js"
INDEX_HTML = ROOT / "templates" / "index.html"
HOME_CSS = ROOT / "static" / "css" / "home.css"


def _function_body(source: str, name: str) -> str:
    marker = f"function {name}"
    assert marker in source
    return source.split(marker, 1)[1].split("\nfunction ", 1)[0]


def _function_source(source: str, name: str) -> str:
    marker = f"function {name}"
    start = source.index(marker)
    brace_start = source.index("{", start)
    depth = 0
    for index in range(brace_start, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError(f"Could not extract function {name}")


def _run_node(script: str) -> str:
    result = subprocess.run(
        ["node", "-e", script],
        check=True,
        text=True,
        capture_output=True,
        cwd=ROOT,
    )
    return result.stdout


def _position_grid_helper_script(assertions: str) -> str:
    source = HOME_JS.read_text(encoding="utf-8")
    functions = [
        "clampSlotValue",
        "escapeHtml",
        "getValidPositionGridItems",
        "getStrategySlotMovement",
        "sortPositionGridItems",
        "renderSlotSegments",
    ]
    helpers = "\n\n".join(_function_source(source, name) for name in functions)
    return helpers + "\n\n" + textwrap.dedent(assertions)


def test_homepage_replaces_daily_profit_panel_with_position_grid():
    source = INDEX_HTML.read_text(encoding="utf-8")

    assert 'class="strategy-overview-section"' in source
    assert 'data-strategy-tab="grid"' in source
    assert 'data-strategy-tab="table"' in source
    assert 'data-strategy-panel="grid"' in source
    assert 'data-strategy-panel="table"' in source
    assert 'id="positionGridPanel"' in source
    assert 'id="positionGridCards"' in source
    assert 'id="dailyProfitPanel"' not in source
    assert "昨日策略仓位" in source
    assert "今日策略仓位" in source
    assert "总当日盈亏" in source
    assert 'id="positionGridDailyProfitTotal"' in source
    assert "当日盈亏" in source
    assert "本月盈亏" in source


def test_homepage_does_not_expose_scheduler_settings_controls():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = HOME_JS.read_text(encoding="utf-8")

    assert "schedulerSettingsModal" not in html
    assert "schedulerSettingsBtn" not in html
    assert "showSchedulerSettings" not in source
    assert "hideSchedulerSettings" not in source
    assert "loadSchedulerSettings" not in source
    assert "saveSchedulerSettings" not in source
    assert "/api/macd/optimization/schedule/configure" not in source


def test_homepage_does_not_expose_macd_optimization_controls():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = HOME_JS.read_text(encoding="utf-8")

    assert "optimizeAllBtn" not in html
    assert "optimizeAllBtn" not in source
    assert "optimizeAllMACDParams" not in source
    assert "/api/macd/optimize-params" not in source
    assert "/api/watchlist/${etf.code}/macd-params" not in source


def test_homepage_uses_backend_slot_value_for_amount_display():
    source = HOME_JS.read_text(encoding="utf-8")

    assert "getPositionSlotValue" in source
    assert "* 200" not in source
    assert "每仓200元" not in source


def test_strategy_overview_tabs_default_to_grid_and_can_switch():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = HOME_JS.read_text(encoding="utf-8")

    assert 'data-strategy-tab="grid" class="strategy-tab active"' in html
    assert 'data-strategy-panel="grid" class="strategy-tab-panel active"' in html
    assert 'data-strategy-panel="table" class="strategy-tab-panel"' in html

    assert "setupStrategyOverviewTabs()" in source
    assert "function setupStrategyOverviewTabs()" in source
    assert "data-strategy-tab" in source
    assert "data-strategy-panel" in source
    assert "classList.toggle('active'" in source


def test_load_batch_signals_renders_position_grid_instead_of_daily_profit():
    source = HOME_JS.read_text(encoding="utf-8")
    body = _function_body(source, "loadBatchSignals")

    assert "renderPositionGrid(strategyData)" in body
    assert "updateDailyProfit(strategyData)" not in body


def test_position_grid_delta_uses_strategy_slots_not_today_action_count():
    source = HOME_JS.read_text(encoding="utf-8")
    body = _function_body(source, "getStrategySlotMovement")

    assert "latest_data" in body
    assert "previous_positions_used" in body
    assert "positions_used" in body
    assert "today_action_count" not in body


def test_advice_modal_uses_backend_previous_positions_for_today_operation():
    source = HOME_JS.read_text(encoding="utf-8")
    body = _function_body(source, "loadAdvice")

    assert "previous_positions_used: etf.previous_positions_used ?? etf.db_position ?? 0" in body
    assert "previous_positions_used: etf.latest_data?.previous_positions_used || 0" not in body


def test_advice_modal_uses_loaded_strategy_data_not_a_second_batch_request():
    source = HOME_JS.read_text(encoding="utf-8")
    body = _function_body(source, "loadAdvice")

    assert "let signals = getValidPositionGridItems(strategyData)" in body
    assert "fetch('/api/watchlist/batch-signals')" not in body


def test_advice_modal_uses_backend_operation_and_actual_holdings():
    source = HOME_JS.read_text(encoding="utf-8")
    body = _function_body(source, "loadAdvice")

    assert "etf.today_operation ||" in body
    assert "const currentPosition = formattedSignals.filter(s => s.db_position > 0)" in body
    assert "positions_used > 0" not in body


def test_advice_modal_does_not_duplicate_backend_today_operation_as_strategy_changes():
    source = HOME_JS.read_text(encoding="utf-8")
    body = _function_body(source, "loadAdvice")

    assert "strategy_delta" not in body
    assert "今日策略变化" not in body
    assert "当前实际持仓已与策略目标一致，无待执行调仓" not in body
    assert "今日信号目标与昨日持仓一致，无需调仓" in body


def test_position_grid_sort_prioritizes_add_reduce_then_hold():
    source = HOME_JS.read_text(encoding="utf-8")
    body = _function_body(source, "sortPositionGridItems")

    assert "groupRank" in body
    assert "delta > 0" in body
    assert "delta < 0" in body
    assert "targetSlots" in body


def test_position_grid_renders_slot_segment_states():
    source = HOME_JS.read_text(encoding="utf-8")
    body = _function_body(source, "renderSlotSegments")

    assert "position-slot-segment keep" in body
    assert "position-slot-segment add" in body
    assert "position-slot-segment reduce" in body
    assert "position-slot-segment empty" in body


def test_position_grid_escapes_card_text_and_attributes():
    source = HOME_JS.read_text(encoding="utf-8")
    escape_body = _function_body(source, "escapeHtml")
    render_body = _function_body(source, "renderPositionGrid")

    assert "String(value ?? '')" in escape_body
    assert ".replace(/&/g, '&amp;')" in escape_body
    assert ".replace(/</g, '&lt;')" in escape_body
    assert ".replace(/>/g, '&gt;')" in escape_body
    assert ".replace(/\"/g, '&quot;')" in escape_body
    assert ".replace(/'/g, '&#39;')" in escape_body

    assert "safeName" in render_body
    assert "safeCode" in render_body
    assert "safeSignal" in render_body
    assert "safeSignalStrength" in render_body
    assert "safeMacdText" in render_body
    assert "safeKdjText" in render_body
    assert "safeReason" in render_body
    assert "safeAriaLabel" in render_body
    assert "safeRemark" in render_body
    assert "position-card-remark" in render_body
    assert "基金名称：" not in render_body


def test_strategy_overview_displays_daily_and_monthly_profit():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = HOME_JS.read_text(encoding="utf-8")
    grid_body = _function_body(source, "renderPositionGrid")
    table_body = _function_body(source, "renderStrategyTable")

    assert "<th>当日盈亏</th>" in html
    assert "<th>本月盈亏</th>" in html
    assert 'td colspan="16"' in html

    assert "daily_profit" in grid_body
    assert "monthly_profit" in grid_body
    assert "当日盈亏" in grid_body
    assert "本月盈亏" in grid_body
    assert "formatMoney" in grid_body

    assert "daily_profit" in table_body
    assert "monthly_profit" in table_body
    assert "formatMoney" in table_body


def test_position_grid_displays_total_daily_profit_summary():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = HOME_JS.read_text(encoding="utf-8")
    grid_body = _function_body(source, "renderPositionGrid")

    assert "总当日盈亏" in html
    assert "总本月盈亏" in html
    assert 'id="positionGridDailyProfitTotal"' in html
    assert 'id="positionGridMonthlyProfitTotal"' in html

    assert "dailyProfitTotalEl" in grid_body
    assert "monthlyProfitTotalEl" in grid_body
    assert "totalDailyProfit" in grid_body
    assert "totalMonthlyProfit" in grid_body
    assert "daily_profit" in grid_body
    assert "monthly_profit" in grid_body
    assert "positionGridDailyProfitTotal" in grid_body
    assert "positionGridMonthlyProfitTotal" in grid_body


def test_strategy_profit_colors_use_red_for_gain_green_for_loss():
    css = HOME_CSS.read_text(encoding="utf-8")
    source = HOME_JS.read_text(encoding="utf-8")
    grid_body = _function_body(source, "renderPositionGrid")
    table_body = _function_body(source, "renderStrategyTable")

    assert ".profit-positive" in css
    assert "color: #dc2626" in css
    assert ".profit-negative" in css
    assert "color: #059669" in css

    assert "dailyChangeClass = getProfitClass(dailyChange)" in grid_body
    assert "dailyProfitClass = getProfitClass(dailyProfit)" in grid_body
    assert 'class="${dailyChangeClass}"' in grid_body
    assert 'class="${dailyProfitClass}"' in grid_body
    assert "getProfitClass(item.daily_change_pct || 0)" in table_body
    assert "getProfitClass(dailyProfit)" in table_body


def test_position_grid_uses_three_columns_and_shows_strategy_params():
    css = HOME_CSS.read_text(encoding="utf-8")
    source = HOME_JS.read_text(encoding="utf-8")
    grid_body = _function_body(source, "renderPositionGrid")

    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css

    assert "strategyText" in grid_body
    assert "macdParamsText" in grid_body
    assert "getShortStrategyName(item.strategy)" in grid_body
    assert "getPositionGridMacdParamsText(item)" in grid_body
    assert "策略 <b>${safeStrategyText}</b>" in grid_body
    assert "MACD参数 <b>${safeMacdParamsText}</b>" in grid_body


def test_position_grid_summary_uses_two_rows_of_three_metrics():
    css = HOME_CSS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in css
    assert html.count('class="position-grid-metric') == 6


def test_position_grid_filters_invalid_items_before_sorting():
    source = HOME_JS.read_text(encoding="utf-8")
    helper_body = _function_body(source, "getValidPositionGridItems")
    render_body = _function_body(source, "renderPositionGrid")

    assert "Array.isArray(data)" in helper_body
    assert "item && typeof item === 'object'" in helper_body
    assert "getValidPositionGridItems(data)" in render_body
    assert "sortPositionGridItems(validItems)" in render_body


def test_position_grid_total_positions_nonpositive_defaults_to_ten():
    source = HOME_JS.read_text(encoding="utf-8")
    body = _function_body(source, "getStrategySlotMovement")

    assert "rawTotalSlots" in body
    assert "rawTotalSlots > 0 ? rawTotalSlots : 10" in body


def test_position_grid_helpers_execute_escaping_and_slot_defaults():
    script = _position_grid_helper_script(
        r"""
        const assert = require('assert');

        assert.strictEqual(
            escapeHtml(`"><img src=x onerror=alert(1)> & 'bad'`),
            '&quot;&gt;&lt;img src=x onerror=alert(1)&gt; &amp; &#39;bad&#39;'
        );

        assert.deepStrictEqual(getValidPositionGridItems([null, 0, 'x', { code: 'A' }]), [{ code: 'A' }]);

        const movement = getStrategySlotMovement({
            total_positions: 0,
            positions_used: 12,
            latest_data: { previous_positions_used: 7 }
        });
        assert.deepStrictEqual(movement, {
            previousSlots: 7,
            targetSlots: 10,
            totalSlots: 10,
            delta: 3
        });

        assert.deepStrictEqual(getStrategySlotMovement(null), {
            previousSlots: 0,
            targetSlots: 0,
            totalSlots: 10,
            delta: 0
        });
        """
    )

    _run_node(script)


def test_position_grid_helpers_execute_sorting_and_slot_segments():
    script = _position_grid_helper_script(
        r"""
        const assert = require('assert');

        const sorted = sortPositionGridItems([
            { code: 'HOLD_HIGH', total_positions: 10, positions_used: 8, latest_data: { previous_positions_used: 8 } },
            { code: 'ADD_SMALL', total_positions: 10, positions_used: 4, latest_data: { previous_positions_used: 3 } },
            { code: 'REDUCE_BIG', total_positions: 10, positions_used: 1, latest_data: { previous_positions_used: 6 } },
            { code: 'ADD_BIG', total_positions: 10, positions_used: 8, latest_data: { previous_positions_used: 3 } },
            { code: 'HOLD_LOW', total_positions: 10, positions_used: 2, latest_data: { previous_positions_used: 2 } },
            { code: 'REDUCE_SMALL', total_positions: 10, positions_used: 4, latest_data: { previous_positions_used: 6 } }
        ]).map(item => item.code);

        assert.deepStrictEqual(sorted, [
            'ADD_BIG',
            'ADD_SMALL',
            'REDUCE_BIG',
            'REDUCE_SMALL',
            'HOLD_HIGH',
            'HOLD_LOW'
        ]);

        const addSlots = renderSlotSegments(2, 5, 6);
        assert.strictEqual((addSlots.match(/position-slot-segment keep/g) || []).length, 2);
        assert.strictEqual((addSlots.match(/position-slot-segment add/g) || []).length, 3);
        assert.strictEqual((addSlots.match(/position-slot-segment empty/g) || []).length, 1);

        const reduceSlots = renderSlotSegments(5, 2, 6);
        assert.strictEqual((reduceSlots.match(/position-slot-segment keep/g) || []).length, 2);
        assert.strictEqual((reduceSlots.match(/position-slot-segment reduce/g) || []).length, 3);
        assert.strictEqual((reduceSlots.match(/position-slot-segment empty/g) || []).length, 1);
        """
    )

    _run_node(script)
