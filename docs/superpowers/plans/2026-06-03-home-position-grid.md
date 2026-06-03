# Home Position Grid Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the homepage standalone daily-profit panel with a position-card wall that shows yesterday strategy slots to today strategy slots for every watchlist ETF.

**Architecture:** Keep the existing FastAPI/Jinja/static-JS homepage. Reuse `/api/watchlist/batch-signals`; compute the grid view model in `static/js/home.js` from `latest_data.previous_positions_used` and `positions_used`, then render into a new container in `templates/index.html`. Styling lives in `static/css/home.css`.

**Tech Stack:** FastAPI, Jinja templates, plain JavaScript, CSS, pytest text/behavior checks.

---

## File Map

- Modify `templates/index.html`: replace the `dailyProfitPanel` section with a `positionGridPanel` section before the strategy table.
- Modify `static/js/home.js`: call `renderPositionGrid(strategyData)` from `loadBatchSignals()`, add grid helper/render functions, and remove the standalone `updateDailyProfit(strategyData)` call from the load success path.
- Modify `static/css/home.css`: add summary strip, card wall, slot segment, delta badge, empty/error state, and responsive rules.
- Modify `tests/test_home_daily_profit_frontend.py`: convert the old daily-profit-panel assertions into position-grid assertions.

## Task 1: Update Homepage Tests For Position Grid Contract

**Files:**
- Modify: `tests/test_home_daily_profit_frontend.py`

- [ ] **Step 1: Replace the old daily profit tests**

Replace the entire file with:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOME_JS = ROOT / "static" / "js" / "home.js"
INDEX_HTML = ROOT / "templates" / "index.html"


def _function_body(source: str, name: str) -> str:
    marker = f"function {name}"
    assert marker in source
    return source.split(marker, 1)[1].split("\nfunction ", 1)[0]


def test_homepage_replaces_daily_profit_panel_with_position_grid():
    source = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="positionGridPanel"' in source
    assert 'id="positionGridCards"' in source
    assert 'id="dailyProfitPanel"' not in source
    assert "昨日策略仓位" in source
    assert "今日策略仓位" in source


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
```

- [ ] **Step 2: Run the targeted tests and verify they fail**

Run:

```bash
pytest tests/test_home_daily_profit_frontend.py -q
```

Expected: failures showing `positionGridPanel`, `renderPositionGrid`, and `getStrategySlotMovement` are missing.

## Task 2: Add The Position Grid Container To The Homepage Template

**Files:**
- Modify: `templates/index.html`
- Test: `tests/test_home_daily_profit_frontend.py`

- [ ] **Step 1: Replace the daily profit panel section**

In `templates/index.html`, remove the section with `id="dailyProfitPanel"` and insert this section in the same location, before scheduler status:

```html
            <!-- 持仓格子面板 -->
            <section class="position-grid-panel" id="positionGridPanel">
                <div class="position-grid-header">
                    <div>
                        <h3 class="panel-title">持仓格子</h3>
                        <p class="position-grid-subtitle">昨日策略仓位 → 今日策略仓位，默认按策略建议执行</p>
                    </div>
                    <div class="position-grid-sort-note">排序：加仓最多 → 减仓最多 → 持有不变</div>
                </div>
                <div class="position-grid-summary" id="positionGridSummary">
                    <div class="position-grid-metric">
                        <span>昨日策略仓位</span>
                        <strong id="positionGridPreviousTotal">0 格</strong>
                    </div>
                    <div class="position-grid-metric">
                        <span>今日策略仓位</span>
                        <strong id="positionGridTargetTotal">0 格</strong>
                    </div>
                    <div class="position-grid-metric add">
                        <span>建议加仓</span>
                        <strong id="positionGridAddTotal">+0 格</strong>
                    </div>
                    <div class="position-grid-metric reduce">
                        <span>建议减仓</span>
                        <strong id="positionGridReduceTotal">-0 格</strong>
                    </div>
                </div>
                <div class="position-grid-cards" id="positionGridCards">
                    <div class="position-grid-empty">正在加载持仓格子...</div>
                </div>
            </section>
```

- [ ] **Step 2: Run the template-focused test**

Run:

```bash
pytest tests/test_home_daily_profit_frontend.py::test_homepage_replaces_daily_profit_panel_with_position_grid -q
```

Expected: PASS.

## Task 3: Implement Position Grid Rendering In Homepage JavaScript

**Files:**
- Modify: `static/js/home.js`
- Test: `tests/test_home_daily_profit_frontend.py`

- [ ] **Step 1: Update the data load success path**

In `loadBatchSignals()`, replace:

```javascript
            renderStrategyTable(strategyData);
            updateStats(strategyData);
            updateDailyProfit(strategyData);  // 更新今日收益
            updateLastUpdated();
