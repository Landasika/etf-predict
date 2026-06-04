// 首页策略汇总
console.log('📝 home.js v93 已加载 - 首页持仓格子');

// 实时更新控制
let realtimeEnabled = false;
let realtimeRefreshInterval = null;
let realtimeCountdownInterval = null;  // 倒计时定时器
let nextRefreshTime = null;  // 下次刷新时间
let positionSlotValue = 0;
let activeTradeSlotValue = 0;

// API请求辅助函数 - 处理认证和错误
async function fetchAPI(url, options = {}) {
    const response = await fetch(url, options);

    // 检查是否为401未认证
    if (response.status === 401) {
        // 尝试解析响应内容
        let errorMsg = '未认证，请先登录';
        try {
            const data = await response.json();
            errorMsg = data.message || errorMsg;
        } catch (e) {
            // 如果无法解析JSON，使用默认消息
        }

        // 跳转到登录页面
        alert(errorMsg);
        window.location.href = '/login';
        throw new Error(errorMsg);
    }

    // 检查其他错误状态
    if (!response.ok) {
        let errorMsg = `请求失败 (${response.status})`;
        try {
            const data = await response.json();
            errorMsg = data.message || data.error || errorMsg;
        } catch (e) {
            // 如果无法解析JSON，尝试获取文本
            const text = await response.text();
            if (text) {
                errorMsg = `服务器错误: ${text.substring(0, 100)}`;
            }
        }
        throw new Error(errorMsg);
    }

    return response.json();
}

document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ DOMContentLoaded 事件触发');

    // 初始化排序状态
    window.sortState = {
        column: null,
        direction: 'asc'
    };

    setupStrategyOverviewTabs();

    // 加载批量信号数据
    loadBatchSignals();
    loadDataDate();

    // 刷新按钮
    document.getElementById('refreshBtn').addEventListener('click', async function() {
        const btn = this;
        const originalText = btn.innerHTML;

        try {
            // 禁用按钮并显示加载状态
            btn.disabled = true;
            btn.innerHTML = '⏳ 刷新中...';

            // 调用刷新缓存API（使用fetchAPI辅助函数）
            const result = await fetchAPI('/api/watchlist/refresh-cache', {
                method: 'POST'
            });

            if (result.success) {
                // 刷新成功后重新加载数据（强制刷新，跳过缓存）
                await Promise.all([
                    loadBatchSignals(true),  // 强制刷新
                    loadDataDate()
                ]);

                // 显示成功提示
                alert(`刷新成功！\n策略数据: ${result.signals_count} 条\n数据日期: ${result.data_date}`);
            } else {
                alert('刷新失败: ' + result.message);
            }
        } catch (error) {
            console.error('刷新缓存失败:', error);
            // 如果是认证错误，不显示额外的alert（fetchAPI已经处理了）
            if (!error.message.includes('未认证')) {
                alert('刷新缓存失败: ' + error.message);
            }
        } finally {
            // 恢复按钮状态
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });

    // 更新数据按钮
    document.getElementById('updateDataBtn').addEventListener('click', triggerDataUpdate);

    // 添加ETF按钮
    document.getElementById('addEtfBtn').addEventListener('click', showAddModal);

    // 操作建议按钮
    document.getElementById('showAdviceBtn').addEventListener('click', showAdviceModal);

    // 点击模态框外部关闭
    document.getElementById('addEtfModal').addEventListener('click', function(e) {
        if (e.target === this) {
            hideAddModal();
        }
    });

    // 操作建议模态框
    document.getElementById('adviceModal').addEventListener('click', function(e) {
        if (e.target === this) {
            hideAdviceModal();
        }
    });
    document.querySelectorAll('#adviceModal .close, #adviceModal .close-modal').forEach(function(btn) {
        btn.addEventListener('click', hideAdviceModal);
    });

    // 检查Token配置状态
    checkTokenStatus();

    // 加载调度器状态
    loadSchedulerStatus();

    // 定期轮询调度器状态（每30秒）
    setInterval(loadSchedulerStatus, 30000);

    // 实时监控按钮
    document.getElementById('toggleRealtimeBtn').addEventListener('click', toggleRealtimeUpdate);
    document.getElementById('realtimeSettingsBtn').addEventListener('click', showRealtimeSettings);
    document.getElementById('closeRealtimeModalBtn').addEventListener('click', hideRealtimeSettings);
    document.getElementById('cancelRealtimeSettingsBtn').addEventListener('click', hideRealtimeSettings);
    document.getElementById('saveRealtimeSettingsBtn').addEventListener('click', saveRealtimeSettings);

    // 点击实时监控设置弹窗外部关闭
    document.getElementById('realtimeSettingsModal').addEventListener('click', function(e) {
        if (e.target === this) {
            hideRealtimeSettings();
        }
    });

    // 检查实时更新状态
    checkRealtimeStatus();
});

// 全局数据存储
let strategyData = [];

function setupStrategyOverviewTabs() {
    const tabs = Array.from(document.querySelectorAll('[data-strategy-tab]'));
    const panels = Array.from(document.querySelectorAll('[data-strategy-panel]'));

    if (tabs.length === 0 || panels.length === 0) {
        return;
    }

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.getAttribute('data-strategy-tab');

            tabs.forEach(item => {
                const isActive = item === tab;
                item.classList.toggle('active', isActive);
                item.setAttribute('aria-selected', isActive ? 'true' : 'false');
            });

            panels.forEach(panel => {
                panel.classList.toggle(
                    'active',
                    panel.getAttribute('data-strategy-panel') === target
                );
            });
        });
    });
}

// 加载批量信号数据
async function loadBatchSignals(forceRefresh = false) {
    try {
        const url = forceRefresh ? '/api/watchlist/batch-signals?refresh=true' : '/api/watchlist/batch-signals';
        const result = await fetchAPI(url);

        if (result.success) {
            positionSlotValue = getPositionSlotValue(result);
            strategyData = result.data;
            renderPositionGrid(strategyData);
            renderStrategyTable(strategyData);
            updateStats(strategyData);
            updateLastUpdated();

            // 显示缓存状态
            if (result.cached) {
                console.log('✅ 策略数据来自缓存 (数据日期: ' + result.data_date + ')');
            } else {
                console.log('🔄 策略数据重新计算完成 (数据日期: ' + result.data_date + ')');
            }
        }
    } catch (error) {
        console.error('加载信号数据失败:', error);
        // 如果是认证错误，不显示额外的错误提示（fetchAPI已经处理了跳转）
        if (!error.message.includes('未认证')) {
            showError('加载信号数据失败');
        }
    }
}

function clampSlotValue(value, fallback = 0) {
    const numberValue = Number(value);
    if (!Number.isFinite(numberValue)) {
        return fallback;
    }
    return Math.max(0, Math.trunc(numberValue));
}

