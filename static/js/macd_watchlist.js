/**
 * ETF策略回测自选管理页面
 * 支持多策略选择、持仓仓位显示
 */

// 全局状态
let currentEtfCode = null;
let currentStrategy = null;
let watchlistData = null;
let backtestChart = null;

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
let klineChart = null;
let positionHistoryChart = null;  // 仓位历史图表
let profitCurveChart = null;  // 收益曲线图表
let profitPositionChart = null;  // 收益页面仓位图表
let optimizedMacdParams = null;  // 存储优化后的MACD参数
let currentMacdParams = null;  // 当前使用的MACD参数

// 默认MACD参数
const DEFAULT_MACD_PARAMS = {
    macd_fast: 8,
    macd_slow: 17,
    macd_signal: 5
};

const FIXED_BACKTEST_START_DATE = '20250101';

// API基础URL
const API_BASE = '/api';

// 统一固定回测起点，避免每天滚动窗口导致历史结果漂移
function getBacktestStartDate() {
    return FIXED_BACKTEST_START_DATE;
}

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initEventListeners();
    loadWatchlist();
});

// 监听hash变化，处理从其他页面跳转过来的情况
window.addEventListener('hashchange', function() {
    const hash = window.location.hash.substring(1); // 移除#号
    if (hash) {
        selectEtf(hash);
    }
});

/**
 * 初始化事件监听器
 */
function initEventListeners() {
    // 添加ETF按钮
    document.getElementById('addEtfBtn').addEventListener('click', openAddEtfModal);

    // 关闭弹窗
    document.getElementById('closeModalBtn').addEventListener('click', closeAddEtfModal);
    document.getElementById('cancelAddBtn').addEventListener('click', closeAddEtfModal);

    // 确认添加
    document.getElementById('confirmAddBtn').addEventListener('click', confirmAddEtf);

    // 更新策略按钮
    document.getElementById('updateStrategyBtn').addEventListener('click', updateStrategy);

    // 高级设置
    document.getElementById('saveSettingsBtn').addEventListener('click', saveSettings);

    // 策略选择变化
    document.getElementById('addStrategySelect').addEventListener('change', function() {
        updateAddModalNote(this.value);
    });

    // 搜索框
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', handleSearch);
    }

    // 清除搜索按钮
    const clearSearchBtn = document.getElementById('clearSearchBtn');
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener('click', clearSearch);
    }

    // 点击弹窗外部关闭
    document.getElementById('addEtfModal').addEventListener('click', function(e) {
        if (e.target === this) {
            closeAddEtfModal();
        }
    });

    // 优化参数按钮
    const optimizeBtn = document.getElementById('optimizeParamsBtn');
    if (optimizeBtn) {
        optimizeBtn.addEventListener('click', optimizeMACDParams);
    }

    // 恢复默认参数按钮
    const resetBtn = document.getElementById('resetParamsBtn');
    if (resetBtn) {
        resetBtn.addEventListener('click', resetMacdParams);
    }

    // 关闭优化面板按钮
    const closeOptBtn = document.getElementById('closeOptPanelBtn');
    if (closeOptBtn) {
        closeOptBtn.addEventListener('click', function() {
            document.getElementById('optimizationResultPanel').style.display = 'none';
        });
    }
}

/**
 * 加载自选ETF列表
 */
async function loadWatchlist() {
    try {
        const response = await fetch(`${API_BASE}/watchlist`);
        watchlistData = await response.json();

        renderWatchlist(watchlistData.etfs);

        // 保存原始的hash处理函数
        const hashEtf = window.location.hash.substring(1);
        if (hashEtf) {
            // 验证hash中的ETF是否在自选列表中
            const etfExists = watchlistData.etfs.find(e => e.code === hashEtf);
            if (etfExists) {
                console.log('从URL hash加载ETF:', hashEtf);
                selectEtf(hashEtf);
            } else {
                console.warn('URL hash中的ETF不在自选列表中:', hashEtf);
                // 如果hash中的ETF不存在，使用默认ETF
                if (watchlistData.default_etf) {
                    selectEtf(watchlistData.default_etf);
                }
            }
        }
        // 如果没有hash，但有默认ETF，自动加载
        else if (watchlistData.default_etf) {
            selectEtf(watchlistData.default_etf);
        }
    } catch (error) {
        console.error('Failed to load watchlist:', error);
        showError('加载自选列表失败');
    }
}

/**
 * 渲染自选ETF列表
 */
function renderWatchlist(etfs) {
    const container = document.getElementById('watchlistContainer');

    if (!etfs || etfs.length === 0) {
        container.innerHTML = '<div class="empty-list">暂无自选ETF<br>点击"+ 添加"按钮添加</div>';
        return;
    }

    container.innerHTML = etfs.map(etf => {
        // Get strategy short name
        const strategyMap = {
            'macd_aggressive': 'MACD激进',
            'optimized_t_trading': '做T优化',
            'macd_kdj': 'MACD+KDJ',
            'multifactor': '量化',
            'macd_kdj_discrete': 'MACD+KDJ离散',
            'rsi_macd_kdj_triple': '三指标共振',
            'pure_rsi': '纯RSI',
            'rsi_triple_lines': 'RSI三线'
        };
        const strategyName = strategyMap[etf.strategy] || 'MACD';

        return `
        <div class="etf-item ${etf.code === currentEtfCode ? 'active' : ''}"
             data-code="${etf.code}"
             data-strategy="${etf.strategy || 'macd_aggressive'}"
             onclick="selectEtf('${etf.code}')">
            <div class="etf-info">
                <span class="etf-code">${etf.code}</span>
                <span class="etf-name">${etf.name}</span>
                <span class="etf-strategy">${strategyName}</span>
            </div>
            <button class="delete-btn"
                    onclick="event.stopPropagation(); removeEtf('${etf.code}')"
                    title="删除">×</button>
        </div>
    `;
    }).join('');
}

/**
 * 处理搜索
 */
function handleSearch(e) {
    const searchTerm = e.target.value.toLowerCase().trim();
    const clearBtn = document.getElementById('clearSearchBtn');

    // 显示或隐藏清除按钮
    if (searchTerm) {
        clearBtn.style.display = 'block';
    } else {
        clearBtn.style.display = 'none';
    }

    // 过滤ETF列表
    filterWatchlist(searchTerm);
}

/**
 * 清除搜索
 */
function clearSearch() {
    const searchInput = document.getElementById('searchInput');
    searchInput.value = '';
    document.getElementById('clearSearchBtn').style.display = 'none';

    // 重新显示完整的ETF列表
    if (watchlistData && watchlistData.etfs) {
        renderWatchlist(watchlistData.etfs);
    }
}

/**
 * 过滤ETF列表
 */
function filterWatchlist(searchTerm) {
    if (!watchlistData || !watchlistData.etfs) {
        return;
    }

    if (!searchTerm) {
        renderWatchlist(watchlistData.etfs);
        return;
    }

    const filtered = watchlistData.etfs.filter(etf => {
        const codeMatch = etf.code.toLowerCase().includes(searchTerm);
        const nameMatch = etf.name && etf.name.toLowerCase().includes(searchTerm);
        return codeMatch || nameMatch;
    });

    if (filtered.length === 0) {
        document.getElementById('watchlistContainer').innerHTML =
            '<div class="empty-list">未找到匹配的ETF</div>';
    } else {
        renderWatchlist(filtered);
    }
}

/**
 * 选择ETF
 */
async function selectEtf(etfCode) {
    if (currentEtfCode === etfCode) return;

    currentEtfCode = etfCode;

    // 从watchlist中获取该ETF的策略
    const etf = watchlistData.etfs.find(e => e.code === etfCode);
    currentStrategy = etf ? (etf.strategy || 'macd_aggressive') : 'macd_aggressive';

    // 更新UI激活状态
    document.querySelectorAll('.etf-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.code === etfCode) {
            item.classList.add('active');
        }
    });

    // 隐藏空状态，显示内容
    document.getElementById('emptyState').style.display = 'none';
    document.getElementById('strategySelector').style.display = 'flex';
    document.getElementById('advancedSettings').style.display = 'block';
    document.getElementById('realtimeCard').style.display = 'grid';
    document.getElementById('chartSection').style.display = 'block';
    document.getElementById('klineChartSection').style.display = 'block';
    document.getElementById('detailsSection').style.display = 'grid';

    // 更新策略选择器
    document.getElementById('strategySelect').value = currentStrategy;

    // 隐藏优化结果面板（但不重置优化参数）
    document.getElementById('optimizationResultPanel').style.display = 'none';

    // 根据策略显示/隐藏优化按钮
    updateOptimizeButtonVisibility(currentStrategy);

    // 加载并显示当前参数（从watchlist读取，会自动加载优化参数）
    if (currentStrategy === 'macd_kdj_discrete') {
        await loadAndDisplayDiscreteParams(etfCode);
    } else if (currentStrategy === 'rsi_triple_lines') {
        await loadAndDisplayRsiTripleLinesParams(etfCode);
    } else {
        await loadAndDisplayMacdParams(etfCode);
    }

    // 加载ETF的高级设置
    await loadEtfSettings(etfCode);

    // 根据策略类型显示对应的面板
    updatePanelsByStrategy(currentStrategy);

    // 加载数据
    await Promise.all([
        loadRealtimeSignal(etfCode, currentStrategy),
        loadBacktestData(etfCode, currentStrategy)
    ]);
}

/**
 * 根据策略类型更新面板显示
 */
function updatePanelsByStrategy(strategy) {
    const macdPanel = document.getElementById('macdPanel');
    const weightsPanel = document.getElementById('weightsPanel');
    const tripleIndicatorPanel = document.getElementById('tripleIndicatorPanel');
    const rsiIndicatorsPanel = document.getElementById('rsiIndicatorsPanel');
    const positionHistorySection = document.getElementById('positionHistorySection');

    // 先隐藏所有特殊面板
    if (tripleIndicatorPanel) tripleIndicatorPanel.style.display = 'none';
    if (rsiIndicatorsPanel) rsiIndicatorsPanel.style.display = 'none';
    if (positionHistorySection) positionHistorySection.style.display = 'none';

    if (strategy === 'macd_aggressive' || strategy === 'optimized_t_trading' || strategy === 'macd_kdj') {
        macdPanel.style.display = 'block';
        weightsPanel.style.display = 'none';
    } else if (strategy === 'macd_kdj_discrete') {
        macdPanel.style.display = 'block';
        weightsPanel.style.display = 'none';
    } else if (strategy === 'rsi_macd_kdj_triple') {
        macdPanel.style.display = 'none';
        weightsPanel.style.display = 'none';
        if (tripleIndicatorPanel) tripleIndicatorPanel.style.display = 'block';
        if (positionHistorySection) positionHistorySection.style.display = 'block';
    } else if (strategy === 'pure_rsi') {
        macdPanel.style.display = 'none';
        weightsPanel.style.display = 'none';
        if (rsiIndicatorsPanel) rsiIndicatorsPanel.style.display = 'block';
        if (positionHistorySection) positionHistorySection.style.display = 'block';
    } else if (strategy === 'rsi_triple_lines') {
        macdPanel.style.display = 'none';
        weightsPanel.style.display = 'none';
        // RSI三线策略也使用RSI面板显示
        if (rsiIndicatorsPanel) rsiIndicatorsPanel.style.display = 'block';
        if (positionHistorySection) positionHistorySection.style.display = 'block';
    } else if (strategy === 'multifactor') {
        macdPanel.style.display = 'none';
        weightsPanel.style.display = 'block';
    }

    // 更新优化按钮可见性
    updateOptimizeButtonVisibility(strategy);
}

