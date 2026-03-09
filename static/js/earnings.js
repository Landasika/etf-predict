// 收益汇总页面
console.log('📝 earnings.js v10 已加载 - 添加认证支持');

// 收益日历相关
let allProfitCalendarData = [];  // 存储所有ETF的日收益数据
let currentCalendarDate = new Date();  // 当前日历显示的月份
let currentCalendarYear = new Date().getFullYear();  // 当前日历显示的年份
let mainChart = null;  // 主图表（资产+仓位）
let currentCalendarView = 'daily';  // 日历视图：daily 或 monthly
let allTimelineData = [];  // 存储完整的时间线数据
let dailyTimelineData = [];  // 存储日度数据
let monthlyProfitData = [];  // 存储月度汇总数据

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

    // 加载数据日期
    loadDataDate();

    // 刷新按钮
    document.getElementById('refreshBtn').addEventListener('click', async function() {
        location.reload();
    });

    // 更新数据按钮
    document.getElementById('updateDataBtn').addEventListener('click', triggerDataUpdate);

    // 加载收益数据按钮
    const loadProfitBtn = document.getElementById('loadProfitDataBtn');
    if (loadProfitBtn) {
        loadProfitBtn.addEventListener('click', loadAllEtfsProfitData);
    }

    // 更新时间
    updateLastUpdated();
});

// 加载数据日期
async function loadDataDate() {
    try {
        const response = await fetch('/api/data/latest-date');
        const result = await response.json();

        if (result.success && result.latest_date) {
            document.getElementById('dataDate').textContent = result.latest_date;
        }
    } catch (error) {
        console.error('加载数据日期失败:', error);
    }
}