function getPositionSlotValue(source = {}) {
    const value = Number(source.slot_value || positionSlotValue);
    return Number.isFinite(value) && value > 0 ? value : 0;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getValidPositionGridItems(data) {
    if (!Array.isArray(data)) {
        return [];
    }
    return data.filter(item => item && typeof item === 'object');
}

function getStrategySlotMovement(item) {
    const source = item && typeof item === 'object' ? item : {};
    const latestData = source.latest_data || {};
    const rawTotalSlots = clampSlotValue(source.total_positions, 10);
    const totalSlots = rawTotalSlots > 0 ? rawTotalSlots : 10;
    const previousSlots = Math.min(
        clampSlotValue(latestData.previous_positions_used, 0),
        totalSlots
    );
    const targetSlots = Math.min(
        clampSlotValue(source.positions_used, 0),
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

function formatMoney(value) {
    const numberValue = Number(value || 0);
    const prefix = numberValue > 0 ? '+' : '';
    return `${prefix}¥${numberValue.toFixed(2)}`;
}

function getPositionGridMacdParamsText(item) {
    const params = item.macd_params || {};
    const fast = params.fast ?? 8;
    const slow = params.slow ?? 17;
    const signal = params.signal ?? 5;
    return `F:${fast} S:${slow} Sig:${signal}`;
}

function renderPositionGrid(data) {
    const panel = document.getElementById('positionGridPanel');
    const cardsEl = document.getElementById('positionGridCards');
    const previousTotalEl = document.getElementById('positionGridPreviousTotal');
    const targetTotalEl = document.getElementById('positionGridTargetTotal');
    const addTotalEl = document.getElementById('positionGridAddTotal');
    const reduceTotalEl = document.getElementById('positionGridReduceTotal');
    const dailyProfitTotalEl = document.getElementById('positionGridDailyProfitTotal');
    const monthlyProfitTotalEl = document.getElementById('positionGridMonthlyProfitTotal');

    if (!panel || !cardsEl || !previousTotalEl || !targetTotalEl || !addTotalEl || !reduceTotalEl || !dailyProfitTotalEl || !monthlyProfitTotalEl) {
        return;
    }

    const validItems = getValidPositionGridItems(data);

    if (validItems.length === 0) {
        previousTotalEl.textContent = '0 格';
        targetTotalEl.textContent = '0 格';
        addTotalEl.textContent = '+0 格';
        reduceTotalEl.textContent = '-0 格';
        dailyProfitTotalEl.textContent = formatMoney(0);
        dailyProfitTotalEl.className = getProfitClass(0);
        monthlyProfitTotalEl.textContent = formatMoney(0);
        monthlyProfitTotalEl.className = getProfitClass(0);
        cardsEl.innerHTML = '<div class="position-grid-empty">暂无数据，请先添加ETF到自选</div>';
        panel.style.display = 'block';
        return;
    }

    const items = sortPositionGridItems(validItems);
    let previousTotal = 0;
    let targetTotal = 0;
    let addTotal = 0;
    let reduceTotal = 0;
    let totalDailyProfit = 0;
    let totalMonthlyProfit = 0;

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
        const strategyText = getShortStrategyName(item.strategy);
        const macdParamsText = getPositionGridMacdParamsText(item);
        const dailyChange = Number(item.daily_change_pct || 0);
        const dailyProfit = Number(item.daily_profit || 0);
        const monthlyProfit = Number(item.monthly_profit || 0);
        totalDailyProfit += dailyProfit;
        totalMonthlyProfit += monthlyProfit;
        const dailyChangeText = `${dailyChange >= 0 ? '+' : ''}${dailyChange.toFixed(2)}%`;
        const dailyChangeClass = getProfitClass(dailyChange);
        const dailyProfitClass = getProfitClass(dailyProfit);
        const monthlyProfitClass = getProfitClass(monthlyProfit);
        const macdText = Number.isFinite(Number(macd.hist)) ? `MACD ${Number(macd.hist).toFixed(4)}` : 'MACD --';
        const kdjText = kdj.status || 'KDJ --';
        const reason = getPositionGridReason(item, movement.delta);
        const code = item.code ?? '--';
        const remark = item.remark || item.name || code;
        const safeCode = escapeHtml(code);
        const safeName = escapeHtml(item.name || code);
        const safeRemark = escapeHtml(remark);
        const safeSignal = escapeHtml(signal);
        const safeSignalStrength = escapeHtml(signalStrength);
        const safeStrategyText = escapeHtml(strategyText);
        const safeMacdParamsText = escapeHtml(macdParamsText);
        const safeMacdText = escapeHtml(macdText);
        const safeKdjText = escapeHtml(kdjText);
        const safeReason = escapeHtml(reason);
        const safeAriaLabel = escapeHtml(`${code} 今日策略仓位 ${movement.targetSlots} 格`);

        return `
            <article class="${getPositionGridCardClass(movement.delta)}">
                <div class="position-card-head">
                    <div>
                        <div class="position-card-name">${safeName}</div>
                        <div class="position-card-code">${safeCode}</div>
                        <div class="position-card-remark">${safeRemark}</div>
                    </div>
                    ${getPositionGridBadge(movement.delta)}
                </div>
                <div class="position-card-change">
                    <strong>${movement.previousSlots} → ${movement.targetSlots}</strong>
                    <span>昨日策略 → 今日策略</span>
                </div>
                <div class="position-slot-bar" style="--slot-total:${movement.totalSlots}" role="meter" aria-valuemin="0" aria-valuemax="${movement.totalSlots}" aria-valuenow="${movement.targetSlots}" aria-label="${safeAriaLabel}">
                    ${renderSlotSegments(movement.previousSlots, movement.targetSlots, movement.totalSlots)}
                </div>
                <div class="position-card-meta">
                    <span>策略 <b>${safeStrategyText}</b></span>
                    <span>MACD参数 <b>${safeMacdParamsText}</b></span>
                    <span>信号 <b>${safeSignal}</b></span>
                    <span>强度 <b>${safeSignalStrength}</b></span>
                    <span>今日涨跌 <b class="${dailyChangeClass}">${dailyChangeText}</b></span>
                    <span>当日盈亏 <b class="${dailyProfitClass}">${formatMoney(dailyProfit)}</b></span>
                    <span>本月盈亏 <b class="${monthlyProfitClass}">${formatMoney(monthlyProfit)}</b></span>
                    <span><b>${safeMacdText}</b></span>
                    <span><b>${safeKdjText}</b></span>
                </div>
                <div class="position-card-reason" title="${safeReason}">${safeReason}</div>
            </article>
        `;
    }).join('');

    previousTotalEl.textContent = `${previousTotal} 格`;
    targetTotalEl.textContent = `${targetTotal} 格`;
    addTotalEl.textContent = `+${addTotal} 格`;
    reduceTotalEl.textContent = `-${reduceTotal} 格`;
    dailyProfitTotalEl.textContent = formatMoney(totalDailyProfit);
    dailyProfitTotalEl.className = getProfitClass(totalDailyProfit);
    monthlyProfitTotalEl.textContent = formatMoney(totalMonthlyProfit);
    monthlyProfitTotalEl.className = getProfitClass(totalMonthlyProfit);
    cardsEl.innerHTML = cardsHtml;
    panel.style.display = 'block';
}

// 渲染策略表格
function renderStrategyTable(data) {
    const tbody = document.getElementById('strategyTableBody');

    if (data.length === 0) {
        tbody.innerHTML = `
            <tr class="empty-row">
                <td colspan="16" class="empty-cell">
                    暂无数据，请先添加ETF到自选
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = data.map(item => {
        // 简化策略名称
        const shortStrategyName = getShortStrategyName(item.strategy);

        // MACD 参数显示
        const paramsDisplay = item.macd_params
            ? `<span class="macd-params-badge ${item.macd_params.is_optimized ? 'optimized' : ''}">
                 F:${item.macd_params.fast} S:${item.macd_params.slow} Sig:${item.macd_params.signal}
               </span>`
            : '<span class="macd-params-default">8/17/5</span>';

        // 近一年收益率（数据已经是近一年的，不需要再除以2）
        const strategyReturn = item.profit_pct;
        const stockReturn = (item.benchmark_return || 0);
        const dailyProfit = Number(item.daily_profit || 0);
        const monthlyProfit = Number(item.monthly_profit || 0);

        // 备注：优先使用用户自定义备注，否则使用自动生成的
        const remark = item.remark || generateRemark(item);
        const hasCustomRemark = !!item.remark;

        // 合并MACD和KDJ为"因子"
        const macd = item.macd || {};
        const kdj = item.kdj || {};
        const kdjStatus = kdj.status || '未知';
        const kdjStatusClass = getKdjStatusClass(kdjStatus);

        const factorsDisplay = `
            <div class="factors-info">
                <div class="factor-item">
                    <span class="factor-label">MACD:</span>
                    <span>DIF ${macd.dif?.toFixed(4) || 'N/A'}</span>
                    <span>DEA ${macd.dea?.toFixed(4) || 'N/A'}</span>
                </div>
                <div class="factor-item">
                    <span class="factor-label">KDJ:</span>
                    <span>K ${kdj.k?.toFixed(1) || 'N/A'}</span>
                    <span>D ${kdj.d?.toFixed(1) || 'N/A'}</span>
                    <span class="kdj-status-mini ${kdjStatusClass}">${kdjStatus}</span>
                </div>
            </div>
        `;

        // 数据更新日期
        const dataUpdateDate = item.data_date || '-';
        const dataDateDisplay = `
            <span class="data-date-badge">${dataUpdateDate}</span>
        `;

        // 今日操作样式
        let todayOperationClass = '';
        if (item.today_action_count > 0) {
            todayOperationClass = 'signal-badge buy';  // 买入
        } else if (item.today_action_count < 0) {
            todayOperationClass = 'signal-badge sell';  // 卖出
        } else {
            todayOperationClass = 'signal-badge hold';  // 持有
        }

        return `
        <tr>
            <td><strong>${item.code}</strong></td>
            <td>${item.name}</td>
            <td><span class="strategy-name">${shortStrategyName}</span></td>
            <td>${paramsDisplay}</td>
            <td><span class="${todayOperationClass}">${item.today_operation || item.signal_name}</span></td>
            <td><strong>${item.next_action}</strong></td>
            <td>
                <span class="${getProfitClass(strategyReturn)}">
                    ${strategyReturn >= 0 ? '+' : ''}${strategyReturn.toFixed(2)}%
                </span>
            </td>
            <td>
                <span class="${getProfitClass(stockReturn)}">
                    ${stockReturn >= 0 ? '+' : ''}${stockReturn.toFixed(2)}%
                </span>
            </td>
            <td>
                <strong>${item.db_position !== undefined ? item.db_position : item.positions_used}仓</strong>
                ${item.db_position !== undefined && item.db_position !== item.positions_used
                    ? ` <span style="font-size:11px;color:#f59e0b;">→信号${item.positions_used}仓</span>`
                    : ''}
            </td>
            <td>
                <span class="${getProfitClass(item.daily_change_pct || 0)}">
                    ${(item.daily_change_pct || 0) >= 0 ? '+' : ''}${(item.daily_change_pct || 0).toFixed(2)}%
                </span>
            </td>
            <td>
                <span class="${getProfitClass(dailyProfit)}">
                    ${formatMoney(dailyProfit)}
                </span>
            </td>
            <td>
                <span class="${getProfitClass(monthlyProfit)}">
                    ${formatMoney(monthlyProfit)}
                </span>
            </td>
            <td>${factorsDisplay}</td>
            <td>${dataDateDisplay}</td>
            <td><span class="remark-text ${hasCustomRemark ? 'custom-remark' : ''}" onclick="editRemark('${item.code}', '${(item.remark || '').replace(/'/g, "\\'")}')" title="${hasCustomRemark ? '点击编辑' : '点击添加备注'}">${remark || '-'}</span></td>
            <td>
                <div class="action-buttons">
                    <a href="/macd-watchlist#${item.code}" class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px;">详情</a>
                    <button class="btn btn-secondary" style="font-size: 11px; padding: 4px 8px; background: #fef3c7; border-color: #f59e0b; color: #92400e;" onclick="openTradeModal('${item.code}', ${item.db_position || 0}, ${item.positions_used}, ${item.price || 0}, '${item.strategy || 'macd_aggressive'}', ${getPositionSlotValue(item)})">调整</button>
                    <button class="btn btn-danger" onclick="removeEtf('${item.code}')">删除</button>
                </div>
            </td>
        </tr>
    `;
    }).join('');

    // 延迟添加排序功能，确保DOM已更新
    setTimeout(() => {
        addSortableHeaders('strategyTable', sortStrategyData);
    }, 10);
}

// 全局排序处理函数
function handleHeaderClick(header, table, sortFunction) {
    return function() {
        const column = header.textContent.trim().replace(' ⇅', '').replace(' ↑', '').replace(' ↓', '');

        // 切换排序方向
        if (window.sortState.column === column) {
            window.sortState.direction = window.sortState.direction === 'asc' ? 'desc' : 'asc';
        } else {
            window.sortState.column = column;
            window.sortState.direction = 'asc';
        }

        // 更新图标
        table.querySelectorAll('.sort-icon').forEach(icon => {
            icon.innerHTML = ' ⇅';
            icon.style.opacity = '0.3';
        });
        const currentIcon = header.querySelector('.sort-icon');
        if (currentIcon) {
            currentIcon.innerHTML = window.sortState.direction === 'asc' ? ' ↑' : ' ↓';
            currentIcon.style.opacity = '1';
        }

        // 排序数据
        sortFunction(column, window.sortState.direction);
    };
}

// 添加可排序的表头
function addSortableHeaders(tableId, sortFunction) {
    const table = document.getElementById(tableId);
    if (!table) return;

    const headers = table.querySelectorAll('th');

    headers.forEach((header, index) => {
        // 跳过"操作"列（最后一列）
        if (index === headers.length - 1) return;

        // 设置样式
        header.style.cursor = 'pointer';
        header.style.userSelect = 'none';

        // 添加排序图标（如果还没有）
        if (!header.querySelector('.sort-icon')) {
            const icon = document.createElement('span');
            icon.className = 'sort-icon';
            icon.innerHTML = ' ⇅';
            icon.style.marginLeft = '5px';
            icon.style.opacity = '0.3';
            icon.style.fontSize = '12px';
            header.appendChild(icon);
        }

        // 如果还没有设置点击处理，则设置
        if (!header.hasAttribute('data-sortable')) {
            header.setAttribute('data-sortable', 'true');
            header.onclick = handleHeaderClick(header, table, sortFunction);
        }
    });
}

// 策略表格排序
function sortStrategyData(column, direction) {
    const columnMap = {
        'ETF代码': 'code',
        'ETF名称': 'name',
        '策略': 'strategy',
        '今日操作': 'today_action_count',
        '下个交易日操作': 'next_action',
        '近一年策略收益率': 'profit_pct',
        '近一年股票涨幅率': 'benchmark_return',
        '持仓': 'positions_used',
        '当日涨幅': 'daily_change_pct',
        '当日盈亏': 'daily_profit',
        '本月盈亏': 'monthly_profit'
    };

    const field = columnMap[column];
    if (!field) return;

    strategyData.sort((a, b) => {
        let valA = a[field];
        let valB = b[field];

        // 今日操作按数值排序（买入最多排最前）
        if (column === '今日操作') {
            // today_action_count: 正数买入，负数卖出，0持有
            // 排序：买入多 > 买入少 > 持有 > 卖出少 > 卖出多
            return direction === 'asc' ? valA - valB : valB - valA;
        }

        if (typeof valA === 'string') {
            valA = valA.toLowerCase();
            valB = valB.toLowerCase();
        }

        if (direction === 'asc') {
            return valA > valB ? 1 : -1;
        } else {
            return valA < valB ? 1 : -1;
        }
    });

    renderStrategyTable(strategyData);
}

// 更新统计信息
function updateStats(data) {
    const totalCount = data.length;
    const buyCount = data.filter(item => item.signal === 'buy' || item.signal === 'BUY').length;
    const sellCount = data.filter(item => item.signal === 'sell' || item.signal === 'SELL').length;
    const holdCount = data.filter(item => item.signal === 'hold' || item.signal === 'HOLD').length;

    document.getElementById('totalCount').textContent = totalCount;
    document.getElementById('buyCount').textContent = buyCount;
    document.getElementById('sellCount').textContent = sellCount;
    document.getElementById('holdCount').textContent = holdCount;
}

// 更新今日收益
function updateDailyProfit(data) {
    const panel = document.getElementById('dailyProfitPanel');
    const totalProfitEl = document.getElementById('dailyProfitTotal');
    const totalProfitPctEl = document.getElementById('dailyProfitPct');
    const detailsEl = document.getElementById('dailyProfitDetails');
    const backendTotalPositionsEl = document.getElementById('yesterdayTotalPositions');
    const backendTotalInvestmentEl = document.getElementById('yesterdayTotalInvestment');

    if (!panel || !totalProfitEl || !detailsEl) return;

    // 计算总收益和总仓位
    let totalProfit = 0;
    let totalInvestment = 0;  // 总投资（用于计算收益率）
    let backendTotalPositions = 0;  // 后端持仓总仓位

    // 为每个ETF计算今日收益
    const profitItems = data.map(item => {
        const dailyProfit = item.daily_profit || 0;
        const dailyChangePct = item.daily_change_pct || 0;
        const backendPositions = item.db_position !== undefined ? item.db_position : 0;
        const investment = backendPositions * getPositionSlotValue(item);
        totalProfit += dailyProfit;
        totalInvestment += investment;
        backendTotalPositions += backendPositions;

        return {
            code: item.code,
            name: item.name,
            profit: dailyProfit,
            changePct: dailyChangePct,
            positions: backendPositions
        };
    });

    // 过滤出后端有持仓的ETF
    const activeItems = profitItems.filter(item => item.positions > 0);

    if (activeItems.length === 0) {
        panel.style.display = 'none';
        return;
    }

    panel.style.display = 'block';

    // 更新后端总仓位和总资金
    backendTotalPositionsEl.textContent = `${backendTotalPositions}仓`;
    backendTotalInvestmentEl.textContent = `¥${totalInvestment.toLocaleString()}`;

    // 更新总收益
    const profitClass = totalProfit >= 0 ? 'positive' : 'negative';
    totalProfitEl.textContent = `${totalProfit >= 0 ? '+' : ''}¥${totalProfit.toFixed(2)}`;
    totalProfitEl.className = `daily-profit-value ${profitClass}`;

    // 计算收益率（相对于总投资）
    const profitPct = totalInvestment > 0 ? (totalProfit / totalInvestment * 100) : 0;
    totalProfitPctEl.textContent = `(${profitPct >= 0 ? '+' : ''}${profitPct.toFixed(2)}%)`;
    totalProfitPctEl.className = `daily-profit-pct ${profitClass}`;

    // 更新详情列表
    detailsEl.innerHTML = activeItems.map(item => {
        const profitClass = item.profit >= 0 ? '' : 'negative';
        const profitStr = `${item.profit >= 0 ? '+' : ''}¥${item.profit.toFixed(2)}`;
        const changeStr = `${item.changePct >= 0 ? '+' : ''}${item.changePct.toFixed(2)}%`;

        return `
            <div class="daily-profit-item">
                <span class="etf-name">${item.code} ${item.name}</span>
                <span class="etf-info" style="display: flex; align-items: center; gap: 10px;">
                    <span class="etf-profit ${profitClass}">${profitStr}</span>
                    <span class="etf-change">${item.positions}仓(后端) · ${changeStr}</span>
                </span>
            </div>
        `;
    }).join('');
}

// 更新最后更新时间
function updateLastUpdated() {
    const now = new Date();
    const timeStr = now.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
    document.getElementById('lastUpdated').textContent = timeStr;
}

// 获取收益样式类
function getProfitClass(profit) {
    if (profit > 0) return 'profit-positive';
    if (profit < 0) return 'profit-negative';
    return 'profit-neutral';
}

// 简化策略名称
function getShortStrategyName(strategy) {
    const nameMap = {
        'macd_aggressive': 'MACD激进',
        'macd_aggressive_entry': 'MACD激进+柱衰竭',
        'optimized_t_trading': '做T优化',
        'macd_kdj': 'MACD+KDJ',
        'multifactor': '多因子',
        'macd_kdj_discrete': 'MACD+KDJ离散',
        'rsi_macd_kdj_triple': '三指标共振',
        'pure_rsi': '纯RSI',
        'rsi_triple_lines': 'RSI三线',
        'macd_histogram_momentum': 'MACD柱动量'
    };
    return nameMap[strategy] || strategy;
}

// 生成备注
function generateRemark(item) {
    const remarks = [];

    // 根据持仓情况生成备注
    if (item.positions_used === 0) {
        remarks.push('空仓');
    } else if (item.positions_used <= 3) {
        remarks.push('轻仓');
    } else if (item.positions_used <= 7) {
        remarks.push('中仓');
    } else {
        remarks.push('重仓');
    }

    // 根据收益率生成备注（近一年收益率）
    const returnValue = item.profit_pct;
    if (returnValue > 30) {
        remarks.push('表现优秀');
    } else if (returnValue > 15) {
        remarks.push('表现良好');
    } else if (returnValue < 0) {
        remarks.push('亏损');
    }

    // 根据信号生成备注
    if (item.signal === 'buy' || item.signal === 'BUY') {
        remarks.push('买入信号');
    } else if (item.signal === 'sell' || item.signal === 'SELL') {
        remarks.push('卖出信号');
    }

    return remarks.length > 0 ? remarks.join('，') : '-';
}

// 显示添加模态框
function showAddModal() {
    document.getElementById('addEtfModal').classList.add('show');
}

// 隐藏添加模态框
function hideAddModal() {
    document.getElementById('addEtfModal').classList.remove('show');
    document.getElementById('etfCodeInput').value = '';
}

// 确认添加ETF
async function confirmAddEtf() {
    const etfCode = document.getElementById('etfCodeInput').value.trim();
    const strategy = document.getElementById('addStrategySelect').value;

    if (!etfCode) {
        alert('请输入ETF代码');
        return;
    }

    try {
        const response = await fetch('/api/watchlist/add', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                etf_code: etfCode,
                strategy: strategy
            })
        });

        const result = await response.json();

        if (result.success) {
            alert(result.message);
            hideAddModal();
            loadBatchSignals();
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('添加ETF失败:', error);
        alert('添加ETF失败');
    }
}

// 删除ETF
async function removeEtf(etfCode) {
    if (!confirm(`确定要删除 ${etfCode} 吗？`)) {
        return;
    }

    try {
        const response = await fetch(`/api/watchlist/${etfCode}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            alert(result.message);
            loadBatchSignals();
        } else {
            alert(result.message);
        }
    } catch (error) {
        console.error('删除ETF失败:', error);
        alert('删除ETF失败');
    }
}