/**
 * 根据策略类型显示/隐藏优化按钮
 */
function updateOptimizeButtonVisibility(strategy) {
    const macdParamsSection = document.getElementById('macdParamsSection');
    if (macdParamsSection) {
        // MACD激进策略、MACD+KDJ离散策略和RSI三线策略显示优化按钮和参数区域
        if (strategy === 'macd_aggressive' || strategy === 'macd_kdj_discrete' || strategy === 'rsi_triple_lines') {
            macdParamsSection.style.display = 'flex';
        } else {
            macdParamsSection.style.display = 'none';
        }
    }

    // 更新优化按钮的点击事件
    const optimizeBtn = document.getElementById('optimizeParamsBtn');
    if (optimizeBtn) {
        // 移除旧的事件监听器
        optimizeBtn.onclick = null;

        // 根据策略类型添加新的监听器
        if (strategy === 'macd_kdj_discrete') {
            optimizeBtn.onclick = optimizeMacdKdjDiscreteParams;
        } else if (strategy === 'rsi_triple_lines') {
            optimizeBtn.onclick = optimizeRsiTripleLinesParams;
        } else {
            optimizeBtn.onclick = optimizeMACDParams;
        }
    }

    // 更新恢复默认参数按钮的点击事件
    const resetBtn = document.getElementById('resetParamsBtn');
    if (resetBtn) {
        resetBtn.onclick = null;

        if (strategy === 'macd_kdj_discrete') {
            resetBtn.onclick = resetMacdKdjDiscreteParams;
        } else if (strategy === 'rsi_triple_lines') {
            resetBtn.onclick = resetRsiTripleLinesParams;
        } else {
            resetBtn.onclick = resetMacdParams;
        }
    }
}

/**
 * 加载实时信号
 */
async function loadRealtimeSignal(etfCode, strategy) {
    try {
        const startDate = getBacktestStartDate();
        const url = `${API_BASE}/watchlist/${etfCode}/signal?start_date=${startDate}&strategy=${strategy}`;
        const response = await fetch(url);
        const result = await response.json();

        if (!result.success) {
            showError(result.message);
            return;
        }

        const data = result.data;
        updateRealtimeCard(data, strategy);

    } catch (error) {
        console.error('Failed to load signal:', error);
        showError('加载实时信号失败');
    }
}

/**
 * 更新实时数据卡片
 */
function updateRealtimeCard(data, strategy) {
    // 更新页面顶部的最新数据日期
    const latestDateEl = document.getElementById('latestDataDate');
    if (latestDateEl && data.latest_date) {
        latestDateEl.textContent = data.latest_date;
    }

    // 显示权重状态（如果是多因子策略）
    if (strategy === 'multifactor' && data.weight_status) {
        showWeightStatus(data.weight_status);
    } else {
        hideWeightStatus();
    }

    // 显示初始资本信息（如果有建仓日期）
    if (data.backtest_summary) {
        const initialCapital = data.backtest_summary.initial_capital !== undefined ? data.backtest_summary.initial_capital : 2000;
        const buildDate = data.backtest_summary.build_position_date;
        const profitBasisEl = document.getElementById('profitBasis');

        const positionValue = data.position_value !== undefined ? data.position_value : 0;

        if (buildDate && initialCapital !== 2000) {
            // 有建仓日期
            const buildDateFormatted = `${buildDate.slice(0, 4)}-${buildDate.slice(4, 6)}-${buildDate.slice(6, 8)}`;
            profitBasisEl.textContent = `从${buildDateFormatted}建仓，初始资金¥${initialCapital.toFixed(0)}（近一年数据）`;
            profitBasisEl.style.color = '#667eea';

            console.log(`[收益计算] 建仓日期: ${buildDateFormatted}, 初始资本: ¥${initialCapital.toFixed(2)}, 当前资产: ¥${positionValue.toFixed(2)}, 收益: ¥${(positionValue - initialCapital).toFixed(2)} (${((positionValue - initialCapital) / initialCapital * 100).toFixed(2)}%)`);
        } else {
            // 无建仓日期，使用近一年数据
            profitBasisEl.textContent = `近一年数据，初始资金¥${initialCapital.toFixed(0)}`;
            profitBasisEl.style.color = '#999';
        }

        // 收益金额
        const profit = positionValue - initialCapital;
        const profitEl = document.getElementById('profitValue');
        profitEl.textContent = formatCurrency(profit, true);
        profitEl.className = `card-value ${profit >= 0 ? 'positive' : 'negative'}`;

        // 收益百分比
        const profitPct = (profit / initialCapital) * 100;
        const profitPctEl = document.getElementById('profitPct');
        profitPctEl.textContent = `(${profitPct.toFixed(2)}%)`;
        profitPctEl.className = `card-pct ${profit >= 0 ? 'positive' : 'negative'}`;
    } else {
        // 没有backtest_summary数据时的处理
        const positionValue = data.position_value !== undefined ? data.position_value : 0;
        const profit = positionValue - 2000;
        const profitEl = document.getElementById('profitValue');
        profitEl.textContent = formatCurrency(profit, true);
        profitEl.className = `card-value ${profit >= 0 ? 'positive' : 'negative'}`;

        const profitPct = (profit / 2000) * 100;
        const profitPctEl = document.getElementById('profitPct');
        profitPctEl.textContent = `(${profitPct.toFixed(2)}%)`;
        profitPctEl.className = `card-pct ${profit >= 0 ? 'positive' : 'negative'}`;

        // 更新收益说明
        const profitBasisEl = document.getElementById('profitBasis');
        profitBasisEl.textContent = '近一年数据，初始资金¥2000';
        profitBasisEl.style.color = '#999';
    }

    // 当前仓位
    const positionsUsed = data.positions_used !== undefined ? data.positions_used : 0;
    const positionsEl = document.getElementById('positionsUsed');
    positionsEl.textContent = `${positionsUsed}/10`;
    const ratio = positionsUsed / 10;
    if (ratio >= 0.8) {
        positionsEl.className = 'card-value positions high';
    } else if (ratio >= 0.5) {
        positionsEl.className = 'card-value positions medium';
    } else if (ratio > 0) {
        positionsEl.className = 'card-value positions low';
    } else {
        positionsEl.className = 'card-value positions empty';
    }

    // 下个交易日操作
    document.getElementById('nextAction').textContent = data.next_action || '--';

    // 根据策略类型更新对应的面板
    if (strategy === 'macd_aggressive' || strategy === 'optimized_t_trading' || strategy === 'macd_kdj') {
        updateMacdIndicators(data.latest_data);
    } else if (strategy === 'macd_kdj_discrete') {
        updateMacdIndicators(data.latest_data);
    } else if (strategy === 'rsi_macd_kdj_triple') {
        updateTripleIndicators(data.latest_data);
    } else if (strategy === 'pure_rsi') {
        updateRsiIndicators(data.latest_data);
    } else if (strategy === 'rsi_triple_lines') {
        updateRsiTripleLinesIndicators(data.latest_data);
    } else if (strategy === 'multifactor' && data.weights) {
        updateWeights(data.weights);
    }

    // 更新回测指标
    updateMetrics(data.backtest_summary);
}

/**
 * 更新MACD指标显示
 */
function updateMacdIndicators(latestData) {
    if (!latestData) return;

    const macdDif = latestData.macd_dif !== undefined ? latestData.macd_dif : 0;
    const macdDea = latestData.macd_dea !== undefined ? latestData.macd_dea : 0;

    document.getElementById('macdDif').textContent = macdDif.toFixed(4);
    document.getElementById('macdDea').textContent = macdDea.toFixed(4);

    const hist = macdDif - macdDea;
    const histEl = document.getElementById('macdHist');
    histEl.textContent = hist.toFixed(4);
    histEl.className = `macd-value ${hist >= 0 ? 'positive' : 'negative'}`;

    const signalStrength = latestData.signal_strength !== undefined ? latestData.signal_strength : 0;
    const strengthEl = document.getElementById('signalStrength');
    strengthEl.textContent = signalStrength;
    strengthEl.className = `macd-strength ${signalStrength >= 0 ? 'positive' : 'negative'}`;

    const signalType = latestData.signal_type || 'HOLD';
    const typeEl = document.getElementById('signalType');
    typeEl.textContent = signalType;
    typeEl.className = `macd-type ${signalType === 'BUY' ? 'buy' : signalType === 'SELL' ? 'sell' : 'hold'}`;
}

/**
 * 更新权重配置显示
 */
function updateWeights(weights) {
    if (!weights) return;

    const macdWeight = weights.MACD !== undefined ? weights.MACD : 0;
    const macdPct = (macdWeight * 100).toFixed(1);
    document.getElementById('macdWeightBar').style.width = macdPct + '%';
    document.getElementById('macdWeightValue').textContent = macdPct + '%';

    const kdjWeight = weights.KDJ !== undefined ? weights.KDJ : 0;
    const kdjPct = (kdjWeight * 100).toFixed(1);
    document.getElementById('kdjWeightBar').style.width = kdjPct + '%';
    document.getElementById('kdjWeightValue').textContent = kdjPct + '%';

    const bollWeight = weights.BOLL !== undefined ? weights.BOLL : 0;
    const bollPct = (bollWeight * 100).toFixed(1);
    document.getElementById('bollWeightBar').style.width = bollPct + '%';
    document.getElementById('bollWeightValue').textContent = bollPct + '%';
}

/**
 * 更新RSI+MACD+KDJ三指标显示
 */