```

with:

```javascript
            renderPositionGrid(strategyData);
            renderStrategyTable(strategyData);
            updateStats(strategyData);
            updateLastUpdated();
```

- [ ] **Step 2: Add position grid helper functions before `renderStrategyTable`**

Insert this code after `loadBatchSignals()` and before `renderStrategyTable(data)`:

```javascript
function clampSlotValue(value, fallback = 0) {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) {
        return fallback;
    }
    return Math.max(0, Math.trunc(numberValue));
}

function getStrategySlotMovement(item) {
    const latestData = item.latest_data || {};
    const totalSlots = Math.max(1, clampSlotValue(item.total_positions, 10));
    const previousSlots = Math.min(
        clampSlotValue(latestData.previous_positions_used, 0),
        totalSlots
    );
    const targetSlots = Math.min(
        clampSlotValue(item.positions_used, 0),
        totalSlots
    );

    return {
        previousSlots,
        targetSlots,
        totalSlots,
        delta: targetSlots - previousSlots
    };
}

function sortPositionGridItems(data) {
    return [...data].sort((a, b) => {
        const aMove = getStrategySlotMovement(a);
        const bMove = getStrategySlotMovement(b);
        const groupRank = (move) => {
            if (move.delta > 0) return 0;
            if (move.delta < 0) return 1;
            return 2;
        };

        const rankDiff = groupRank(aMove) - groupRank(bMove);
        if (rankDiff !== 0) return rankDiff;

        if (aMove.delta > 0 && bMove.delta > 0) {
            return bMove.delta - aMove.delta || String(a.code).localeCompare(String(b.code));
        }
        if (aMove.delta < 0 && bMove.delta < 0) {
            return Math.abs(bMove.delta) - Math.abs(aMove.delta) || String(a.code).localeCompare(String(b.code));
        }
        return bMove.targetSlots - aMove.targetSlots || String(a.code).localeCompare(String(b.code));
    });
}

function renderSlotSegments(previousSlots, targetSlots, totalSlots) {
    const keepSlots = Math.min(previousSlots, targetSlots);
    return Array.from({ length: totalSlots }, (_, index) => {
        let className = 'position-slot-segment empty';
        if (index < keepSlots) {
            className = 'position-slot-segment keep';
        } else if (index < targetSlots && targetSlots > previousSlots) {
            className = 'position-slot-segment add';
        } else if (index < previousSlots && previousSlots > targetSlots) {
            className = 'position-slot-segment reduce';
        }
        return `<span class="${className}" aria-hidden="true"></span>`;
    }).join('');
}

function getPositionGridReason(item, delta) {
    const latestData = item.latest_data || {};
    if (item.action_reason) return item.action_reason;
    if (latestData.signal_reason) return latestData.signal_reason;
    if (item.next_action && item.next_action !== '--') return item.next_action;
    if (delta > 0) return '策略建议加仓';
    if (delta < 0) return '策略建议减仓';
    return '保持现有策略仓位';
}

function getPositionGridCardClass(delta) {
    if (delta > 0) return 'position-grid-card add';
    if (delta < 0) return 'position-grid-card reduce';
    return 'position-grid-card hold';
}

function getPositionGridBadge(delta) {
    if (delta > 0) return `<span class="position-delta-badge add">+${delta} 格</span>`;
    if (delta < 0) return `<span class="position-delta-badge reduce">${delta} 格</span>`;
    return '<span class="position-delta-badge hold">不变</span>';
}