// 加载数据日期
async function loadDataDate() {
    try {
        const result = await fetchAPI('/api/data/latest-date');

        if (result.success && result.latest_date) {
            // 格式化日期显示
            const dateStr = result.latest_date;
            const formattedDate = dateStr.substring(0, 4) + '-' +
                                 dateStr.substring(4, 6) + '-' +
                                 dateStr.substring(6, 8);
            document.getElementById('dataDate').textContent = formattedDate;
        } else {
            document.getElementById('dataDate').textContent = '无数据';
        }
    } catch (error) {
        console.error('加载数据日期失败:', error);
        // 认证错误已经在fetchAPI中处理
        if (!error.message.includes('未认证')) {
            document.getElementById('dataDate').textContent = '加载失败';
        }
    }
}

// 更新市场数据
async function updateMarketData() {
    const btn = document.getElementById('updateDataBtn');
    const originalText = btn.innerHTML;

    try {
        // 禁用按钮并显示加载状态
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon">⏳</span> 更新中...';

        const response = await fetch('/api/data/update', {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            alert(result.message + '\n\n' + (result.note || ''));
        } else {
            alert('更新失败: ' + result.message);
        }
    } catch (error) {
        console.error('更新数据失败:', error);
        alert('更新数据失败: ' + error.message);
    } finally {
        // 恢复按钮状态
        btn.disabled = false;
        btn.innerHTML = originalText;

        // 重新加载数据日期
        loadDataDate();
    }
}

// 显示错误
function showError(message) {
    // 这里可以添加更友好的错误显示
    console.error(message);
}

// 编辑备注
function editRemark(etfCode, currentRemark) {
    const newRemark = prompt('请输入备注内容：', currentRemark);

    // 如果用户点击取消或输入为空（但原来是空的），则不做处理
    if (newRemark === null) {
        return;
    }

    // 保存备注
    saveRemark(etfCode, newRemark);
}

// 保存备注
async function saveRemark(etfCode, remark) {
    try {
        const response = await fetch('/api/watchlist/remark', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                etf_code: etfCode,
                remark: remark
            })
        });

        const result = await response.json();

        if (result.success) {
            // 重新加载数据以显示新备注
            loadBatchSignals();
        } else {
            alert('保存备注失败: ' + result.message);
        }
    } catch (error) {
        console.error('保存备注失败:', error);
        alert('保存备注失败: ' + error.message);
    }
}