function updateTripleIndicators(latestData) {
    if (!latestData) return;

    // 趋势铁律（新增）
    const trendType = latestData.trend_type || 'UNKNOWN';
    const trendTypeEl = document.getElementById('trendType');
    const trendStatusEl = document.getElementById('trendStatus');
    if (trendTypeEl) {
        let trendText = '未知';
        if (trendType === 'BULL') {
            trendText = '多头（可重仓）';
        } else if (trendType === 'FLAT') {
            trendText = '震荡（轻仓）';
        } else if (trendType === 'BEAR') {
            trendText = '空头（空仓）';
        }
        trendTypeEl.textContent = trendText;
        trendTypeEl.className = 'indicator-value ' + (trendType === 'BULL' ? 'bull' : trendType === 'FLAT' ? 'weak' : 'bear');
    }
    if (trendStatusEl) {
        if (trendType === 'BULL') {
            trendStatusEl.textContent = '0-8成';
            trendStatusEl.className = 'indicator-status golden-cross';
        } else if (trendType === 'FLAT') {
            trendStatusEl.textContent = '3-5成';
            trendStatusEl.className = 'indicator-status normal';
        } else if (trendType === 'BEAR') {
            trendStatusEl.textContent = '0-1成';
            trendStatusEl.className = 'indicator-status dead-cross';
        }
    }

    // MA20/MA60
    const ma20 = latestData.ma20 || 0;
    const ma60 = latestData.ma60 || 0;
    const maValueEl = document.getElementById('maValue');
    if (maValueEl && ma20 > 0 && ma60 > 0) {
        maValueEl.textContent = `MA20:${ma20.toFixed(2)} MA60:${ma60.toFixed(2)}`;
    }

    // MACD零轴状态
    const macdAboveZero = latestData.macd_above_zero || false;
    const macdZeroStatusEl = document.getElementById('macdZeroStatus');
    if (macdZeroStatusEl) {
        macdZeroStatusEl.textContent = macdAboveZero ? '零轴上方' : '零轴下方';
        macdZeroStatusEl.className = 'indicator-status ' + (macdAboveZero ? 'golden-cross' : 'dead-cross');
    }

    // RSI
    const rsi = latestData.rsi !== undefined ? latestData.rsi : 50;
    const rsiValueEl = document.getElementById('rsiValue');
    const rsiStatusEl = document.getElementById('rsiStatus');
    if (rsiValueEl) rsiValueEl.textContent = rsi.toFixed(1);
    if (rsiStatusEl) {
        let rsiStatus = '正常';
        let rsiClass = 'normal';
        if (rsi >= 80) {
            rsiStatus = '超买';
            rsiClass = 'overbought';
        } else if (rsi >= 70) {
            rsiStatus = '强势';
            rsiClass = 'strong';
        } else if (rsi <= 20) {
            rsiStatus = '超卖';
            rsiClass = 'oversold';
        } else if (rsi <= 30) {
            rsiStatus = '弱势';
            rsiClass = 'weak';
        }
        rsiStatusEl.textContent = rsiStatus;
        rsiStatusEl.className = 'indicator-status ' + rsiClass;
    }

    // KDJ
    const kdjK = latestData.kdj_k !== undefined ? latestData.kdj_k : 50;
    const kdjD = latestData.kdj_d !== undefined ? latestData.kdj_d : 50;
    const kdjJ = latestData.kdj_j !== undefined ? latestData.kdj_j : 50;
    const kdjValueEl = document.getElementById('kdjValue');
    const kdjStatusEl = document.getElementById('kdjStatus');
    if (kdjValueEl) kdjValueEl.textContent = `K:${kdjK.toFixed(1)} D:${kdjD.toFixed(1)} J:${kdjJ.toFixed(1)}`;
    if (kdjStatusEl) {
        let kdjStatus = '正常';
        let kdjClass = 'normal';
        const goldenCross = latestData.kdj_golden_cross || false;
        const deadCross = latestData.kdj_dead_cross || false;

        if (goldenCross) {
            kdjStatus = '金叉';
            kdjClass = 'golden-cross';
        } else if (deadCross) {
            kdjStatus = '死叉';
            kdjClass = 'dead-cross';
        } else if (kdjK >= 80) {
            kdjStatus = '高位';
            kdjClass = 'high';
        } else if (kdjK <= 20) {
            kdjStatus = '低位';
            kdjClass = 'low';
        }
        kdjStatusEl.textContent = kdjStatus;
        kdjStatusEl.className = 'indicator-status ' + kdjClass;
    }

    // 当前仓位
    const positionsUsed = latestData.positions_used !== undefined ? latestData.positions_used : 0;
    const positionValueEl = document.getElementById('currentPosition');
    if (positionValueEl) {
        positionValueEl.textContent = `${positionsUsed}/8成`;
        positionValueEl.className = 'position-value ' + (positionsUsed >= 5 ? 'heavy' : positionsUsed >= 3 ? 'medium' : 'light');
    }

    // 信号说明
    const signalReason = latestData.signal_reason || '--';
    const signalReasonEl = document.getElementById('signalReason');
    if (signalReasonEl) signalReasonEl.textContent = signalReason;
}

/**
 * 更新纯RSI策略指标显示
 */
function updateRsiIndicators(latestData) {
    if (!latestData) return;

    const rsi = latestData.rsi || 0;
    const rsiZone = latestData.rsi_zone || '';
    const rsiDirection = latestData.rsi_direction || '';
    const rsiConsecutiveUp = latestData.rsi_consecutive_up || 0;
    const positionReason = latestData.position_reason || '';

    // 更新RSI值
    const rsiValueEl = document.getElementById('rsiPureValue');
    if (rsiValueEl) rsiValueEl.textContent = rsi.toFixed(2);

    // 更新RSI区间
    const rsiZoneEl = document.getElementById('rsiPureZone');
    if (rsiZoneEl) {
        rsiZoneEl.textContent = _formatRsiZone(rsiZone);
        rsiZoneEl.className = 'indicator-value indicator-zone ' + _getRsiZoneClass(rsiZone);
    }

    // 更新RSI方向
    const rsiDirEl = document.getElementById('rsiPureDirection');
    if (rsiDirEl) {
        rsiDirEl.textContent = _formatRsiDirection(rsiDirection);
        rsiDirEl.className = 'indicator-value indicator-direction ' + _getRsiDirectionClass(rsiDirection);
    }

    // 更新连续向上天数
    const rsiConsecutiveUpEl = document.getElementById('rsiPureConsecutiveUp');
    if (rsiConsecutiveUpEl) rsiConsecutiveUpEl.textContent = rsiConsecutiveUp;

    // 更新RSI状态
    const rsiStatusEl = document.getElementById('rsiPureStatus');
    if (rsiStatusEl) {
        rsiStatusEl.textContent = _getRsiStatus(rsi, rsiZone, rsiDirection);
        rsiStatusEl.className = 'indicator-value indicator-status ' + _getRsiStatusClass(rsi);
    }

    // 更新仓位说明
    const positionReasonEl = document.getElementById('rsiPurePositionReason');
    if (positionReasonEl) positionReasonEl.textContent = positionReason;
}

// RSI辅助函数
function _formatRsiZone(zone) {
    const zoneMap = {
        'DEEP_OVERSOLD': '极度超卖(<20)',
        'OVERSOLD': '超卖(20-30)',
        'WEAK': '弱势(30-50)',
        'NEUTRAL': '中性(50-59)',
        'STRONG': '强势(59-80)',
        'OVERBOUGHT': '超买(80-90)',
        'EXTREME': '极端(>90)'
    };
    return zoneMap[zone] || zone;
}

function _getRsiZoneClass(zone) {
    const classMap = {
        'DEEP_OVERSOLD': 'zone-deep-oversold',
        'OVERSOLD': 'zone-oversold',
        'WEAK': 'zone-weak',
        'NEUTRAL': 'zone-neutral',
        'STRONG': 'zone-strong',
        'OVERBOUGHT': 'zone-overbought',
        'EXTREME': 'zone-extreme'
    };
    return classMap[zone] || '';
}

function _formatRsiDirection(direction) {
    const dirMap = {
        'UP': '↑ 向上',
        'DOWN': '↓ 向下',
        'FLAT': '→ 走平'
    };
    return dirMap[direction] || direction;
}

function _getRsiDirectionClass(direction) {
    const classMap = {
        'UP': 'direction-up',
        'DOWN': 'direction-down',
        'FLAT': 'direction-flat'
    };
    return classMap[direction] || '';
}

function _getRsiStatus(rsi, zone, direction) {
    if (rsi >= 80) {
        return direction === 'DOWN' ? '超买拐头-警惕' : '严重超买';
    } else if (rsi >= 60) {
        return direction === 'UP' ? '健康上升' : '强势整理';
    } else if (rsi >= 50) {
        return '中性区域';
    } else if (rsi >= 30) {
        return direction === 'UP' ? '弱势修复' : '弱势下跌';
    } else if (rsi >= 20) {
        return direction === 'UP' ? '超卖反弹' : '超卖区域';
    } else {
        return direction === 'UP' ? '极度超卖-试错' : '极度超卖-观望';
    }
}

function _getRsiStatusClass(rsi) {
    if (rsi >= 80) return 'status-overbought';
    if (rsi >= 60) return 'status-strong';
    if (rsi >= 50) return 'status-neutral';
    if (rsi >= 30) return 'status-weak';
    if (rsi >= 20) return 'status-oversold';
    return 'status-deep-oversold';
}

/**
 * 更新RSI三线策略指标显示
 */
function updateRsiTripleLinesIndicators(latestData) {
    if (!latestData) return;

    const rsi1 = latestData.rsi1 || 0;
    const rsi2 = latestData.rsi2 || 0;
    const rsi3 = latestData.rsi3 || 0;
    const tripleAlignment = latestData.triple_alignment || '';
    const rsi1Direction = latestData.rsi1_direction || '';
    const rsi1ConsecutiveUp = latestData.rsi1_consecutive_up || 0;
    const positionReason = latestData.position_reason || '';

    // 复用纯RSI的更新逻辑，但显示三线数据
    const rsiValueEl = document.getElementById('rsiPureValue');
    if (rsiValueEl) rsiValueEl.textContent = `RSI1:${rsi1.toFixed(1)} RSI2:${rsi2.toFixed(1)} RSI3:${rsi3.toFixed(1)}`;

    // 更新RSI区间（使用RSI1）
    const rsiZoneEl = document.getElementById('rsiPureZone');
    if (rsiZoneEl) {
        const rsiZone = _getRsi1Zone(rsi1);
        rsiZoneEl.textContent = rsiZone.text;
        rsiZoneEl.className = 'indicator-value indicator-zone ' + rsiZone.class;
    }

    // 更新RSI方向
    const rsiDirEl = document.getElementById('rsiPureDirection');
    if (rsiDirEl) {
        rsiDirEl.textContent = _formatRsiDirection(rsi1Direction);
        rsiDirEl.className = 'indicator-value indicator-direction ' + _getRsiDirectionClass(rsi1Direction);
    }

    // 更新连续向上天数
    const rsiConsecutiveUpEl = document.getElementById('rsiPureConsecutiveUp');
    if (rsiConsecutiveUpEl) rsiConsecutiveUpEl.textContent = rsi1ConsecutiveUp;

    // 更新RSI状态（显示排列）
    const rsiStatusEl = document.getElementById('rsiPureStatus');
    if (rsiStatusEl) {
        rsiStatusEl.textContent = _getRsiTripleLinesStatus(rsi1, tripleAlignment, rsi1Direction);
        rsiStatusEl.className = 'indicator-value indicator-status ' + _getRsiTripleLinesStatusClass(tripleAlignment, rsi1);
    }

    // 更新仓位说明
    const positionReasonEl = document.getElementById('rsiPurePositionReason');
    if (positionReasonEl) positionReasonEl.textContent = positionReason;
}

// RSI三线辅助函数
function _getRsi1Zone(rsi1) {
    if (rsi1 < 20) return { text: '极度超卖(<20)', class: 'zone-deep-oversold' };
    if (rsi1 < 30) return { text: '超卖(20-30)', class: 'zone-oversold' };
    if (rsi1 < 50) return { text: '弱势(30-50)', class: 'zone-weak' };
    if (rsi1 < 59) return { text: '中性(50-59)', class: 'zone-neutral' };
    if (rsi1 < 80) return { text: '强势(59-80)', class: 'zone-strong' };
    if (rsi1 < 90) return { text: '超买(80-90)', class: 'zone-overbought' };
    return { text: '极端(>90)', class: 'zone-extreme' };
}

function _getRsiTripleLinesStatus(rsi1, tripleAlignment, rsi1Direction) {
    if (tripleAlignment === 'BULLISH') {
        return '多头排列';
    } else if (tripleAlignment === 'BEARISH') {
        return '空头排列';
    } else if (tripleAlignment === 'GLUED') {
        return '三线黏合';
    } else if (rsi1 >= 80) {
        return rsi1Direction === 'DOWN' ? '超买拐头-警惕' : '严重超买';
    } else if (rsi1 >= 60) {
        return rsi1Direction === 'UP' ? '健康上升' : '强势整理';
    } else if (rsi1 >= 50) {
        return '中性区域';
    } else if (rsi1 >= 30) {
        return rsi1Direction === 'UP' ? '弱势修复' : '弱势下跌';
    } else if (rsi1 >= 20) {
        return rsi1Direction === 'UP' ? '超卖反弹' : '超卖区域';
    } else {
        return rsi1Direction === 'UP' ? '极度超卖-试错' : '极度超卖-观望';
    }
}