// 触发数据更新
async function triggerDataUpdate() {
    const btn = document.getElementById('updateDataBtn');
    const originalText = btn.innerHTML;

    try {
        btn.disabled = true;
        btn.innerHTML = '⏳ 更新中...';

        const response = await fetch('/api/data/update', {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showMessage('数据更新成功！', 'success');
            // 刷新页面
            setTimeout(() => location.reload(), 1000);
        } else {
            showMessage('数据更新失败: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('数据更新失败:', error);
        showMessage('数据更新失败: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}

// 显示消息提示（替代 alert）
function showMessage(message, type = 'info') {
    const msgDiv = document.createElement('div');
    msgDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        font-weight: 500;
        animation: slideIn 0.3s ease;
    `;
    msgDiv.textContent = message;
    document.body.appendChild(msgDiv);

    setTimeout(() => {
        msgDiv.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => msgDiv.remove(), 300);
    }, 3000);
}

// 更新最后更新时间
function updateLastUpdated() {
    const now = new Date();
    const timeStr = now.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('lastUpdated').textContent = timeStr;
}

/**
 * 加载所有ETF的收益数据（用户手动触发）
 */
async function loadAllEtfsProfitData() {
    const btn = document.getElementById('loadProfitDataBtn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">加载中...</span>';
    }

    try {
        const response = await fetch('/api/profit/all-etfs-daily?start_date=20250101');
        const result = await response.json();

        if (!result.success) {
            console.error('Failed to load all ETFs profit:', result.message);
            showMessage('加载收益数据失败: ' + result.message, 'error');
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span class="btn-icon">📊</span><span class="btn-text">加载所有ETF收益数据</span>';
            }
            return;
        }

        const dailyProfits = result.data.daily_profits;
        const timeline = result.data.timeline || [];
        const totalInitialCapital = result.data.total_initial_capital;
        const etfCount = result.data.etf_count;

        if (!dailyProfits || dailyProfits.length === 0) {
            showMessage('没有收益数据', 'error');
            return;
        }

        // 计算累计收益
        let totalProfit = 0;
        dailyProfits.forEach(d => {
            totalProfit += d.daily_profit;
        });

        const latestValue = totalInitialCapital + totalProfit;
        const totalPct = (totalProfit / totalInitialCapital) * 100;

        // 更新汇总卡片
        document.getElementById('profitEtfCount').textContent = etfCount;
        document.getElementById('profitInitialCapital').textContent = `¥${totalInitialCapital.toFixed(2)}`;
        document.getElementById('profitCurrentValue').textContent = `¥${latestValue.toFixed(2)}`;

        const profitPctEl = document.getElementById('profitTotalPct');
        profitPctEl.textContent = `${totalPct >= 0 ? '+' : ''}${totalPct.toFixed(2)}%`;
        profitPctEl.className = 'profit-value ' + (totalPct >= 0 ? 'profit-positive' : 'profit-negative');

        // 显示内容，隐藏加载按钮
        document.getElementById('profitContent').style.display = 'block';
        document.getElementById('calendarLoadingContainer').style.display = 'none';

        // 保存完整数据并过滤
        allTimelineData = timeline;
        dailyTimelineData = filterTimelineFrom2025(timeline);
        monthlyProfitData = aggregateMonthlyProfits(dailyProfits);

        // 显示图表区域并渲染日度曲线
        if (dailyTimelineData.length > 0) {
            document.getElementById('chartsSection').style.display = 'block';
            renderMainChart(dailyTimelineData, dailyProfits, totalInitialCapital, result.data.total_positions_max || 100);
        }

        // 绑定日历视图切换按钮
        document.getElementById('calendarViewDailyBtn').onclick = () => switchCalendarView('daily');
        document.getElementById('calendarViewMonthlyBtn').onclick = () => switchCalendarView('monthly');

        // 保存日收益数据用于日历渲染
        allProfitCalendarData = dailyProfits;

        // 渲染默认日历视图（日视图）
        renderAllEtfCalendarForMonth(currentCalendarDate);

        // 绑定日历导航事件
        document.getElementById('prevMonthBtn').onclick = () => {
            currentCalendarDate.setMonth(currentCalendarDate.getMonth() - 1);
            renderAllEtfCalendarForMonth(currentCalendarDate);
        };

        document.getElementById('nextMonthBtn').onclick = () => {
            currentCalendarDate.setMonth(currentCalendarDate.getMonth() + 1);
            renderAllEtfCalendarForMonth(currentCalendarDate);
        };

        // 绑定年视图导航事件
        document.getElementById('prevYearBtn').onclick = () => {
            currentCalendarYear -= 1;
            renderYearlyCalendar(currentCalendarYear);
        };

        document.getElementById('nextYearBtn').onclick = () => {
            currentCalendarYear += 1;
            renderYearlyCalendar(currentCalendarYear);
        };

        showMessage('收益数据加载完成！', 'success');

    } catch (error) {
        console.error('Failed to load profit data:', error);
        showMessage('加载收益数据失败', 'error');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span class="btn-icon">📊</span><span class="btn-text">加载所有ETF收益数据</span>';
        }
    }
}

/**
 * 渲染指定月份的日历（所有ETF汇总）
 */
function renderAllEtfCalendarForMonth(date) {
    if (!allProfitCalendarData || allProfitCalendarData.length === 0) {
        return;
    }

    const year = date.getFullYear();
    const month = date.getMonth();

    // 更新月份标签
    document.getElementById('currentMonthLabel').textContent = `${year}年${month + 1}月`;

    // 获取当月第一天和最后一天
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    // 计算日历网格（从周日开始）
    const calendarContainer = document.getElementById('profitCalendar');
    calendarContainer.innerHTML = '';
    calendarContainer.classList.remove('monthly-view');  // 移除月度视图类

    // 添加星期标题
    const weekDays = ['日', '一', '二', '三', '四', '五', '六'];
    weekDays.forEach(day => {
        const header = document.createElement('div');
        header.className = 'calendar-day-header';
        header.textContent = day;
        calendarContainer.appendChild(header);
    });

    // 添加空白格子（月初前的空白）
    const firstDayWeek = firstDay.getDay();
    for (let i = 0; i < firstDayWeek; i++) {
        const emptyDay = document.createElement('div');
        emptyDay.className = 'calendar-day empty';
        calendarContainer.appendChild(emptyDay);
    }

    // 构建每日收益数据映射（单日收益）
    const dailyProfitMap = {};
    allProfitCalendarData.forEach(d => {
        const dateStr = String(d.date);
        const y = parseInt(dateStr.substring(0, 4));
        const m = parseInt(dateStr.substring(4, 6)) - 1;
        const day = parseInt(dateStr.substring(6, 8));

        if (y === year && m === month) {
            dailyProfitMap[day] = {
                profit: d.daily_profit,
                etfCount: d.etf_count,
                etfProfits: d.etf_profits
            };
        }
    });

    // 添加日期格子
    for (let day = 1; day <= lastDay.getDate(); day++) {
        const dayEl = document.createElement('div');
        dayEl.className = 'calendar-day';

        const dayData = dailyProfitMap[day];

        if (dayData) {
            // 有交易数据
            const profitClass = getDailyProfitClass(dayData.profit);
            dayEl.classList.add(profitClass);

            dayEl.innerHTML = `
                <span class="calendar-day-number">${day}</span>
                <span class="calendar-day-profit ${dayData.profit >= 0 ? 'positive' : 'negative'}">
                    ${dayData.profit >= 0 ? '+' : ''}${dayData.profit.toFixed(2)}
                </span>
            `;

            // 添加悬停提示
            dayEl.onmouseenter = (e) => showAllEtfCalendarTooltip(e, year, month + 1, day, dayData);
            dayEl.onmouseleave = hideCalendarTooltip;
        } else {
            // 无交易数据（周末或节假日）
            dayEl.classList.add('neutral');
            dayEl.innerHTML = `
                <span class="calendar-day-number">${day}</span>
                <span class="calendar-day-profit neutral">-</span>
            `;
        }

        calendarContainer.appendChild(dayEl);
    }
}

/**
 * 根据单日收益金额获取日历格子样式类
 */
function getDailyProfitClass(profit) {
    const absProfit = Math.abs(profit);

    if (profit > 0) {
        if (absProfit < 50) return 'profit-low';
        if (absProfit < 100) return 'profit-medium-low';
        if (absProfit < 200) return 'profit-medium';
        if (absProfit < 500) return 'profit-medium-high';
        return 'profit-high';
    } else {
        if (absProfit < 50) return 'loss-low';
        if (absProfit < 100) return 'loss-medium-low';
        if (absProfit < 200) return 'loss-medium';
        if (absProfit < 500) return 'loss-medium-high';
        return 'loss-high';
    }
}

/**
 * 显示所有ETF日历提示框
 */
function showAllEtfCalendarTooltip(event, year, month, day, dayData) {
    const tooltip = document.createElement('div');
    tooltip.className = 'calendar-tooltip';
    tooltip.id = 'calendarTooltip';

    const dateStr = `${year}年${month}月${day}日`;
    const profit = dayData.profit;
    const profitClass = profit >= 0 ? 'positive' : 'negative';

    // 构建ETF详情列表（只显示盈利或亏损最多的前5个）
    let etfDetailsHtml = '';
    if (dayData.etfProfits && dayData.etfProfits.length > 0) {
        const sortedEtfs = dayData.etfProfits.sort((a, b) => Math.abs(b.profit) - Math.abs(a.profit)).slice(0, 5);
        etfDetailsHtml = '<div style="margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.2); padding-top: 8px;">';
        etfDetailsHtml += '<div style="font-size: 11px; color: #aaa; margin-bottom: 4px;">主要ETF:</div>';
        sortedEtfs.forEach(etf => {
            const etfProfitClass = etf.profit >= 0 ? 'positive' : 'negative';
            etfDetailsHtml += `<div style="font-size: 11px;">${etf.name}: <span class="${etfProfitClass}">${etf.profit >= 0 ? '+' : ''}${etf.profit.toFixed(1)}</span></div>`;
        });
        etfDetailsHtml += '</div>';
    }

    tooltip.innerHTML = `
        <div class="tooltip-date">${dateStr}</div>
        <div class="tooltip-profit ${profitClass}">
            总收益: ${profit >= 0 ? '+' : ''}¥${profit.toFixed(2)}
        </div>
        <div style="font-size: 11px; color: #aaa;">涉及 ${dayData.etfCount} 个ETF</div>
        ${etfDetailsHtml}
    `;

    document.body.appendChild(tooltip);

    // 定位提示框
    const rect = event.target.getBoundingClientRect();
    tooltip.style.left = (rect.left + rect.width / 2 - tooltip.offsetWidth / 2) + 'px';
    tooltip.style.top = (rect.top - tooltip.offsetHeight - 10) + 'px';
}

/**
 * 隐藏日历提示框
 */
function hideCalendarTooltip() {
    const tooltip = document.getElementById('calendarTooltip');
    if (tooltip) {
        tooltip.remove();
    }
}

/**
 * 过滤从2025-01-01开始的数据
 */
function filterTimelineFrom2025(timeline) {
    return timeline.filter(d => {
        const dateStr = String(d.date);
        return dateStr >= '20250101';
    });
}

/**
 * 聚合月度收益数据（用于日历）
 */
function aggregateMonthlyProfits(dailyProfits) {
    const monthlyMap = new Map();

    dailyProfits.forEach(day => {
        const dateStr = String(day.date);
        const year = parseInt(dateStr.substring(0, 4));
        const month = parseInt(dateStr.substring(4, 6));
        const monthKey = `${year}-${month.toString().padStart(2, '0')}`;

        if (!monthlyMap.has(monthKey)) {
            monthlyMap.set(monthKey, {
                year: year,
                month: month,
                total_profit: 0,
                etf_count: 0
            });
        }

        const monthData = monthlyMap.get(monthKey);
        monthData.total_profit += day.daily_profit;  // 使用单日收益
        monthData.etf_count += 1;
    });

    return Array.from(monthlyMap.values()).sort((a, b) => {
        if (a.year !== b.year) return a.year - b.year;
        return a.month - b.month;
    });
}

/**
 * 切换日历视图（日/月）
 */
function switchCalendarView(view) {
    console.log('切换到视图:', view);
    console.log('月度数据数量:', monthlyProfitData.length);
    console.log('日度数据数量:', allProfitCalendarData.length);

    currentCalendarView = view;

    // 更新按钮状态
    document.getElementById('calendarViewDailyBtn').classList.toggle('active', view === 'daily');
    document.getElementById('calendarViewMonthlyBtn').classList.toggle('active', view === 'monthly');

    // 显示/隐藏导航控制
    document.getElementById('dailyViewControls').style.display = view === 'daily' ? 'flex' : 'none';
    document.getElementById('yearlyViewControls').style.display = view === 'monthly' ? 'flex' : 'none';

    // 渲染对应视图
    if (view === 'daily') {
        renderAllEtfCalendarForMonth(currentCalendarDate);
    } else {
        renderYearlyCalendar(currentCalendarYear);
    }
}

/**
 * 渲染年度日历（显示12个月的收益）
 */
function renderYearlyCalendar(year) {
    console.log('渲染年度日历:', year);
    const calendarContainer = document.getElementById('profitCalendar');
    calendarContainer.innerHTML = '';
    calendarContainer.classList.add('monthly-view');

    // 更新年份标签
    document.getElementById('currentYearLabel').textContent = `${year}年`;

    // 获取该年的月度数据
    const yearData = monthlyProfitData.filter(d => d.year === year);
    console.log(`${year}年有数据的月份:`, yearData.map(d => `${d.month}月=${d.total_profit.toFixed(0)}`));

    // 直接渲染12个月份（不需要季度标题）
    for (let month = 1; month <= 12; month++) {
        const monthData = yearData.find(d => d.month === month);
        const monthEl = document.createElement('div');
        monthEl.className = 'calendar-month-card';

        if (monthData) {
            const profit = monthData.total_profit;
            const profitClass = getMonthlyProfitClass(profit);
            monthEl.classList.add(profitClass);

            monthEl.innerHTML = `
                <span class="calendar-month-name">${month}月</span>
                <span class="calendar-month-profit ${profit >= 0 ? 'positive' : 'negative'}">
                    ¥${profit >= 0 ? '+' : ''}${profit.toFixed(2)}
                </span>
            `;
        } else {
            monthEl.classList.add('neutral');
            monthEl.innerHTML = `
                <span class="calendar-month-name">${month}月</span>
                <span class="calendar-month-profit neutral">无数据</span>
            `;
        }

        calendarContainer.appendChild(monthEl);
    }
}

/**
 * 根据月度收益获取样式类
 */
function getMonthlyProfitClass(profit) {
    const absProfit = Math.abs(profit);

    if (profit > 0) {
        if (absProfit < 200) return 'profit-low';
        if (absProfit < 500) return 'profit-medium-low';
        if (absProfit < 1000) return 'profit-medium';
        if (absProfit < 2000) return 'profit-medium-high';
        return 'profit-high';
    } else {
        if (absProfit < 200) return 'loss-low';
        if (absProfit < 500) return 'loss-medium-low';
        if (absProfit < 1000) return 'loss-medium';
        if (absProfit < 2000) return 'loss-medium-high';
        return 'loss-high';
    }
}

/**
 * 渲染主图表（累计收益 + 仓位变化，双Y轴）
 */
function renderMainChart(timeline, dailyProfits, initialCapital, maxPositions) {
    if (!timeline || timeline.length === 0) return;

    const dates = timeline.map(d => {
        const dateStr = String(d.date);
        return `${dateStr.substring(4, 6)}-${dateStr.substring(6, 8)}`;
    });

    // 累加每天的收益（从2025-01-01开始）
    let cumulativeSum = 0;
    const dailyProfitsMap = new Map(dailyProfits.map(d => [String(d.date), d.daily_profit]));

    const cumulativeProfits = timeline.map(d => {
        const dateStr = String(d.date);
        const dailyProfit = dailyProfitsMap.get(dateStr) || 0;
        cumulativeSum += dailyProfit;
        return cumulativeSum;
    });

    const positions = timeline.map(d => d.total_positions);

    const chartDom = document.getElementById('mainChart');
    if (!chartDom) return;

    if (mainChart) {
        mainChart.dispose();
    }

    mainChart = echarts.init(chartDom);

    const option = {
        title: {
            text: '累计收益与仓位变化趋势（日度）',
            left: 'center',
            top: 10,
            textStyle: {
                fontSize: 16,
                fontWeight: 600,
                color: '#333'
            }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            },
            formatter: function(params) {
                let result = `<div style="font-weight: 600; margin-bottom: 5px;">${params[0].axisValue}</div>`;
                params.forEach(param => {
                    let value = param.value;
                    if (param.seriesName === '总仓位') {
                        result += `${param.marker} ${param.seriesName}: ${value.toFixed(1)} 仓<br/>`;
                    } else {
                        result += `${param.marker} ${param.seriesName}: ¥${value.toFixed(2)}<br/>`;
                    }
                });
                return result;
            }
        },
        legend: {
            data: ['累计收益', '总仓位'],
            top: 45
        },
        toolbox: {
            show: true,
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                restore: {},
                saveAsImage: {
                    pixelRatio: 2,
                    title: '保存图片'
                }
            },
            right: 20,
            top: 10
        },
        dataZoom: [
            {
                type: 'inside',
                start: 0,
                end: 100
            },
            {
                start: 0,
                end: 100,
                height: 20,
                bottom: 10
            }
        ],
        grid: {
            left: '5%',
            right: '5%',
            bottom: '15%',
            top: '20%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: dates,
            axisLabel: {
                rotate: 45,
                fontSize: 11
            }
        },
        yAxis: [
            {
                type: 'value',
                name: '累计收益(元)',
                position: 'left',
                axisLabel: {
                    formatter: function(value) {
                        return '¥' + value.toFixed(0);
                    }
                },
                splitLine: {
                    show: true,
                    lineStyle: {
                        color: '#e5e7eb'
                    }
                }
            },
            {
                type: 'value',
                name: '仓位(成)',
                position: 'right',
                min: 0,
                max: maxPositions * 1.1,
                axisLabel: {
                    formatter: '{value}'
                },
                splitLine: {
                    show: false
                }
            }
        ],
        series: [
            {
                name: '累计收益',
                type: 'line',
                yAxisIndex: 0,
                data: cumulativeProfits,
                smooth: true,
                symbol: 'circle',
                symbolSize: 6,
                itemStyle: { color: '#10b981' },
                lineStyle: {
                    width: 2
                },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(16, 185, 129, 0.3)' },
                        { offset: 1, color: 'rgba(16, 185, 129, 0.05)' }
                    ])
                },
                markLine: {
                    data: [
                        { yAxis: 0, name: '盈亏平衡线' }
                    ],
                    lineStyle: {
                        color: '#666',
                        type: 'solid',
                        width: 1
                    },
                    label: {
                        formatter: '盈亏平衡'
                    }
                }
            },
            {
                name: '总仓位',
                type: 'line',
                yAxisIndex: 1,
                data: positions,
                smooth: true,
                symbol: 'diamond',
                symbolSize: 6,
                itemStyle: { color: '#f59e0b' },
                lineStyle: {
                    type: 'dashed',
                    width: 2
                },
                markLine: {
                    data: [
                        { type: 'average', name: '平均仓位' }
                    ],
                    lineStyle: {
                        color: '#f59e0b',
                        type: 'solid',
                        width: 1
                    },
                    label: {
                        formatter: '平均: {c}'
                    }
                }
            }
        ]
    };

    mainChart.setOption(option);

    // 响应式
    window.addEventListener('resize', () => {
        mainChart.resize();
    });
}