// KDJ 状态样式类映射
function getKdjStatusClass(status) {
    const classMap = {
        '严重超买': 'kdj-severe-overbought',
        '超买': 'kdj-overbought',
        '超卖': 'kdj-oversold',
        '正常': 'kdj-neutral',
        '未知': 'kdj-unknown'
    };
    return classMap[status] || 'kdj-unknown';
}

// ==================== 数据更新调度器 ====================

// 检查Token配置状态
async function checkTokenStatus() {
    try {
        const response = await fetch('/api/data-update/token-status');
        const result = await response.json();

        if (result.success && !result.data.configured) {
            // Token未配置，显示提示
            const updateDataBtn = document.getElementById('updateDataBtn');
            if (updateDataBtn) {
                updateDataBtn.title = '⚠️ 请先配置 tinyshare 授权码';
            }

            console.warn('⚠️ tinyshare 授权码未配置，数据更新功能不可用');
            console.warn('配置方法：先执行 pip install tinyshare --upgrade，再在 config.json 中设置 tinyshare.token');
        }
    } catch (error) {
        console.error('检查Token状态失败:', error);
    }
}

// 加载调度器状态
async function loadSchedulerStatus() {
    try {
        const response = await fetch('/api/data-update/scheduler/status');
        const result = await response.json();

        if (result.success) {
            const status = result.data;
            updateSchedulerUI(status);
        }
    } catch (error) {
        console.error('加载调度器状态失败:', error);
    }
}