function _getRsiTripleLinesStatusClass(tripleAlignment, rsi1) {
    if (tripleAlignment === 'BULLISH') return 'status-strong';
    if (tripleAlignment === 'BEARISH') return 'status-deep-oversold';
    if (tripleAlignment === 'GLUED') return 'status-neutral';
    if (rsi1 >= 80) return 'status-overbought';
    if (rsi1 >= 60) return 'status-strong';
    if (rsi1 >= 50) return 'status-neutral';
    if (rsi1 >= 30) return 'status-weak';
    if (rsi1 >= 20) return 'status-oversold';
    return 'status-deep-oversold';
}

/**
 * 更新回测指标
 */
function updateMetrics(metrics) {
    if (!metrics) return;

    const totalReturnEl = document.getElementById('totalReturn');
    const totalReturn = metrics.total_return_pct !== undefined ? metrics.total_return_pct : 0;
    totalReturnEl.textContent = totalReturn.toFixed(2) + '%';
    totalReturnEl.className = `metric-value ${totalReturn >= 0 ? 'positive' : 'negative'}`;

    const benchmarkReturnEl = document.getElementById('benchmarkReturn');
    const benchmarkReturn = metrics.buy_hold_return_pct !== undefined ? metrics.buy_hold_return_pct :
                           (metrics.buy_hold_return !== undefined ? (metrics.buy_hold_return / 20 * 100) : 0);
    benchmarkReturnEl.textContent = benchmarkReturn.toFixed(2) + '%';
    benchmarkReturnEl.className = `metric-value ${benchmarkReturn >= 0 ? 'positive' : 'negative'}`;

    const tradeCountEl = document.getElementById('tradeCount');
    tradeCountEl.textContent = metrics.trades || metrics.total_trades || 0;

    const winRateEl = document.getElementById('winRate');
    const winRate = metrics.win_rate !== undefined ? metrics.win_rate : 0;
    winRateEl.textContent = (winRate * 100).toFixed(1) + '%';
    winRateEl.className = `metric-value ${winRate >= 0.5 ? 'positive' : 'negative'}`;

    const maxDrawdownEl = document.getElementById('maxDrawdown');
    const maxDrawdown = metrics.max_drawdown !== undefined ? metrics.max_drawdown : 0;
    maxDrawdownEl.textContent = (maxDrawdown * 100).toFixed(2) + '%';
    maxDrawdownEl.className = 'metric-value negative';

    const sharpeRatioEl = document.getElementById('sharpeRatio');
    const sharpeRatio = metrics.sharpe_ratio !== undefined ? metrics.sharpe_ratio : 0;
    sharpeRatioEl.textContent = sharpeRatio.toFixed(2);
    sharpeRatioEl.className = `metric-value ${sharpeRatio >= 1 ? 'positive' : 'negative'}`;
}

/**
 * 加载回测数据
 */
async function loadBacktestData(etfCode, strategy) {
    try {
        const startDate = getBacktestStartDate();
        const response = await fetch(`${API_BASE}/macd/backtest/watchlist/${etfCode}?start_date=${startDate}&strategy=${strategy}`);
        const result = await response.json();

        if (!result.success) {
            showError(result.message);
            return;
        }

        const data = result.data;
        renderBacktestChart(data);
        renderTrades(data);

        // 不再自动加载收益情况页面（避免性能问题）
        // 用户需要手动点击"加载收益数据"按钮

        // 对于RSI+MACD+KDJ三指标策略、纯RSI策略和RSI三线策略，绘制仓位历史图表
        if (strategy === 'rsi_macd_kdj_triple' || strategy === 'pure_rsi' || strategy === 'rsi_triple_lines') {
            renderPositionHistoryChart(data);
        }

        // 加载K线数据
        await loadKlineData(etfCode, strategy);

    } catch (error) {
        console.error('Failed to load backtest:', error);
        showError('加载回测数据失败');
    }
}

/**
 * 渲染回测图表
 */
function renderBacktestChart(data) {
    const chartDom = document.getElementById('backtestChart');

    if (backtestChart) {
        backtestChart.dispose();
    }

    backtestChart = echarts.init(chartDom);

    // 计算初始资金（用于计算收益率）
    const initialCapital = data.backtest_summary?.initial_capital || 2000;

    // 将收益金额转换为收益率百分比
    const returnPctData = data.strategy_values.map(v => (v / initialCapital) * 100);

    // 计算股票价格的初始值和范围，用于对齐右Y轴
    const initialPrice = data.prices[0];
    const minPrice = Math.min(...data.prices);
    const maxPrice = Math.max(...data.prices);

    // 计算价格变化的百分比范围（相对于初始价格）
    const minPricePct = ((minPrice - initialPrice) / initialPrice) * 100;
    const maxPricePct = ((maxPrice - initialPrice) / initialPrice) * 100;

    // 计算策略收益率的最小最大值
    const minStrategyPct = Math.min(...returnPctData);
    const maxStrategyPct = Math.max(...returnPctData);

    // 右Y轴范围取两者的并集，确保能容纳所有数据
    const yAxisRightMin = Math.min(minPricePct, minStrategyPct);
    const yAxisRightMax = Math.max(maxPricePct, maxStrategyPct);

    // 添加一些边距
    const returnMargin = (yAxisRightMax - yAxisRightMin) * 0.1 || 10;

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                animation: false,
                label: {
                    backgroundColor: '#777',
                    show: true
                },
                z: 100  // 确保十字准星在顶层
            },
            enterable: false,  // 禁止鼠标进入tooltip
            confine: true,     // 限制tooltip在图表区域内
            hideDelay: 0,      // 鼠标移开立即隐藏
            transitionDuration: 0.1,  // 缩短动画时间
            formatter: function(params) {
                // 只显示第一个系列（股票价格）的数据，避免卡顿
                const date = params[0].axisValue;
                let html = `<strong>${date}</strong><br/>`;

                // 找到股票价格
                const priceParam = params.find(p => p.seriesName === '股票价格');
                if (priceParam) {
                    const changePct = ((priceParam.value - initialPrice) / initialPrice) * 100;
                    const sign = changePct >= 0 ? '+' : '';
                    html += `${priceParam.marker} 价格: ¥${priceParam.value.toFixed(3)} (${sign}${changePct.toFixed(2)}%)<br/>`;
                }

                // 找到策略收益率
                const strategyParam = params.find(p => p.seriesName === '策略收益率');
                if (strategyParam) {
                    html += `${strategyParam.marker} 策略收益率: ${strategyParam.value.toFixed(2)}%`;
                }

                return html;
            }
        },
        legend: {
            data: ['股票价格', '策略收益率'],
            top: 10
        },
        grid: {
            left: '60px',
            right: '80px',
            top: '60px',
            bottom: '100px'  // 增加底部空间给dataZoom
        },
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: 0,
                start: 0,
                end: 100,
                zoomOnMouseWheel: true,  // 启用鼠标滚轮缩放
                moveOnMouseMove: true,   // 启用鼠标拖动平移
                moveOnMouseWheel: false
            },
            {
                show: true,
                xAxisIndex: 0,
                type: 'slider',
                top: '90%',
                start: 0,
                end: 100,
                height: 20,
                borderColor: '#ddd',
                textStyle: { color: '#666' },
                handleStyle: {
                    color: '#667eea',
                    borderColor: '#667eea'
                },
                dataBackground: {
                    areaStyle: { color: '#f0f4ff' }
                },
                selectedDataBackground: {
                    areaStyle: { color: 'rgba(102, 126, 234, 0.2)' }
                }
            }
        ],
        xAxis: {
            type: 'category',
            data: data.dates,
            boundaryGap: false,
            axisLine: { onZero: false },
            splitLine: { show: false }
        },
        yAxis: [
            {
                type: 'value',
                name: '价格',
                position: 'left',
                scale: true,
                splitLine: { show: true, lineStyle: { type: 'dashed', opacity: 0.3 } },
                axisLabel: {
                    formatter: function(value) {
                        const changePct = ((value - initialPrice) / initialPrice) * 100;
                        const sign = changePct >= 0 ? '+' : '';
                        return `¥${value.toFixed(3)}\n(${sign}${changePct.toFixed(1)}%)`;
                    }
                }
            },
            {
                type: 'value',
                name: '收益率',
                position: 'right',
                min: yAxisRightMin - returnMargin,
                max: yAxisRightMax + returnMargin,
                splitLine: { show: false },
                axisLabel: {
                    formatter: '{value}%'
                }
            }
        ],
        series: [
            {
                name: '股票价格',
                type: 'line',
                data: data.prices,
                smooth: true,
                showSymbol: false,
                lineStyle: { color: '#2196F3', width: 1.5 },
                itemStyle: { color: '#2196F3' },
                sampling: 'lttb',  // 降低采样率，提升性能
                progressive: 200,  // 渐进式渲染
                z: 1
            },
            {
                name: '策略收益率',
                type: 'line',
                yAxisIndex: 1,
                data: returnPctData,
                smooth: true,
                showSymbol: false,
                lineStyle: { color: '#999', width: 1.5, type: 'dashed' },
                itemStyle: { color: '#999' },
                sampling: 'lttb',  // 降低采样率，提升性能
                progressive: 200,  // 渐进式渲染
                z: 0
            },
            {
                name: '买入',
                type: 'scatter',
                data: data.buy_signals.map(s => {
                    const index = data.dates.indexOf(s.date);
                    return index >= 0 ? [index, s.price] : null;
                }).filter(x => x !== null),
                symbol: 'triangle',
                symbolSize: 8,
                itemStyle: { color: '#F44336' },
                z: 2,
                progressive: 100,  // 渐进式渲染
                large: true,       // 大数据量优化
                tooltip: {
                    formatter: function(params) {
                        const signal = data.buy_signals.find(s => s.date === data.dates[params.value[0]]);
                        return `${params.value[0]}<br/>买入: ¥${params.value[1].toFixed(3)}<br/>仓位: ${signal?.positions || 0}个`;
                    }
                }
            },
            {
                name: '卖出',
                type: 'scatter',
                data: data.sell_signals.map(s => {
                    const index = data.dates.indexOf(s.date);
                    return index >= 0 ? [index, s.price] : null;
                }).filter(x => x !== null),
                symbol: 'triangle',
                symbolRotate: 180,
                symbolSize: 8,
                itemStyle: { color: '#4CAF50' },
                z: 2,
                progressive: 100,  // 渐进式渲染
                large: true,       // 大数据量优化
                tooltip: {
                    formatter: function(params) {
                        const signal = data.sell_signals.find(s => s.date === data.dates[params.value[0]]);
                        return `${params.value[0]}<br/>卖出: ¥${params.value[1].toFixed(3)}<br/>仓位: ${signal?.positions_closed || 0}个`;
                    }
                }
            }
        ]
    };

    // 添加性能优化配置
    backtestChart.setOption(option, {
        notMerge: true,
        lazyUpdate: true,
        silent: false
    });

    window.addEventListener('resize', function() {
        backtestChart.resize();
    });
}

/**
 * 渲染交易记录
 */
function renderTrades(data) {
    const container = document.getElementById('tradesList');
    const trades = [
        ...data.buy_signals.map(t => ({...t, type: 'buy'})),
        ...data.sell_signals.map(t => ({...t, type: 'sell'}))
    ];

    // 转换日期格式：20260217 → 2026-02-17
    trades.forEach(trade => {
        if (trade.date && /^\d{8}$/.test(trade.date)) {
            const y = trade.date.substring(0, 4);
            const m = trade.date.substring(4, 6);
            const d = trade.date.substring(6, 8);
            trade.dateFormatted = `${y}-${m}-${d}`;
        } else {
            trade.dateFormatted = trade.date;
        }
    });

    // 按时间降序排序（最新的在前）
    trades.sort((a, b) => new Date(b.dateFormatted) - new Date(a.dateFormatted));

    // 只显示最近20条交易记录
    const recentTrades = trades.slice(0, 20);

    if (recentTrades.length === 0) {
        container.innerHTML = '<p class="no-trades">暂无交易记录</p>';
        return;
    }

    container.innerHTML = recentTrades.map(trade => {
        // 对于买入信号显示positions，对于卖出信号显示positions_closed
        const positionsDisplay = trade.positions ? trade.positions :
                                 (trade.positions_closed ? trade.positions_closed : '');
        const positionsText = positionsDisplay ? `${positionsDisplay}个仓位` : '';

        return `
        <div class="trade-item ${trade.type}">
            <div class="trade-date">${trade.dateFormatted}</div>
            <div class="trade-type">${trade.type === 'buy' ? '买入' : '卖出'} ${trade.reason ? `(${trade.reason})` : ''}</div>
            <div class="trade-price">¥${trade.price.toFixed(3)}</div>
            ${positionsText ? `<div class="trade-positions">${positionsText}</div>` : ''}
        </div>
        `;
    }).join('');
}