function renderPositionGrid(data) {
    const panel = document.getElementById('positionGridPanel');
    const cardsEl = document.getElementById('positionGridCards');
    const previousTotalEl = document.getElementById('positionGridPreviousTotal');
    const targetTotalEl = document.getElementById('positionGridTargetTotal');
    const addTotalEl = document.getElementById('positionGridAddTotal');
    const reduceTotalEl = document.getElementById('positionGridReduceTotal');

    if (!panel || !cardsEl || !previousTotalEl || !targetTotalEl || !addTotalEl || !reduceTotalEl) {
        return;
    }

    if (!Array.isArray(data) || data.length === 0) {
        previousTotalEl.textContent = '0 格';
        targetTotalEl.textContent = '0 格';
        addTotalEl.textContent = '+0 格';
        reduceTotalEl.textContent = '-0 格';
        cardsEl.innerHTML = '<div class="position-grid-empty">暂无数据，请先添加ETF到自选</div>';
        panel.style.display = 'block';
        return;
    }

    const items = sortPositionGridItems(data);
    let previousTotal = 0;
    let targetTotal = 0;
    let addTotal = 0;
    let reduceTotal = 0;

    const cardsHtml = items.map((item) => {
        const movement = getStrategySlotMovement(item);
        previousTotal += movement.previousSlots;
        targetTotal += movement.targetSlots;
        if (movement.delta > 0) addTotal += movement.delta;
        if (movement.delta < 0) reduceTotal += Math.abs(movement.delta);

        const latestData = item.latest_data || {};
        const macd = item.macd || {};
        const kdj = item.kdj || {};
        const signal = item.signal_name || item.signal || '持有';
        const signalStrength = item.signal_strength ?? latestData.signal_strength ?? 0;
        const dailyChange = Number(item.daily_change_pct || 0);
        const dailyChangeText = `${dailyChange >= 0 ? '+' : ''}${dailyChange.toFixed(2)}%`;
        const dailyChangeClass = getProfitClass(dailyChange);
        const macdText = Number.isFinite(Number(macd.hist)) ? `MACD ${Number(macd.hist).toFixed(4)}` : 'MACD --';
        const kdjText = kdj.status || 'KDJ --';
        const reason = getPositionGridReason(item, movement.delta);

        return `
            <article class="${getPositionGridCardClass(movement.delta)}">
                <div class="position-card-head">
                    <div>
                        <div class="position-card-name">${item.name || item.code}</div>
                        <div class="position-card-code">${item.code}</div>
                    </div>
                    ${getPositionGridBadge(movement.delta)}
                </div>
                <div class="position-card-change">
                    <strong>${movement.previousSlots} → ${movement.targetSlots}</strong>
                    <span>昨日策略 → 今日策略</span>
                </div>
                <div class="position-slot-bar" style="--slot-total:${movement.totalSlots}" role="meter" aria-valuemin="0" aria-valuemax="${movement.totalSlots}" aria-valuenow="${movement.targetSlots}" aria-label="${item.code} 今日策略仓位 ${movement.targetSlots} 格">
                    ${renderSlotSegments(movement.previousSlots, movement.targetSlots, movement.totalSlots)}
                </div>
                <div class="position-card-meta">
                    <span>信号 <b>${signal}</b></span>
                    <span>强度 <b>${signalStrength}</b></span>
                    <span>今日涨跌 <b class="${dailyChangeClass}">${dailyChangeText}</b></span>
                    <span><b>${macdText}</b></span>
                    <span><b>${kdjText}</b></span>
                </div>
                <div class="position-card-reason" title="${reason}">${reason}</div>
            </article>
        `;
    }).join('');

    previousTotalEl.textContent = `${previousTotal} 格`;
    targetTotalEl.textContent = `${targetTotal} 格`;
    addTotalEl.textContent = `+${addTotal} 格`;
    reduceTotalEl.textContent = `-${reduceTotal} 格`;
    cardsEl.innerHTML = cardsHtml;
    panel.style.display = 'block';
}
```

- [ ] **Step 3: Run the JS contract tests**

Run:

```bash
pytest tests/test_home_daily_profit_frontend.py::test_load_batch_signals_renders_position_grid_instead_of_daily_profit tests/test_home_daily_profit_frontend.py::test_position_grid_delta_uses_strategy_slots_not_today_action_count tests/test_home_daily_profit_frontend.py::test_position_grid_sort_prioritizes_add_reduce_then_hold tests/test_home_daily_profit_frontend.py::test_position_grid_renders_slot_segment_states -q
```

Expected: PASS.

## Task 4: Add Homepage Position Grid Styles

**Files:**
- Modify: `static/css/home.css`
- Test: manual browser inspection

- [ ] **Step 1: Append the position grid CSS before the existing table styles or near section styles**

Add:

```css
/* Position Grid */
.position-grid-panel {
    margin-bottom: 30px;
    padding: 18px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #ffffff;
}

.position-grid-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
    margin-bottom: 14px;
}

.position-grid-subtitle {
    margin-top: -6px;
    color: #64748b;
    font-size: 13px;
}

.position-grid-sort-note {
    color: #64748b;
    font-size: 12px;
    white-space: nowrap;
}

.position-grid-summary {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 10px;
    margin-bottom: 14px;
}

.position-grid-metric {
    padding: 12px 14px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #f8fafc;
}

.position-grid-metric span {
    display: block;
    margin-bottom: 4px;
    color: #64748b;
    font-size: 12px;
    font-weight: 600;
}

.position-grid-metric strong {
    color: #17202a;
    font-size: 22px;
}

.position-grid-metric.add strong {
    color: #dc2626;
}

.position-grid-metric.reduce strong {
    color: #d97706;
}

.position-grid-cards {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(255px, 1fr));
    gap: 12px;
}

.position-grid-card {
    min-height: 154px;
    padding: 13px;
    border: 1px solid #dce5ec;
    border-radius: 8px;
    background: #fff;
}

.position-grid-card.add {
    border-left: 4px solid #dc2626;
    box-shadow: 0 1px 8px rgba(220, 38, 38, 0.08);
}