// 更新调度器UI
function updateSchedulerUI(status) {
    const banner = document.getElementById('schedulerStatusBanner');
    const statusText = document.getElementById('schedulerStatusText');
    const nextRun = document.getElementById('schedulerNextRun');

    if (status.enabled) {
        banner.style.display = 'block';
        statusText.textContent = '定时任务已启用';
        if (status.next_run) {
            const nextDate = new Date(status.next_run);
            const now = new Date();
            const diffMs = nextDate - now;
            const diffMins = Math.floor(diffMs / 60000);

            if (diffMins > 0) {
                nextRun.textContent = `下次运行: ${status.next_run.split(' ')[1]} (${diffMins}分钟后)`;
            } else {
                nextRun.textContent = `下次运行: ${status.next_run.split(' ')[1]}`;
            }
        } else {
            nextRun.textContent = '';
        }
    } else {
        banner.style.display = 'none';
    }

    // 检查是否正在更新
    if (status.update_status.is_updating) {
        showDataUpdateProgress(status.update_status);
    }
}

// 触发数据更新
async function triggerDataUpdate() {
    // 先检查Token是否配置
    try {
        const tokenResponse = await fetch('/api/data-update/token-status');
        const tokenResult = await tokenResponse.json();

        if (tokenResult.success && !tokenResult.data.configured) {
            alert(
                '⚠️ tinyshare 授权码未配置！\n\n' +
                'tinyshare sdk 使用 - 首次不满意可退款\n\n' +
                '1. 安装 tinyshare（首次使用）\n' +
                '   pip install tinyshare --upgrade\n' +
                '2. import tushare as ts 改为：\n' +
                '   import tinyshare as ts\n' +
                '3. 原 token 替换为 tinyshare 的 token（积分授权码）\n\n' +
                '支持配置文件配置，建议在 config.json 中设置 tinyshare.token。\n' +
                '迁移只需修改一句代码。'
            );
            return;
        }
    } catch (error) {
        console.error('检查Token状态失败:', error);
    }

    const confirmed = confirm(
        '立即更新ETF数据？\n\n' +
        '这将使用 tinyshare 下载最新的交易数据并更新到数据库。\n' +
        '预计耗时：1-3分钟\n\n' +
        '是否继续？'
    );

    if (!confirmed) return;

    const btn = document.getElementById('updateDataBtn');
    const originalText = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '⏳ 更新中...';

    try {
        const response = await fetch('/api/data-update/trigger', {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            // 显示进度面板
            showDataUpdateProgress({
                is_updating: true,
                message: '数据更新任务已启动，正在后台执行...'
            });

            // 开始轮询更新状态
            pollDataUpdateStatus();

            alert(result.message);
        } else {
            alert('启动失败: ' + result.message);
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    } catch (error) {
        console.error('触发更新失败:', error);
        alert('启动失败: ' + error.message);
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// 显示数据更新进度
function showDataUpdateProgress(updateStatus) {
    const panel = document.getElementById('dataUpdateProgressPanel');
    const progressBar = document.getElementById('dataUpdateProgressBar');
    const statusText = document.getElementById('dataUpdateStatusText');

    panel.style.display = 'block';
    statusText.textContent = updateStatus.message || '正在更新数据...';

    // 模拟进度条（实际进度需要从日志文件解析）
    if (updateStatus.is_updating) {
        progressBar.style.width = '60%';
        progressBar.classList.add('indeterminate');
    } else {
        progressBar.style.width = '100%';
        progressBar.classList.remove('indeterminate');
    }
}

// 隐藏数据更新进度
function hideDataUpdateProgress() {
    const panel = document.getElementById('dataUpdateProgressPanel');
    panel.style.display = 'none';
}

// 轮询数据更新状态
let updatePollCount = 0;
const MAX_POLL_COUNT = 60; // 最多轮询60次（5分钟）

async function pollDataUpdateStatus() {
    updatePollCount = 0;

    const poll = async () => {
        updatePollCount++;

        try {
            const response = await fetch('/api/data-update/scheduler/status');
            const result = await response.json();

            if (result.success) {
                const updateStatus = result.data.update_status;

                if (!updateStatus.is_updating) {
                    // 更新完成
                    hideDataUpdateProgress();
                    updateSchedulerUI(result.data);

                    // 恢复按钮
                    const btn = document.getElementById('updateDataBtn');
                    btn.disabled = false;
                    btn.innerHTML = '<span class="btn-icon">📥</span> 立即更新数据';

                    // 刷新数据
                    loadBatchSignals(true);
                    loadDataDate();

                    // 显示结果
                    const resultMsg = updateStatus.last_result ?
                        `数据更新${updateStatus.last_result}\n${updateStatus.message}` :
                        '数据更新完成';
                    alert(resultMsg);

                    return; // 停止轮询
                }

                // 更新进度显示
                showDataUpdateProgress(updateStatus);
            }
        } catch (error) {
            console.error('轮询状态失败:', error);
        }

        // 继续轮询
        if (updatePollCount < MAX_POLL_COUNT) {
            setTimeout(poll, 5000); // 每5秒轮询一次
        } else {
            // 超时
            hideDataUpdateProgress();
            const btn = document.getElementById('updateDataBtn');
            btn.disabled = false;
            btn.innerHTML = '<span class="btn-icon">📥</span> 立即更新数据';
            alert('数据更新超时，请稍后手动刷新页面查看结果');
        }
    };

    poll();
}


// ==================== 实时监控功能 ====================

// 切换实时更新状态
async function toggleRealtimeUpdate() {
    const btn = document.getElementById('toggleRealtimeBtn');

    // 切换状态
    realtimeEnabled = !realtimeEnabled;

    try {
        const response = await fetch('/api/realtime/toggle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({enabled: realtimeEnabled})
        });

        const result = await response.json();

        if (result.success) {
            updateRealtimeUI(result.data);

            if (realtimeEnabled) {
                // 启动定时刷新（每60秒）
                startRealtimeRefresh();
            } else {
                // 停止定时刷新
                stopRealtimeRefresh();
            }
        }
    } catch (error) {
        console.error('切换实时更新失败:', error);
        realtimeEnabled = !realtimeEnabled;  // 回滚
    }
}

// 更新实时监控UI
function updateRealtimeUI(data) {
    const btn = document.getElementById('toggleRealtimeBtn');
    const statusDiv = document.getElementById('realtimeStatus');
    const btnText = document.getElementById('realtimeBtnText');

    if (data.enabled) {
        btn.classList.add('btn-realtime-active');
        btnText.textContent = '停止监控';
        statusDiv.style.display = 'flex';

        if (data.is_trading_time) {
            document.querySelector('.status-indicator').classList.add('status-active');
            document.getElementById('realtimeStatusText').textContent = '监控中';
        } else {
            document.querySelector('.status-indicator').classList.remove('status-active');
            document.getElementById('realtimeStatusText').textContent = '等待开市';
        }

        // 启动倒计时显示
        startCountdown(data.update_interval || 60);
    } else {
        btn.classList.remove('btn-realtime-active');
        btnText.textContent = '启用实时监控';
        statusDiv.style.display = 'none';

        // 停止倒计时
        stopCountdown();
    }
}

// 启动实时刷新
function startRealtimeRefresh() {
    // 获取更新间隔（默认60秒）
    const updateInterval = 60;  // 可以从API获取

    // 设置下次刷新时间
    nextRefreshTime = new Date(Date.now() + updateInterval * 1000);

    // 立即刷新一次
    loadBatchSignals(true);

    // 启动定时刷新（每60秒）
    if (realtimeRefreshInterval) {
        clearInterval(realtimeRefreshInterval);
    }

    realtimeRefreshInterval = setInterval(() => {
        loadBatchSignals(true);  // 强制刷新，跳过缓存
        console.log('🔄 实时数据已刷新');

        // 更新下次刷新时间
        nextRefreshTime = new Date(Date.now() + updateInterval * 1000);
    }, updateInterval * 1000);

    console.log('✅ 实时刷新已启动');
}

// 停止实时刷新
function stopRealtimeRefresh() {
    if (realtimeRefreshInterval) {
        clearInterval(realtimeRefreshInterval);
        realtimeRefreshInterval = null;
        console.log('⏹️  实时刷新已停止');
    }

    stopCountdown();
}

// 启动倒计时显示
function startCountdown(updateInterval) {
    // 清除旧的倒计时
    stopCountdown();

    // 立即更新一次
    updateCountdown();

    // 每秒更新倒计时
    realtimeCountdownInterval = setInterval(updateCountdown, 1000);
}

// 停止倒计时
function stopCountdown() {
    if (realtimeCountdownInterval) {
        clearInterval(realtimeCountdownInterval);
        realtimeCountdownInterval = null;
    }

    // 重置显示
    const lastUpdateEl = document.getElementById('realtimeLastUpdate');
    if (lastUpdateEl) {
        lastUpdateEl.textContent = '--:--:--';
    }
}

// 更新倒计时显示
function updateCountdown() {
    const lastUpdateEl = document.getElementById('realtimeLastUpdate');
    if (!lastUpdateEl || !nextRefreshTime) return;

    const now = new Date();
    const diff = nextRefreshTime - now;

    if (diff <= 0) {
        // 倒计时结束，显示"刷新中..."
        lastUpdateEl.textContent = '刷新中...';
        return;
    }

    // 计算剩余时间
    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);

    // 格式化为 MM:SS
    const countdown = `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    lastUpdateEl.textContent = `${countdown}后刷新`;
}

// 检查实时更新状态
async function checkRealtimeStatus() {
    try {
        const response = await fetch('/api/realtime/status');
        const result = await response.json();

        if (result.success) {
            realtimeEnabled = result.data.enabled;
            updateRealtimeUI(result.data);

            if (realtimeEnabled) {
                startRealtimeRefresh();
            }
        }
    } catch (error) {
        console.error('检查实时状态失败:', error);
    }
}

// 显示实时监控设置
async function showRealtimeSettings() {
    // 加载当前设置
    try {
        const response = await fetch('/api/realtime/settings');
        const result = await response.json();

        if (result.success) {
            const settings = result.data;
            document.getElementById('realtimeStartTime').value = settings.start_time || '09:25';
            document.getElementById('realtimeEndTime').value = settings.end_time || '15:05';
            document.getElementById('realtimeInterval').value = settings.update_interval || 60;
        }
    } catch (error) {
        console.error('加载设置失败:', error);
    }

    // 显示弹窗
    document.getElementById('realtimeSettingsModal').style.display = 'block';
}

// 隐藏实时监控设置
function hideRealtimeSettings() {
    document.getElementById('realtimeSettingsModal').style.display = 'none';
}

// 保存实时监控设置
async function saveRealtimeSettings() {
    const startTime = document.getElementById('realtimeStartTime').value;
    const endTime = document.getElementById('realtimeEndTime').value;
    const interval = parseInt(document.getElementById('realtimeInterval').value);

    // 验证时间范围
    if (startTime >= endTime) {
        alert('⚠️ 开始时间必须早于结束时间');
        return;
    }

    try {
        const response = await fetch('/api/realtime/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                start_time: startTime,
                end_time: endTime,
                update_interval: interval
            })
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ 设置已保存');
            hideRealtimeSettings();

            // 如果实时监控正在运行，重启以应用新设置
            if (realtimeEnabled) {
                stopRealtimeRefresh();
                startRealtimeRefresh();
            }
        } else {
            alert('❌ 保存失败: ' + result.message);
        }
    } catch (error) {
        console.error('保存设置失败:', error);
        alert('❌ 保存失败: ' + error.message);
    }
}

// ==================== 操作建议功能 ====================

/**
 * 显示操作建议模态框
 */
async function showAdviceModal() {
    const modal = document.getElementById('adviceModal');
    modal.classList.add('show');
    modal.style.display = 'flex';
    await loadAdvice();
}

/**
 * 隐藏操作建议模态框
 */
function hideAdviceModal() {
    const modal = document.getElementById('adviceModal');
    modal.classList.remove('show');
    modal.style.display = 'none';
}

/**
 * 加载操作建议
 */
async function loadAdvice() {
    const adviceContent = document.getElementById('adviceContent');
    adviceContent.innerHTML = '<div class="loading">正在分析市场数据...</div>';

    try {
        let signals = getValidPositionGridItems(strategyData);
        if (signals.length === 0) {
            const result = await fetchAPI('/api/watchlist/batch-signals');
            if (!result.success || !result.data) {
                adviceContent.innerHTML = '<div class="error">加载数据失败</div>';
                return;
            }
            positionSlotValue = getPositionSlotValue(result);
            strategyData = result.data;
            signals = getValidPositionGridItems(strategyData);
        }

        const formattedSignals = signals.map(etf => ({
            code: etf.code,
            name: etf.name,
            signal: etf.signal,
            close: Number(etf.price || 0),
            macd_dif: Number(etf.macd?.dif || 0),
            macd_dea: Number(etf.macd?.dea || 0),
            macd_hist: Number(etf.macd?.hist || 0),
            signal_strength: Number(etf.signal_strength ?? 0),
            positions_used: Number(etf.positions_used || 0),
            total_positions: etf.total_positions || 10,
            profit_pct: etf.profit_pct,
            action_reason: etf.action_reason || '',
            today_action_count: Number(etf.today_action_count || 0),
            today_operation: etf.today_operation || '',
            db_position: Number(etf.db_position ?? 0),
            previous_positions_used: etf.previous_positions_used ?? etf.db_position ?? 0
        }));

        const buySignals = formattedSignals.filter(s => s.today_action_count > 0);
        const sellSignals = formattedSignals.filter(s => s.today_action_count < 0);
        const holdSignals = formattedSignals.filter(s => s.today_action_count === 0);

        // 生成建议HTML
        let html = '<div class="advice-container">';

        // 买入建议
        if (buySignals.length > 0) {
            html += '<div class="advice-section advice-buy">';
            html += '<h3>🟢 建议买入 (' + buySignals.length + '只)</h3>';
            html += '<table class="advice-table">';
            html += '<thead><tr><th class="col-code">代码</th><th class="col-name">名称</th><th class="col-price">现价</th><th class="col-macd">MACD</th><th class="col-signal">信号强度</th><th class="col-advice">操作理由</th></tr></thead>';
            html += '<tbody>';

            buySignals.forEach(etf => {
                const dif = etf.macd_dif;
                const dea = etf.macd_dea;
                const strength = etf.signal_strength;  // 使用信号生成器的强度值
                const previousPositions = etf.previous_positions_used || 0;
                const currentPositions = etf.positions_used || 0;
                const positionsBought = Math.abs(etf.today_action_count || 0);
                const actualReason = etf.action_reason || 'MACD金叉买入';  // 使用实际的操作原因

                let advice = etf.today_operation || (positionsBought > 0 ? ('买入' + positionsBought + '仓') : '持有');
                let strengthLevel = '';
                let strengthEmoji = '';

                if (strength <= 3) {
                    strengthLevel = '弱';
                    strengthEmoji = '✨';
                } else if (strength <= 6) {
                    strengthLevel = '中';
                    strengthEmoji = '🔥';
                } else if (strength <= 9) {
                    if (strength === 9) {
                        strengthLevel = '极强';
                        strengthEmoji = '🔥🔥🔥';
                    } else if (strength === 8) {
                        strengthLevel = '强';
                        strengthEmoji = '🔥🔥';
                    } else {
                        strengthLevel = '中强';
                        strengthEmoji = '🔥🔥';
                    }
                } else {
                    strengthLevel = '极强';
                    strengthEmoji = '🔥🔥🔥';
                }

                const macdStatus = dif > 0 && dea > 0 ? '零轴上' : (dif < 0 && dea < 0 ? '零轴下' : '穿越中');

                html += '<tr>';
                html += '<td class="col-code">' + etf.code + '</td>';
                html += '<td class="col-name">' + etf.name + '</td>';
                html += '<td class="col-price">' + etf.close.toFixed(3) + '</td>';
                html += '<td class="col-macd" style="font-size:12px;color:#6b7280;">DIF:' + dif.toFixed(4) + '<br>DEA:' + dea.toFixed(4) + '<br>' + macdStatus + '</td>';
                html += '<td class="col-signal">' + strengthEmoji + ' ' + strengthLevel + ' (强度' + strength + ')</td>';
                html += '<td class="col-advice"><strong>' + advice + '</strong><br><span style="font-size:12px;color:#6b7280;font-weight:normal;">昨' + previousPositions + '仓 → 今' + currentPositions + '仓<br>' + actualReason + '</span></td>';
                html += '</tr>';
            });

            html += '</tbody></table></div>';
        }

        // 卖出建议
        if (sellSignals.length > 0) {
            html += '<div class="advice-section advice-sell">';
            html += '<h3>🔴 建议卖出 (' + sellSignals.length + '只)</h3>';
            html += '<table class="advice-table">';
            html += '<thead><tr><th class="col-code">代码</th><th class="col-name">名称</th><th class="col-price">现价</th><th class="col-macd">MACD</th><th class="col-signal">风险级别</th><th class="col-advice">操作理由</th></tr></thead>';
            html += '<tbody>';

            sellSignals.forEach(etf => {
                const dif = etf.macd_dif;
                const dea = etf.macd_dea;
                const strength = etf.signal_strength;  // 负数，如-6, -7, -8, -9, -10
                const previousPositions = etf.previous_positions_used || 0;
                const currentPositions = etf.positions_used || 0;
                const positionsToClose = Math.abs(etf.today_action_count || 0);
                const actualReason = etf.action_reason || 'MACD信号转弱';  // 使用实际的操作原因

                let riskLevel = '';
                let riskEmoji = '';
                let advice = etf.today_operation || (positionsToClose > 0 ? ('卖出' + positionsToClose + '仓') : '持有');

                if (strength >= -3) {
                    riskLevel = '低风险';
                    riskEmoji = '⚠️';
                } else if (strength >= -6) {
                    riskLevel = '中风险';
                    riskEmoji = '⚠️⚠️';
                } else {
                    riskLevel = '高风险';
                    riskEmoji = '⚠️⚠️⚠️';
                }

                const macdStatus = dif > 0 && dea > 0 ? '零轴上' : (dif < 0 && dea < 0 ? '零轴下' : '穿越中');

                html += '<tr>';
                html += '<td class="col-code">' + etf.code + '</td>';
                html += '<td class="col-name">' + etf.name + '</td>';
                html += '<td class="col-price">' + etf.close.toFixed(3) + '</td>';
                html += '<td class="col-macd" style="font-size:12px;color:#6b7280;">DIF:' + dif.toFixed(4) + '<br>DEA:' + dea.toFixed(4) + '<br>' + macdStatus + '</td>';
                html += '<td class="col-signal">' + riskEmoji + ' ' + riskLevel + ' (强度' + Math.abs(strength) + ')</td>';
                html += '<td class="col-advice"><strong>' + advice + '</strong><br><span style="font-size:12px;color:#6b7280;font-weight:normal;">昨' + previousPositions + '仓 → 今' + currentPositions + '仓<br>' + actualReason + '</span></td>';
                html += '</tr>';
            });

            html += '</tbody></table></div>';
        }

        if (buySignals.length === 0 && sellSignals.length === 0) {
            html += '<div class="advice-section advice-hold">';
            html += '<h3>✅ 今日无调仓</h3>';
            html += '<p>今日信号目标与昨日持仓一致，无需调仓。</p>';
            html += '</div>';
        }

        // 持有观望
        if (holdSignals.length > 0) {
            html += '<div class="advice-section advice-hold">';
            html += '<h3>⚪ 持有观望 (' + holdSignals.length + '只)</h3>';

            // 找出值得关注的ETF
            const attention = holdSignals.filter(etf => {
                const diff = etf.macd_dif - etf.macd_dea;
                // DIF接近DEA，可能即将交叉
                return Math.abs(diff) < 0.005;
            });

            if (attention.length > 0) {
                html += '<div class="attention-list">';
                html += '<h4>⭐ 值得关注（即将变盘）</h4>';
                html += '<table class="advice-table">';
                html += '<thead><tr><th>代码</th><th>名称</th><th>现价</th><th>MACD状态</th><th>关注理由</th></tr></thead>';
                html += '<tbody>';

                attention.forEach(etf => {
                    const dif = etf.macd_dif;
                    const dea = etf.macd_dea;
                    const diff = dif - dea;
                    let status = '';
                    let reason = '';
                    let emoji = '';

                    if (diff > 0 && dif > 0) {
                        status = '金叉中（零轴上）';
                        reason = '上升趋势明确，可考虑加仓';
                        emoji = '📈';
                    } else if (diff > 0 && dif < 0) {
                        status = '金叉中（零轴下）';
                        reason = '即将突破零轴，关键位置';
                        emoji = '🎯';
                    } else if (diff < 0 && dif > 0) {
                        status = '死叉中（零轴上）';
                        reason = '高位回调，注意风险';
                        emoji = '⚡';
                    } else {
                        status = '死叉中（零轴下）';
                        reason = '底部震荡，等待企稳';
                        emoji = '💎';
                    }

                    html += '<tr>';
                    html += '<td>' + etf.code + '</td>';
                    html += '<td>' + etf.name + '</td>';
                    html += '<td>' + etf.close.toFixed(3) + '</td>';
                    html += '<td>' + emoji + ' ' + status + '<br><span style="font-size:11px;color:#9ca3af;">DIF:' + dif.toFixed(4) + ' | DEA:' + dea.toFixed(4) + '</span></td>';
                    html += '<td>' + reason + '</td>';
                    html += '</tr>';
                });

                html += '</tbody></table>';
                html += '</div>';
            } else {
                html += '<p>当前市场稳定，暂无即将变盘的ETF</p>';
            }

            // 显示当前持仓信息
            const currentPosition = formattedSignals.filter(s => s.db_position > 0);
            if (currentPosition.length > 0) {
                html += '<div style="margin-top:20px;padding:15px;background:white;border-radius:8px;">';
                html += '<h5 style="margin:0 0 10px 0;color:#4b5563;">📦 当前持仓</h5>';
                currentPosition.slice(0, 5).forEach(etf => {
                    html += '<div style="padding:8px 0;border-bottom:1px solid #f3f4f6;display:flex;justify-content:space-between;">';
                    html += '<span>' + etf.code + ' ' + etf.name + '</span>';
                    html += '<span style="color:#059669;">' + etf.db_position + '仓</span>';
                    html += '</div>';
                });
                if (currentPosition.length > 5) {
                    html += '<div style="text-align:center;color:#9ca3af;padding-top:8px;">还有 ' + (currentPosition.length - 5) + ' 只持仓...</div>';
                }
                html += '</div>';
            }

            html += '</div>';
        }

        // 市场总结
        html += '<div class="advice-summary">';
        html += '<h3>📊 市场总结</h3>';
        html += '<ul>';

        const buyRatio = (buySignals.length / signals.length * 100).toFixed(1);
        const sellRatio = (sellSignals.length / signals.length * 100).toFixed(1);

        if (buySignals.length > sellSignals.length * 2) {
            html += '<li class="trend-bull">📈 市场偏多头，有 ' + buySignals.length + ' 只ETF出现买入信号，做多情绪浓厚</li>';
        } else if (sellSignals.length > buySignals.length * 2) {
            html += '<li class="trend-bear">📉 市场偏空头，有 ' + sellSignals.length + ' 只ETF出现卖出信号，注意风险控制</li>';
        } else {
            html += '<li class="trend-neutral">➡️ 市场处于震荡整理期，多空信号基本平衡，观望为主</li>';
        }

        html += '<li>📊 买入信号占比: ' + buyRatio + '%</li>';
        html += '<li>📊 卖出信号占比: ' + sellRatio + '%</li>';
        html += '<li>📊 观望信号占比: ' + (100 - parseFloat(buyRatio) - parseFloat(sellRatio)).toFixed(1) + '%</li>';

        // 添加操作建议
        if (buySignals.length === 0 && sellSignals.length === 0) {
            html += '<li style="color:#d97706;margin-top:12px;">💡 当前无明显交易信号，建议继续持仓观望，等待明确的买卖点</li>';
        } else if (buySignals.length > 0) {
            html += '<li style="color:#059669;margin-top:12px;">💡 出现买入信号，建议根据信号强度分批建仓，做好止损</li>';
        }

        html += '</ul>';
        html += '</div>';

        html += '</div>';

        adviceContent.innerHTML = html;

    } catch (error) {
        console.error('加载建议失败:', error);
        adviceContent.innerHTML = '<div class="error">加载失败: ' + error.message + '</div>';
    }
}

// ---- 持仓调整 ----
function openTradeModal(code, dbPos, sigPos, price, strategy, slotValue) {
    activeTradeSlotValue = getPositionSlotValue({ slot_value: slotValue });
    document.getElementById('tradeEtfCode').value = code;
    document.getElementById('tradePrice').value = price || '';
    document.getElementById('tradePosBefore').value = dbPos;
    document.getElementById('tradeAction').value = dbPos > sigPos ? 'SELL' : 'BUY';
    document.getElementById('tradePosAfter').value = sigPos;
    document.getElementById('tradeModal').style.display = 'flex';
    updateTradePreview();
}

function closeTradeModal() {
    document.getElementById('tradeModal').style.display = 'none';
}

function updateTradePreview() {
    const action = document.getElementById('tradeAction').value;
    const price = parseFloat(document.getElementById('tradePrice').value) || 0;
    const before = parseInt(document.getElementById('tradePosBefore').value) || 0;
    const after = parseInt(document.getElementById('tradePosAfter').value) || 0;
    const delta = Math.abs(after - before);
    const amount = delta * activeTradeSlotValue;
    const shares = price > 0 ? Math.floor(amount / price) : 0;
    const preview = document.getElementById('tradePreview');
    if (delta === 0) {
        preview.style.display = 'block';
        preview.innerHTML = '仓位无变化';
    } else {
        preview.style.display = 'block';
        preview.innerHTML = (action === 'BUY' ? '买入' : '卖出') + ' <b>' + delta + '</b> 仓 = <b>' + amount + '元</b>，约 <b>' + shares + '</b> 股 @ ' + price + '<br>仓位: ' + before + ' → ' + after;
    }
}

async function executeTrade() {
    const code = document.getElementById('tradeEtfCode').value;
    const action = document.getElementById('tradeAction').value;
    const price = parseFloat(document.getElementById('tradePrice').value);
    const before = parseInt(document.getElementById('tradePosBefore').value);
    const after = parseInt(document.getElementById('tradePosAfter').value);

    if (!price || before === after) { alert('请填写完整'); return; }
    try {
        const res = await fetch('/api/positions/' + code + '/execute', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action, price, positions_before: before, positions_after: after, strategy: 'manual' })
        });
        const data = await res.json();
        if (data.success) { alert(data.message); closeTradeModal(); location.reload(); }
        else { alert('失败: ' + JSON.stringify(data)); }
    } catch (e) { alert('请求失败: ' + e.message); }
}