/**
 * 渲染仓位历史图表（用于RSI+MACD+KDJ三指标策略）
 */
function renderPositionHistoryChart(data) {
    const chartDom = document.getElementById('positionHistoryChart');
    if (!chartDom) return;

    if (positionHistoryChart) {
        positionHistoryChart.dispose();
    }

    positionHistoryChart = echarts.init(chartDom);

    // 从performance数据中提取仓位历史
    // 注意：data中可能没有performance，需要从API获取
    // 如果API返回的数据中没有position_units，我们暂时跳过
    if (!data.performance || data.performance.length === 0) {
        chartDom.innerHTML = '<p class="no-trades">暂无仓位数据</p>';
        return;
    }

    const performance = data.performance;
    const dates = performance.map(p => {
        // 转换日期格式
        const date = p.date;
        if (date && /^\d{8}$/.test(date)) {
            const y = date.substring(0, 4);
            const m = date.substring(4, 6);
            const d = date.substring(6, 8);
            return `${y}-${m}-${d}`;
        }
        return date;
    });
    const positions = performance.map(p => p.positions_used || 0);
    const prices = performance.map(p => p.price || 0);

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            formatter: function(params) {
                const date = params[0].axisValue;
                let html = `<strong>${date}</strong><br/>`;
                params.forEach(param => {
                    html += `${param.marker} ${param.seriesName}: ${param.seriesName === '仓位(成)' ? param.value : '¥' + param.value.toFixed(3)}<br/>`;
                });
                return html;
            }
        },
        legend: {
            data: ['仓位(成)', '价格'],
            bottom: 0
        },
        grid: {
            left: '3%',
            right: '3%',
            bottom: '15%',
            top: '10%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            data: dates,
            boundaryGap: false
        },
        yAxis: [
            {
                type: 'value',
                name: '仓位(成)',
                min: 0,
                max: 10,
                interval: 2,
                axisLabel: { formatter: '{value}成' }
            },
            {
                type: 'value',
                name: '价格',
                axisLabel: { formatter: '¥{value}' }
            }
        ],
        series: [
            {
                name: '仓位(成)',
                type: 'line',
                data: positions,
                smooth: true,
                itemStyle: { color: '#5470c6' },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(84, 112, 198, 0.3)' },
                            { offset: 1, color: 'rgba(84, 112, 198, 0.05)' }
                        ]
                    }
                }
            },
            {
                name: '价格',
                type: 'line',
                yAxisIndex: 1,
                data: prices,
                smooth: true,
                itemStyle: { color: '#91cc75' }
            }
        ]
    };

    positionHistoryChart.setOption(option);
}

/**
 * 打开添加ETF弹窗
 */
function openAddEtfModal() {
    document.getElementById('addEtfModal').classList.add('active');
    document.getElementById('etfCodeInput').value = '';
    document.getElementById('etfCodeInput').focus();
    updateAddModalNote('macd_aggressive');
}

/**
 * 关闭添加ETF弹窗
 */
function closeAddEtfModal() {
    document.getElementById('addEtfModal').classList.remove('active');
}

/**
 * 更新添加弹窗的提示信息
 */
function updateAddModalNote(strategy) {
    const noteEl = document.getElementById('addModalNote');
    const strategyNoteEl = document.getElementById('strategyNote_macd_kdj_discrete');

    // 隐藏所有策略特定说明
    if (strategyNoteEl) {
        strategyNoteEl.style.display = 'none';
    }

    if (strategy === 'macd_aggressive') {
        noteEl.innerHTML = '<p>💡 提示：MACD激进策略无需额外文件，可直接使用</p>';
    } else if (strategy === 'optimized_t_trading') {
        noteEl.innerHTML = '<p>✨ 推荐：优化做T策略，宽松止损-20% + 严格买入过滤 + 分批止盈</p>';
    } else if (strategy === 'macd_kdj') {
        noteEl.innerHTML = '<p>🎯 MACD+KDJ融合：MACD择时 + KDJ仓位控制 + 风控减仓</p>';
    } else if (strategy === 'macd_kdj_discrete') {
        noteEl.innerHTML = '<p>🎯 MACD+KDJ离散仓位：MACD判断趋势 + KDJ确定0-10成仓位</p>';
        // 显示策略说明div
        if (strategyNoteEl) {
            strategyNoteEl.style.display = 'block';
        }
    } else if (strategy === 'rsi_macd_kdj_triple') {
        noteEl.innerHTML = '<p>🎯 三指标共振优化版：MA60大趋势过滤 + RSI(14) + MACD红柱放大 + KDJ(14,3,3)，避免单边下跌反复抄底</p>';
    } else if (strategy === 'multifactor') {
        noteEl.innerHTML = '<p>⚠️ 注意：多因子策略需要权重文件，请先运行优化脚本生成</p>';
    } else {
        noteEl.innerHTML = '<p>ℹ️ 提示：选择合适的策略添加到自选</p>';
    }
}

/**
 * 确认添加ETF
 */
async function confirmAddEtf() {
    const etfCode = document.getElementById('etfCodeInput').value.trim();
    const strategy = document.getElementById('addStrategySelect').value;

    if (!etfCode) {
        showError('请输入ETF代码');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/watchlist/add`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ etf_code: etfCode, strategy: strategy })
        });

        const result = await response.json();

        if (result.success) {
            showSuccess(result.message);
            closeAddEtfModal();
            loadWatchlist();
        } else {
            showError(result.message);
        }
    } catch (error) {
        console.error('Failed to add ETF:', error);
        showError('添加失败');
    }
}

/**
 * 更新策略
 */
async function updateStrategy() {
    if (!currentEtfCode) return;

    const newStrategy = document.getElementById('strategySelect').value;
    const statusEl = document.getElementById('strategyStatus');

    if (newStrategy === currentStrategy) {
        statusEl.textContent = '策略未改变';
        statusEl.className = 'strategy-status warning';
        return;
    }

    statusEl.textContent = '更新中...';
    statusEl.className = 'strategy-status loading';

    try {
        const response = await fetch(`${API_BASE}/watchlist/${currentEtfCode}/strategy`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ strategy: newStrategy })
        });

        const result = await response.json();

        if (result.success) {
            statusEl.textContent = '✓ 已更新';
            statusEl.className = 'strategy-status success';
            currentStrategy = newStrategy;

            // 重新加载数据
            await Promise.all([
                loadRealtimeSignal(currentEtfCode, newStrategy),
                loadBacktestData(currentEtfCode, newStrategy)
            ]);

            // 更新面板显示
            updatePanelsByStrategy(newStrategy);

            // 重新加载列表以更新策略标签
            loadWatchlist();

            setTimeout(() => {
                statusEl.textContent = '';
            }, 2000);
        } else {
            statusEl.textContent = '✗ 失败';
            statusEl.className = 'strategy-status error';
            showError(result.message);
        }
    } catch (error) {
        console.error('Failed to update strategy:', error);
        statusEl.textContent = '✗ 错误';
        statusEl.className = 'strategy-status error';
        showError('更新策略失败');
    }
}

/**
 * 保存高级设置
 */
async function saveSettings() {
    if (!currentEtfCode) {
        showError('请先选择一个ETF');
        return;
    }

    const initialCapital = parseFloat(document.getElementById('initialCapital').value);
    const totalPositions = parseInt(document.getElementById('totalPositions').value);
    const buildPositionDate = document.getElementById('buildPositionDate').value;
    const statusEl = document.getElementById('settingsStatus');

    // 验证输入
    if (initialCapital < 1000 || initialCapital > 1000000) {
        statusEl.textContent = '✗ 初始资金必须在1000-1000000之间';
        statusEl.className = 'settings-status error';
        return;
    }

    if (totalPositions < 1 || totalPositions > 50) {
        statusEl.textContent = '✗ 仓位数必须在1-50之间';
        statusEl.className = 'settings-status error';
        return;
    }

    // 转换日期格式 YYYY-MM-DD -> YYYYMMDD
    let buildDateFormatted = null;
    if (buildPositionDate) {
        buildDateFormatted = buildPositionDate.replace(/-/g, '');
    }

    statusEl.textContent = '保存中...';
    statusEl.className = 'settings-status loading';

    try {
        const response = await fetch(`${API_BASE}/watchlist/${currentEtfCode}/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                initial_capital: initialCapital,
                total_positions: totalPositions,
                build_position_date: buildDateFormatted
            })
        });

        const result = await response.json();

        if (result.success) {
            statusEl.textContent = '✓ 已保存';
            statusEl.className = 'settings-status success';

            // 重新加载数据以应用新设置
            await Promise.all([
                loadRealtimeSignal(currentEtfCode, currentStrategy),
                loadBacktestData(currentEtfCode, currentStrategy)
            ]);

            setTimeout(() => {
                statusEl.textContent = '';
            }, 2000);
        } else {
            statusEl.textContent = '✗ 失败';
            statusEl.className = 'settings-status error';
            showError(result.message);
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
        statusEl.textContent = '✗ 错误';
        statusEl.className = 'settings-status error';
        showError('保存设置失败');
    }
}

/**
 * 加载ETF的高级设置
 */
function loadEtfSettings(etfCode) {
    const etf = watchlistData.etfs.find(e => e.code === etfCode);
    if (!etf) return;

    // 设置初始资金
    const initialCapital = etf.initial_capital || 2000;
    document.getElementById('initialCapital').value = initialCapital;

    // 设置总仓位
    const totalPositions = etf.total_positions || 10;
    document.getElementById('totalPositions').value = totalPositions;

    // 设置建仓日期
    const buildDate = etf.build_position_date;
    if (buildDate) {
        // 转换格式 YYYYMMDD -> YYYY-MM-DD
        const formattedDate = `${buildDate.slice(0, 4)}-${buildDate.slice(4, 6)}-${buildDate.slice(6, 8)}`;
        document.getElementById('buildPositionDate').value = formattedDate;
    } else {
        // 默认设置为空，让用户自己选择
        document.getElementById('buildPositionDate').value = '';
    }
}

/**
 * 删除ETF
 */
async function removeEtf(etfCode) {
    if (!confirm(`确定要删除 ${etfCode} 吗？`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/watchlist/${etfCode}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showSuccess(result.message);

            if (currentEtfCode === etfCode) {
                currentEtfCode = null;
                currentStrategy = null;
                document.getElementById('emptyState').style.display = 'block';
                document.getElementById('strategySelector').style.display = 'none';
                document.getElementById('realtimeCard').style.display = 'none';
                document.getElementById('chartSection').style.display = 'none';
                document.getElementById('detailsSection').style.display = 'none';
            }

            loadWatchlist();
        } else {
            showError(result.message);
        }
    } catch (error) {
        console.error('Failed to remove ETF:', error);
        showError('删除失败');
    }
}