.position-grid-card.reduce {
    border-left: 4px solid #f59e0b;
    box-shadow: 0 1px 8px rgba(245, 158, 11, 0.08);
}

.position-grid-card.hold {
    background: #fbfcfd;
    opacity: 0.66;
}

.position-card-head {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
    margin-bottom: 9px;
}

.position-card-name {
    color: #17202a;
    font-size: 15px;
    font-weight: 750;
    line-height: 1.25;
}

.position-card-code {
    margin-top: 2px;
    color: #64748b;
    font-size: 12px;
}

.position-delta-badge {
    flex: 0 0 auto;
    min-height: 22px;
    padding: 3px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 750;
    white-space: nowrap;
}

.position-delta-badge.add {
    color: #b91c1c;
    background: #fee2e2;
}

.position-delta-badge.reduce {
    color: #92400e;
    background: #fef3c7;
}

.position-delta-badge.hold {
    color: #475569;
    background: #e2e8f0;
}

.position-card-change {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 8px;
}

.position-card-change strong {
    color: #17202a;
    font-size: 24px;
    line-height: 1;
}

.position-card-change span {
    color: #64748b;
    font-size: 12px;
}

.position-slot-bar {
    display: grid;
    grid-template-columns: repeat(var(--slot-total), minmax(0, 1fr));
    gap: 2px;
    width: 100%;
    min-height: 13px;
    margin: 8px 0 9px;
}

.position-slot-segment {
    height: 13px;
    border-radius: 2px;
    background: #edf2f7;
}

.position-slot-segment.keep {
    background: #22c55e;
}

.position-slot-segment.add {
    background: #ef4444;
}

.position-slot-segment.reduce {
    background: #f59e0b;
}

.position-slot-segment.empty {
    background: #edf2f7;
}

.position-card-meta {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 5px 8px;
    color: #64748b;
    font-size: 12px;
}

.position-card-meta b {
    color: #17202a;
}

.position-card-reason {
    margin-top: 8px;
    color: #52606d;
    font-size: 12px;
    line-height: 1.35;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.position-grid-empty {
    grid-column: 1 / -1;
    padding: 28px;
    color: #64748b;
    text-align: center;
    background: #f8fafc;
    border: 1px dashed #cbd5e1;
    border-radius: 8px;
}
```

- [ ] **Step 2: Add responsive rules inside the existing mobile media area or at the file end**

Add:

```css
@media (max-width: 900px) {
    .position-grid-header {
        align-items: flex-start;
        flex-direction: column;
    }

    .position-grid-sort-note {
        white-space: normal;
    }

    .position-grid-summary {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}

@media (max-width: 560px) {
    .position-grid-panel {
        padding: 14px;
    }

    .position-grid-summary {
        grid-template-columns: 1fr;
    }

    .position-grid-cards {
        grid-template-columns: 1fr;
    }
}
```

- [ ] **Step 3: Run the targeted tests**

Run:

```bash
pytest tests/test_home_daily_profit_frontend.py -q
```

Expected: PASS.

## Task 5: Verify The Homepage End To End

**Files:**
- Verify: `templates/index.html`
- Verify: `static/js/home.js`
- Verify: `static/css/home.css`
- Test: `tests/test_home_daily_profit_frontend.py`

- [ ] **Step 1: Run focused tests**

Run:

```bash
pytest tests/test_home_daily_profit_frontend.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run broader frontend-adjacent tests**

Run:

```bash
pytest tests/test_home_daily_profit_frontend.py tests/test_position_snapshots.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Start the app for manual inspection**

Run:

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Expected: server starts and logs that it is listening on `http://0.0.0.0:8000`.

- [ ] **Step 4: Inspect `/` in the browser**

Open:

```text
http://localhost:8000/
```

Expected:

- The page shows the existing header and action bar.
- The old standalone "今日收益" panel is gone.
- The new "持仓格子" panel appears where the old daily-profit panel was.
- Cards show all watchlist ETFs.
- Add cards appear before reduce cards, and hold cards appear last.
- Slot colors match the spec: green retained, red added, orange reduced, gray empty.
- The strategy table remains below the card wall.

- [ ] **Step 5: Stop the app server**

Use `Ctrl-C` in the terminal running uvicorn.

Expected: server exits cleanly.

## Self-Review

- Spec coverage: The plan covers replacing `dailyProfitPanel`, using strategy slot movement, showing all ETFs, sorting add/reduce/hold, preserving the table, no action buttons, responsive styling, empty states, and tests.
- Placeholder scan: The plan contains no TBD/TODO/fill-later steps.
- Type consistency: Helper names are consistent across tests and implementation: `renderPositionGrid`, `sortPositionGridItems`, `getStrategySlotMovement`, `renderSlotSegments`, and `getPositionGridReason`.