/**
 * 加载K线数据并渲染图表
 */
async function loadKlineData(etfCode, strategy) {
    try {
        const startDate = getBacktestStartDate();
        // 使用新的K线数据API获取OHLCV数据
        const response = await fetch(`${API_BASE}/watchlist/${etfCode}/kline-data?start_date=${startDate}`);
        const result = await response.json();

        if (!result.success) {
            console.error('Failed to load kline data:', result);
            return;
        }

        const klineData = result.data;
        console.log('K线OHLCV数据:', {
            dates: klineData.dates.length,
            open: klineData.open.length,
            high: klineData.high.length,
            low: klineData.low.length,
            close: klineData.close.length,
            volume: klineData.volume.length
        });

        renderKlineChart(klineData, etfCode);

    } catch (error) {
        console.error('Failed to load kline data:', error);
    }
}

/**
 * 渲染K线图表（包含K线、均线、成交量、MACD、KDJ）
 */
function renderKlineChart(klineData, etfCode) {
    const chartDom = document.getElementById('klineChart');

    if (klineChart) {
        klineChart.dispose();
    }

    klineChart = echarts.init(chartDom);

    // 使用真实的OHLCV数据
    const dates = klineData.dates;
    const opens = klineData.open;
    const highs = klineData.high;
    const lows = klineData.low;
    const closes = klineData.close;
    const volumes = klineData.volume;

    console.log('K线数据长度:', dates.length);
    console.log('成交量数据长度:', volumes.length);
    console.log('OHLC样本:', {
        open: opens[0], high: highs[0], low: lows[0], close: closes[0], volume: volumes[0]
    });

    // 计算均线
    const ma5 = calculateMA(closes, 5);
    const ma10 = calculateMA(closes, 10);
    const ma20 = calculateMA(closes, 20);
    const ma60 = calculateMA(closes, 60);

    // 计算MACD
    const macdData = calculateMACD(closes, 12, 26, 9);

    // 计算KDJ
    const kdjData = calculateKDJ(highs, lows, closes, 9, 3, 3);

    // 格式化K线数据
    const candlestickData = formatCandlestickData(opens, closes, lows, highs);

    // 为成交量添加颜色（根据涨跌）
    const volumeData = volumes.map((vol, i) => {
        const isUp = i === 0 ? true : closes[i] >= closes[i - 1];
        return {
            value: vol,
            itemStyle: { color: isUp ? '#ef5350' : '#26a69a' }
        };
    });

    // MACD柱状图数据（带颜色）
    const macdBarData = macdData.macd.map((val, i) => ({
        value: val,
        itemStyle: { color: val >= 0 ? '#ef5350' : '#26a69a' }
    }));

    // K线图 + 成交量 + MACD + KDJ（4个grid）
    const option = {
        animation: false,
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow',
                lineStyle: {
                    color: '#000',
                    width: 1.5
                },
                link: {
                    xAxisIndex: [0, 1, 2, 3]
                }
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#ccc',
            borderWidth: 1,
            textStyle: {
                fontSize: 11
            },
            formatter: function(params) {
                // 获取当前日期的索引
                const dataIndex = params[0].dataIndex;
                const date = dates[dataIndex];

                let html = `<div style="font-weight:bold;margin-bottom:5px;">${date}</div>`;

                // 1. K线数据
                const open = opens[dataIndex];
                const close = closes[dataIndex];
                const high = highs[dataIndex];
                const low = lows[dataIndex];
                html += `<div style="margin:3px 0;"><span style="color:#667eea">●</span> <b>K线</b>: 开${open.toFixed(4)} 高${high.toFixed(4)} 低${low.toFixed(4)} 收${close.toFixed(4)}</div>`;

                // 2. 均线
                html += `<div style="margin:3px 0;"><span style="color:#FF6B6B">●</span> <b>均线</b>: `;
                html += `MA5=${ma5[dataIndex] === null ? '-' : ma5[dataIndex].toFixed(4)} `;
                html += `MA10=${ma10[dataIndex] === null ? '-' : ma10[dataIndex].toFixed(4)} `;
                html += `MA20=${ma20[dataIndex] === null ? '-' : ma20[dataIndex].toFixed(4)} `;
                html += `MA60=${ma60[dataIndex] === null ? '-' : ma60[dataIndex].toFixed(4)}</div>`;

                // 3. 成交量
                const vol = volumes[dataIndex];
                html += `<div style="margin:3px 0;"><span style="color:#999999">●</span> <b>成交量</b>: ${vol.toLocaleString()} 手</div>`;

                // 4. MACD
                html += `<div style="margin:3px 0;"><span style="color:#FF6B6B">●</span> <b>MACD</b>: `;
                html += `DIF=${macdData.dif[dataIndex].toFixed(6)} `;
                html += `DEA=${macdData.dea[dataIndex].toFixed(6)} `;
                const macdVal = macdData.macd[dataIndex];
                html += `MACD=${macdVal.toFixed(6)}</div>`;

                // 5. KDJ
                html += `<div style="margin:3px 0;"><span style="color:#2196F3">●</span> <b>KDJ</b>: `;
                html += `K=${kdjData.k[dataIndex].toFixed(2)} `;
                html += `D=${kdjData.d[dataIndex].toFixed(2)} `;
                html += `J=${kdjData.j[dataIndex].toFixed(2)}</div>`;

                return html;
            }
        },
        title: {
            text: `${etfCode} K线分析 (最近${dates.length}个交易日)`,
            left: 'center',
            textStyle: { fontSize: 14 }
        },
        legend: {
            data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60', '成交量', 'DIF', 'DEA', 'MACD', 'K', 'D', 'J'],
            top: 25,
            textStyle: { fontSize: 10 },
            itemWidth: 15,
            itemHeight: 10
        },
        grid: [
            {
                id: 'gridKline',
                left: '8%',
                right: '8%',
                top: 70,
                height: 200
            },
            {
                id: 'gridVolume',
                left: '8%',
                right: '8%',
                top: 300,
                height: 60
            },
            {
                id: 'gridMACD',
                left: '8%',
                right: '8%',
                top: 380,
                height: 80
            },
            {
                id: 'gridKDJ',
                left: '8%',
                right: '8%',
                top: 480,
                height: 80
            }
        ],
        xAxis: [
            {
                id: 'xAxisKline',
                type: 'category',
                data: dates,
                gridIndex: 0,
                axisLabel: { show: false },
                axisLine: { onZero: false },
                axisPointer: {
                    type: 'shadow',
                    z: 100,
                    label: { show: false },
                    lineStyle: {
                        color: '#000',
                        width: 1.5
                    }
                }
            },
            {
                id: 'xAxisVolume',
                type: 'category',
                data: dates,
                gridIndex: 1,
                axisLabel: { show: false },
                axisPointer: {
                    type: 'shadow',
                    z: 100,
                    label: { show: false },
                    lineStyle: {
                        color: '#000',
                        width: 1.5
                    }
                }
            },
            {
                id: 'xAxisMACD',
                type: 'category',
                data: dates,
                gridIndex: 2,
                axisLabel: { show: false },
                axisPointer: {
                    type: 'shadow',
                    z: 100,
                    label: { show: false },
                    lineStyle: {
                        color: '#000',
                        width: 1.5
                    }
                }
            },
            {
                id: 'xAxisKDJ',
                type: 'category',
                data: dates,
                gridIndex: 3,
                axisLabel: { show: true },
                axisPointer: {
                    type: 'shadow',
                    z: 100,
                    label: { show: false },
                    lineStyle: {
                        color: '#000',
                        width: 1.5
                    }
                }
            }
        ],
        yAxis: [
            {
                id: 'yAxisKline',
                scale: true,
                gridIndex: 0,
                splitLine: { show: true, lineStyle: { type: 'dashed', opacity: 0.3 } }
            },
            {
                id: 'yAxisVolume',
                scale: true,
                gridIndex: 1,
                splitNumber: 2,
                axisLabel: { show: false },
                splitLine: { show: false }
            },
            {
                id: 'yAxisMACD',
                scale: true,
                gridIndex: 2,
                splitLine: { show: false },
                axisLabel: { show: false }
            },
            {
                id: 'yAxisKDJ',
                scale: true,
                gridIndex: 3,
                splitLine: { show: false },
                axisLabel: { show: false }
            }
        ],
        dataZoom: [
            {
                type: 'inside',
                xAxisIndex: [0, 1, 2, 3],
                start: 0,
                end: 100
            },
            {
                show: true,
                xAxisIndex: [0, 1, 2, 3],
                type: 'slider',
                top: '97%',
                start: 70,
                end: 100,
                height: 15
            }
        ],
        series: [
            {
                name: 'K线',
                type: 'candlestick',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: candlestickData,
                itemStyle: {
                    color: '#ef5350',
                    color0: '#26a69a',
                    borderColor: '#ef5350',
                    borderColor0: '#26a69a'
                }
            },
            {
                name: 'MA5',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: ma5,
                smooth: true,
                lineStyle: { opacity: 0.8, width: 1, color: '#FF6B6B' },
                showSymbol: false
            },
            {
                name: 'MA10',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: ma10,
                smooth: true,
                lineStyle: { opacity: 0.8, width: 1, color: '#4ECDC4' },
                showSymbol: false
            },
            {
                name: 'MA20',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: ma20,
                smooth: true,
                lineStyle: { opacity: 0.8, width: 1, color: '#FFE66D' },
                showSymbol: false
            },
            {
                name: 'MA60',
                type: 'line',
                xAxisIndex: 0,
                yAxisIndex: 0,
                data: ma60,
                smooth: true,
                lineStyle: { opacity: 0.8, width: 1, color: '#95E1D3' },
                showSymbol: false
            },
            {
                name: '成交量',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: volumeData
            },
            {
                name: 'DIF',
                type: 'line',
                xAxisIndex: 2,
                yAxisIndex: 2,
                data: macdData.dif,
                smooth: true,
                lineStyle: { color: '#FF6B6B', width: 1.5 },
                showSymbol: false
            },
            {
                name: 'DEA',
                type: 'line',
                xAxisIndex: 2,
                yAxisIndex: 2,
                data: macdData.dea,
                smooth: true,
                lineStyle: { color: '#4ECDC4', width: 1.5 },
                showSymbol: false
            },
            {
                name: 'MACD',
                type: 'bar',
                xAxisIndex: 2,
                yAxisIndex: 2,
                data: macdBarData
            },
            {
                name: 'K',
                type: 'line',
                xAxisIndex: 3,
                yAxisIndex: 3,
                data: kdjData.k,
                smooth: true,
                lineStyle: { color: '#2196F3', width: 1.5 },
                showSymbol: false
            },
            {
                name: 'D',
                type: 'line',
                xAxisIndex: 3,
                yAxisIndex: 3,
                data: kdjData.d,
                smooth: true,
                lineStyle: { color: '#FF9800', width: 1.5 },
                showSymbol: false
            },
            {
                name: 'J',
                type: 'line',
                xAxisIndex: 3,
                yAxisIndex: 3,
                data: kdjData.j,
                smooth: true,
                lineStyle: { color: '#9C27B0', width: 1.5, type: 'dashed' },
                showSymbol: false
            }
        ]
    };

    klineChart.setOption(option, {
        notMerge: true,
        lazyUpdate: true
    });

    // 显示K线图表区域
    document.getElementById('klineChartSection').style.display = 'block';

    // 响应式
    window.addEventListener('resize', function() {
        klineChart && klineChart.resize();
    });
}

/**
 * 计算移动平均线
 */
function calculateMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            result.push(null);  // ECharts handles null by not rendering the point
        } else {
            let sum = 0;
            for (let j = 0; j < period; j++) {
                sum += data[i - j];
            }
            result.push(sum / period);
        }
    }
    return result;
}

/**
 * 计算MACD指标
 */
function calculateMACD(data, shortPeriod, longPeriod, signalPeriod) {
    if (!data || data.length === 0) {
        console.warn('calculateMACD: Empty data array');
        return { dif: [], dea: [], macd: [] };
    }

    try {
        const emaShort = calculateEMA(data, shortPeriod);
        const emaLong = calculateEMA(data, longPeriod);

        const dif = emaShort.map((val, idx) => {
            const longVal = emaLong[idx];
            if (val !== null && val !== undefined && !isNaN(val) &&
                longVal !== null && longVal !== undefined && !isNaN(longVal)) {
                return val - longVal;
            }
            return 0;  // Return 0 instead of null to maintain array length
        });

        const dea = calculateEMA(dif, signalPeriod);

        const macd = dif.map((val, idx) => {
            const deaVal = dea[idx];
            if (deaVal !== null && deaVal !== undefined && !isNaN(deaVal)) {
                return val - deaVal;
            }
            return 0;  // Return 0 instead of null to maintain array length
        });

        return { dif, dea, macd };
    } catch (error) {
        console.error('Error in calculateMACD:', error);
        return { dif: [], dea: [], macd: [] };
    }
}

/**
 * 计算EMA指数移动平均
 */
function calculateEMA(data, period) {
    if (!data || data.length === 0) {
        console.warn('calculateEMA: Empty data array');
        return [];
    }

    const result = [];
    const k = 2 / (period + 1);

    // 第一个EMA值使用第一个数据点
    let ema = data[0];
    result.push(ema);

    for (let i = 1; i < data.length; i++) {
        const val = data[i];
        if (val !== null && val !== undefined && !isNaN(val)) {
            ema = val * k + ema * (1 - k);
            result.push(ema);
        } else {
            result.push(ema);
        }
    }

    return result;
}

/**
 * 计算KDJ指标
 */
function calculateKDJ(highs, lows, closes, n, m1, m2) {
    const k = [];
    const d = [];
    const j = [];

    for (let i = 0; i < closes.length; i++) {
        if (i < n - 1) {
            k.push(50);  // Use 50 as default initial value
            d.push(50);
            j.push(50);
        } else {
            // 计算RSV
            const highN = highs.slice(i - n + 1, i + 1);
            const lowN = lows.slice(i - n + 1, i + 1);
            const closeN = closes.slice(i - n + 1, i + 1);

            const highestHigh = Math.max(...highN);
            const lowestLow = Math.min(...lowN);

            // Avoid division by zero
            let rsv = 50;
            if (highestHigh !== lowestLow) {
                rsv = ((closes[i] - lowestLow) / (highestHigh - lowestLow)) * 100;
            }

            // 计算K值
            const prevK = k[i - 1] !== null && k[i - 1] !== undefined && !isNaN(k[i - 1]) ? k[i - 1] : 50;
            const currentK = (2 / 3) * rsv + (1 / 3) * prevK;
            k.push(currentK);

            // 计算D值
            const prevD = d[i - 1] !== null && d[i - 1] !== undefined && !isNaN(d[i - 1]) ? d[i - 1] : 50;
            const currentD = (2 / 3) * currentK + (1 / 3) * prevD;
            d.push(currentD);

            // 计算J值
            const currentJ = 3 * currentK - 2 * currentD;
            j.push(currentJ);
        }
    }

    return { k, d, j };
}

/**
 * 格式化K线数据
 */
function formatCandlestickData(opens, closes, lows, highs) {
    const result = [];
    for (let i = 0; i < opens.length; i++) {
        result.push([opens[i], closes[i], lows[i], highs[i]]);
    }
    return result;
}

/**
 * 显示错误消息
 */
function showError(message) {
    alert('✗ ' + message);
}

/**
 * 显示成功消息
 */
function showSuccess(message) {
    alert('✓ ' + message);
}

/**
 * 格式化货币
 */
function formatCurrency(value, withSign = false) {
    if (value === undefined || value === null || isNaN(value)) {
        value = 0;
    }
    const formatted = '¥' + Math.abs(value).toFixed(2);
    if (withSign && value >= 0) {
        return '+' + formatted;
    } else if (withSign && value < 0) {
        return '-' + formatted;
    } else {
        return formatted;
    }
}

/**
 * 显示权重状态
 */
function showWeightStatus(status) {
    let statusEl = document.getElementById('weightStatus');

    // 如果元素不存在，创建它
    if (!statusEl) {
        const strategySelector = document.getElementById('strategySelector');
        if (strategySelector) {
            const statusDiv = document.createElement('div');
            statusDiv.id = 'weightStatus';
            statusDiv.className = 'weight-status';
            statusDiv.style.cssText = `
                margin-top: 12px;
                padding: 10px 12px;
                border-radius: 6px;
                font-size: 13px;
                display: flex;
                align-items: center;
                justify-content: space-between;
            `;
            strategySelector.after(statusDiv);
            statusEl = statusDiv;
        }
    }

    if (!statusEl) return;

    // 根据状态设置样式和文本
    if (status.includes('优化完成') || status.includes('成功加载')) {
        statusEl.style.background = '#d4edda';
        statusEl.style.color = '#155724';
        statusEl.innerHTML = `
            <span>✓ ${status}</span>
            <span style="font-size: 11px; opacity: 0.8;">权重已优化</span>
        `;
    } else if (status.includes('后台重新优化')) {
        statusEl.style.background = '#fff3cd';
        statusEl.style.color = '#856404';
        statusEl.innerHTML = `
            <span>⏱ ${status}</span>
            <span style="font-size: 11px; opacity: 0.8;">后台运行中</span>
        `;
    } else if (status.includes('使用缓存') || status.includes('使用旧权重')) {
        statusEl.style.background = '#e2e3e5';
        statusEl.style.color = '#383d41';
        statusEl.innerHTML = `
            <span>ℹ ${status}</span>
            <span style="font-size: 11px; opacity: 0.8;">${status.includes('缓存') ? '已缓存' : '旧权重'}</span>
        `;
    } else {
        statusEl.style.background = '#f8d7da';
        statusEl.style.color = '#721c24';
        statusEl.innerHTML = `
            <span>⚠ ${status}</span>
            <span style="font-size: 11px; opacity: 0.8;">需要注意</span>
        `;
    }

    statusEl.style.display = 'flex';
}

/**
 * 隐藏权重状态
 */
function hideWeightStatus() {
    const statusEl = document.getElementById('weightStatus');
    if (statusEl) {
        statusEl.style.display = 'none';
    }
}

/**
 * 优化MACD参数
 */
async function optimizeMACDParams() {
    if (!currentEtfCode) {
        showError('请先选择一个ETF');
        return;
    }

    const btn = document.getElementById('optimizeParamsBtn');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">优化中...</span>';
    btn.disabled = true;

    // 显示进度提示
    showNotification('正在优化MACD参数，这可能需要15-30秒...', 'info');

    try {
        const response = await fetch(`${API_BASE}/macd/optimize-params/${currentEtfCode}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({lookback_days: 365})
        });

        const result = await response.json();

        if (result.success) {
            displayOptimizationResult(result);
            showNotification('参数优化完成！', 'success');

            // 自动保存优化后的参数
            const bestParams = result.optimization_result.best_params;
            await saveOptimizedParams(currentEtfCode, bestParams);
        } else {
            showError('参数优化失败: ' + result.message);
        }
    } catch (error) {
        console.error('Optimization error:', error);
        showError('优化请求失败');
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }
}

/**
 * 显示优化结果
 */
function displayOptimizationResult(result) {
    const optResult = result.optimization_result;

    // 保存优化后的参数和完整策略参数
    optimizedMacdParams = optResult.aggressive_params;

    // 填充参数值
    document.getElementById('optMacdFast').textContent = optResult.best_params.macd_fast;
    document.getElementById('optMacdSlow').textContent = optResult.best_params.macd_slow;
    document.getElementById('optMacdSignal').textContent = optResult.best_params.macd_signal;

    // 填充指标
    document.getElementById('optReturn').textContent = optResult.metrics.total_return_pct.toFixed(2) + '%';
    document.getElementById('optReturn').className = 'opt-highlight ' + (optResult.metrics.total_return_pct >= 0 ? 'positive' : 'negative');
    document.getElementById('optSharpe').textContent = optResult.metrics.sharpe_ratio.toFixed(2);
    document.getElementById('optDrawdown').textContent = optResult.metrics.max_drawdown_pct.toFixed(2) + '%';

    // 填充额外信息
    document.getElementById('optPeriod').textContent =
        `优化期间: ${optResult.data_period.start} 至 ${optResult.data_period.end} (${optResult.data_period.days}天)`;
    document.getElementById('optTrades').textContent =
        `交易次数: ${optResult.metrics.total_trades} | 胜率: ${(optResult.metrics.win_rate * 100).toFixed(1)}%`;

    // 显示面板
    document.getElementById('optimizationResultPanel').style.display = 'block';
}

/**
 * 显示通知消息
 */
function showNotification(message, type = 'info') {
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        background: ${type === 'success' ? '#d4edda' : type === 'error' ? '#f8d7da' : '#d1ecf1'};
        color: ${type === 'success' ? '#155724' : type === 'error' ? '#721c24' : '#0c5460'};
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 2000;
        animation: slideIn 0.3s ease-out;
        max-width: 350px;
    `;

    document.body.appendChild(notification);

    // 3秒后自动移除
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => {
            document.body.removeChild(notification);
        }, 300);
    }, 3000);
}

// 添加动画样式
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

/**
 * 加载并显示当前MACD参数
 */
async function loadAndDisplayMacdParams(etfCode) {
    try {
        // 从watchlist中获取该ETF的优化参数
        const etf = watchlistData.etfs.find(e => e.code === etfCode);

        if (etf && etf.optimized_macd_params) {
            // 使用优化后的参数
            currentMacdParams = etf.optimized_macd_params;
            updateParamsDisplay(currentMacdParams, true);
            document.getElementById('resetParamsBtn').style.display = 'flex';
        } else {
            // 使用默认参数
            currentMacdParams = {...DEFAULT_MACD_PARAMS};
            updateParamsDisplay(currentMacdParams, false);
            document.getElementById('resetParamsBtn').style.display = 'none';
        }
    } catch (error) {
        console.error('Failed to load MACD params:', error);
        currentMacdParams = {...DEFAULT_MACD_PARAMS};
        updateParamsDisplay(currentMacdParams, false);
    }
}

/**
 * 更新参数显示
 */
function updateParamsDisplay(params, isOptimized) {
    const displayEl = document.getElementById('currentParamsDisplay');
    displayEl.textContent = `Fast:${params.macd_fast} Slow:${params.macd_slow} Signal:${params.macd_signal}`;

    if (isOptimized) {
        displayEl.classList.add('optimized');
    } else {
        displayEl.classList.remove('optimized');
    }
}

/**
 * 保存优化后的参数到JSON
 */
async function saveOptimizedParams(etfCode, params) {
    try {
        const response = await fetch(`${API_BASE}/watchlist/${etfCode}/macd-params`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(params)
        });

        const result = await response.json();

        if (result.success) {
            currentMacdParams = params;
            updateParamsDisplay(params, true);
            document.getElementById('resetParamsBtn').style.display = 'flex';
            showNotification('优化参数已保存，正在重新回测...', 'success');

            // 先刷新 watchlist 数据，确保后续操作使用最新数据
            await loadWatchlist();

            // 重新加载回测数据以使用新的优化参数
            await Promise.all([
                loadRealtimeSignal(etfCode, currentStrategy),
                loadBacktestData(etfCode, currentStrategy)
            ]);

            return true;
        } else {
            showError('保存参数失败: ' + result.message);
            return false;
        }
    } catch (error) {
        console.error('Save params error:', error);
        showError('保存参数失败');
        return false;
    }
}

/**
 * 恢复默认参数
 */
async function resetMacdParams() {
    if (!currentEtfCode) return;

    if (!confirm('确定要恢复默认MACD参数吗？（Fast:8, Slow:17, Signal:5）')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/watchlist/${currentEtfCode}/macd-params`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            currentMacdParams = {...DEFAULT_MACD_PARAMS};
            updateParamsDisplay(currentMacdParams, false);
            document.getElementById('resetParamsBtn').style.display = 'none';
            optimizedMacdParams = null;

            showNotification('已恢复默认参数', 'info');

            // 重新加载回测数据
            await loadBacktestData(currentEtfCode, currentStrategy);
        } else {
            showError('恢复失败: ' + result.message);
        }
    } catch (error) {
        console.error('Reset params error:', error);
        showError('恢复参数失败');
    }
}

// ==================== MACD+KDJ离散策略参数优化 ====================

/**
 * 优化MACD+KDJ离散策略参数
 */
async function optimizeMacdKdjDiscreteParams() {
    if (!currentEtfCode) {
        showError('请先选择一个ETF');
        return;
    }

    const btn = document.getElementById('optimizeParamsBtn');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">优化中...</span>';
    btn.disabled = true;

    // 显示进度提示
    showNotification('正在优化MACD+KDJ参数，这可能需要30-60秒...', 'info');

    try {
        const response = await fetch(`${API_BASE}/macd-kdj-discrete/optimize-params/${currentEtfCode}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                lookback_days: 365,
                optimize_kdj: true
            })
        });

        const result = await response.json();

        if (result.success && result.optimization_result) {
            const bestParams = result.optimization_result.best_params;
            const metrics = result.optimization_result.metrics;

            // 显示优化结果
            showOptimizationResultDiscrete(bestParams, metrics);

            // 自动保存优化参数
            await saveOptimizedDiscreteParams(currentEtfCode, bestParams);
        } else {
            showError('参数优化失败: ' + (result.message || '未知错误'));
        }
    } catch (error) {
        console.error('Optimization error:', error);
        showError('参数优化失败，请稍后重试');
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }
}

/**
 * 显示MACD+KDJ离散策略优化结果
 */
function showOptimizationResultDiscrete(params, metrics) {
    const panel = document.getElementById('optimizationResultPanel');

    if (!panel) {
        console.error('optimizationResultPanel not found');
        return;
    }

    // 更新MACD参数显示
    document.getElementById('optMacdFast').textContent = params.macd_fast;
    document.getElementById('optMacdSlow').textContent = params.macd_slow;
    document.getElementById('optMacdSignal').textContent = params.macd_signal;

    // 显示KDJ参数网格
    const kdjGrid = document.getElementById('optKdjParamsGrid');
    if (kdjGrid) {
        kdjGrid.style.display = 'grid';
        document.getElementById('optKdjN').textContent = params.kdj_n;
        document.getElementById('optKdjM1').textContent = params.kdj_m1;
        document.getElementById('optKdjM2').textContent = params.kdj_m2;
    }

    // 更新指标显示
    const returnEl = document.getElementById('optReturn');
    returnEl.textContent = metrics.total_return_pct + '%';
    returnEl.className = 'opt-highlight ' + (metrics.total_return_pct >= 0 ? 'positive' : 'negative');

    document.getElementById('optSharpe').textContent = metrics.sharpe_ratio.toFixed(2);
    document.getElementById('optDrawdown').textContent = metrics.max_drawdown_pct + '%';

    // 更新期间和交易次数
    document.getElementById('optPeriod').textContent = `优化期间: 近一年`;
    document.getElementById('optTrades').textContent = `交易次数: ${metrics.total_trades}`;

    panel.style.display = 'block';
}

/**
 * 保存优化后的MACD+KDJ离散策略参数
 */
async function saveOptimizedDiscreteParams(etfCode, params) {
    try {
        const response = await fetch(`${API_BASE}/watchlist/${etfCode}/macd-kdj-discrete-params`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(params)
        });

        const result = await response.json();

        if (result.success) {
            showNotification('优化参数已保存，正在重新回测...', 'success');

            // 先刷新 watchlist 数据
            await loadWatchlist();

            // 重新加载回测数据
            await Promise.all([
                loadRealtimeSignal(etfCode, currentStrategy),
                loadBacktestData(etfCode, currentStrategy)
            ]);

            // 更新参数显示
            await loadAndDisplayDiscreteParams(etfCode);

            return true;
        } else {
            showError('保存参数失败: ' + result.message);
            return false;
        }
    } catch (error) {
        console.error('Save params error:', error);
        showError('保存参数失败');
        return false;
    }
}

/**
 * 恢复MACD+KDJ离散策略默认参数
 */
async function resetMacdKdjDiscreteParams() {
    if (!currentEtfCode) return;

    if (!confirm('确定要恢复默认MACD+KDJ参数吗？（MACD:12,26,9 KDJ:9,3,3）')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/watchlist/${currentEtfCode}/macd-kdj-discrete-params`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('已恢复默认参数', 'info');

            // 重新加载回测数据
            await Promise.all([
                loadWatchlist(),
                loadRealtimeSignal(currentEtfCode, currentStrategy),
                loadBacktestData(currentEtfCode, currentStrategy)
            ]);

            // 更新参数显示
            await loadAndDisplayDiscreteParams(currentEtfCode);
        } else {
            showError('恢复失败: ' + result.message);
        }
    } catch (error) {
        console.error('Reset params error:', error);
        showError('恢复参数失败');
    }
}

/**
 * 加载并显示MACD+KDJ离散策略参数
 */
async function loadAndDisplayDiscreteParams(etfCode) {
    try {
        const response = await fetch(`${API_BASE}/watchlist/${etfCode}/macd-kdj-discrete-params`);
        const result = await response.json();

        if (result.success) {
            const params = result.params;
            const displayEl = document.getElementById('currentParamsDisplay');

            if (result.has_optimized) {
                displayEl.textContent = `M:${params.macd_fast},${params.macd_slow},${params.macd_signal} K:${params.kdj_n},${params.kdj_m1},${params.kdj_m2}`;
                displayEl.classList.add('optimized');
                document.getElementById('resetParamsBtn').style.display = 'flex';
            } else {
                displayEl.textContent = `M:${params.macd_fast},${params.macd_slow},${params.macd_signal} K:${params.kdj_n},${params.kdj_m1},${params.kdj_m2}`;
                displayEl.classList.remove('optimized');
                document.getElementById('resetParamsBtn').style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Failed to load params:', error);
    }
}

/**
 * 优化RSI三线策略参数
 */
async function optimizeRsiTripleLinesParams() {
    if (!currentEtfCode) {
        showError('请先选择一个ETF');
        return;
    }

    const btn = document.getElementById('optimizeParamsBtn');
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">优化中...</span>';
    btn.disabled = true;

    // 显示进度提示
    showNotification('正在优化RSI三线参数，这可能需要30-60秒...', 'info');

    try {
        const response = await fetch(`${API_BASE}/rsi-triple-lines/optimize-params/${currentEtfCode}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });

        const result = await response.json();

        if (result.success) {
            displayRsiTripleLinesOptimizationResult(result);
            showNotification('参数优化完成！', 'success');

            // 自动保存优化后的参数
            const bestParams = result.optimization_result.best_params;
            await saveRsiTripleLinesOptimizedParams(currentEtfCode, bestParams);
        } else {
            showError('参数优化失败: ' + result.message);
        }
    } catch (error) {
        console.error('Optimization error:', error);
        showError('优化请求失败');
    } finally {
        btn.innerHTML = originalHTML;
        btn.disabled = false;
    }
}

/**
 * 显示RSI三线优化结果
 */
function displayRsiTripleLinesOptimizationResult(result) {
    const optResult = result.optimization_result;

    // 保存优化后的参数
    optimizedRsiTripleLinesParams = optResult.best_params;

    // 填充参数值
    document.getElementById('optMacdFast').textContent = `RSI1:${optResult.best_params.rsi1_period}`;
    document.getElementById('optMacdSlow').textContent = `RSI2:${optResult.best_params.rsi2_period}`;
    document.getElementById('optMacdSignal').textContent = `RSI3:${optResult.best_params.rsi3_period}`;

    // 填充指标
    document.getElementById('optReturn').textContent = optResult.total_return_pct.toFixed(2) + '%';
    document.getElementById('optReturn').className = 'opt-highlight ' + (optResult.total_return_pct >= 0 ? 'positive' : 'negative');
    document.getElementById('optSharpe').textContent = optResult.sharpe_ratio.toFixed(2);
    document.getElementById('optDrawdown').textContent = optResult.max_drawdown_pct.toFixed(2) + '%';

    // 填充交易信息
    document.getElementById('optPeriod').textContent = `优化期间: 近一年数据`;
    document.getElementById('optTrades').textContent = `交易次数: ${optResult.total_trades} | 胜率: ${optResult.win_rate_pct.toFixed(1)}%`;

    // 显示面板
    document.getElementById('optimizationResultPanel').style.display = 'block';
}

/**
 * 恢复RSI三线默认参数
 */
async function resetRsiTripleLinesParams() {
    if (!currentEtfCode) {
        showError('请先选择一个ETF');
        return;
    }

    try {
        // 删除优化参数
        const response = await fetch(`${API_BASE}/watchlist/${currentEtfCode}/reset-params`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'}
        });

        const result = await response.json();

        if (result.success) {
            // 恢复默认参数显示
            const displayEl = document.getElementById('currentParamsDisplay');
            displayEl.textContent = `RSI1:6 RSI2:12 RSI3:24`;
            displayEl.classList.remove('optimized');
            document.getElementById('resetParamsBtn').style.display = 'none';

            showNotification('已恢复默认参数', 'success');

            // 重新加载信号
            await loadAndDisplayRsiTripleLinesParams(currentEtfCode);
        } else {
            showError('恢复参数失败: ' + result.message);
        }
    } catch (error) {
        console.error('Reset params error:', error);
        showError('恢复参数失败');
    }
}

/**
 * 保存RSI三线优化参数
 */
async function saveRsiTripleLinesOptimizedParams(etfCode, params) {
    try {
        const response = await fetch(`${API_BASE}/watchlist/${etfCode}/rsi-triple-lines-params`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(params)
        });

        const result = await response.json();

        if (result.success) {
            console.log('RSI三线参数已保存:', params);
            // 重新加载信号
            await loadAndDisplayRsiTripleLinesParams(etfCode);
        }
    } catch (error) {
        console.error('Save params error:', error);
    }
}

/**
 * 加载并显示RSI三线策略参数
 */
async function loadAndDisplayRsiTripleLinesParams(etfCode) {
    try {
        const response = await fetch(`${API_BASE}/watchlist/${etfCode}/rsi-triple-lines-params`);
        const result = await response.json();

        if (result.success) {
            const params = result.params;
            const displayEl = document.getElementById('currentParamsDisplay');

            if (result.has_optimized) {
                displayEl.textContent = `RSI1:${params.rsi1_period} RSI2:${params.rsi2_period} RSI3:${params.rsi3_period}`;
                displayEl.classList.add('optimized');
                document.getElementById('resetParamsBtn').style.display = 'flex';
            } else {
                displayEl.textContent = `RSI1:6 RSI2:12 RSI3:24`;
                displayEl.classList.remove('optimized');
                document.getElementById('resetParamsBtn').style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Failed to load params:', error);
    }
}
