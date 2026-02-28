// Settings page JavaScript

// Load settings on page load
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Settings page loaded');
    await loadSettings();
    await loadDataSourceStatus();

    // Setup data source priority checkboxes
    setupPriorityCheckboxes();
});

// Load all settings
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();

        if (data.success) {
            const settings = data.data;
            console.log('Settings loaded:', settings);

            // Load tokens
            if (settings.tushare) {
                const tushareInput = document.getElementById('tushareToken');
                if (tushareInput) {
                    tushareInput.value = settings.tushare.token || '';
                    tushareInput.placeholder = settings.tushare.token ? '已配置' : '输入Tushare Token';

                    // Show/hide status
                    const statusSpan = tushareInput.parentElement?.querySelector('.setting-status');
                    if (statusSpan) {
                        statusSpan.textContent = settings.tushare.token ? '✓ 已配置' : '';
                    }
                }
            }

            if (settings.minishare) {
                const minishareInput = document.getElementById('minishareToken');
                if (minishareInput) {
                    minishareInput.value = settings.minishare.token || '';
                    minishareInput.placeholder = settings.minishare.token ? '已配置' : '输入Minishare Token';

                    // Show/hide status
                    const statusSpan = minishareInput.parentElement?.querySelector('.setting-status');
                    if (statusSpan) {
                        statusSpan.textContent = settings.minishare.token ? '✓ 已配置' : '';
                    }
                }
            }

            // Load data source priority
            if (settings.data_source?.priority) {
                settings.data_source.priority.forEach((source, index) => {
                    const checkbox = document.getElementById(`priority_${source}`);
                    if (checkbox) {
                        checkbox.checked = true;

                        // Update label to show priority number
                        const label = checkbox.parentElement?.querySelector('label');
                        if (label) {
                            const priorityEmoji = ['1️⃣', '2️⃣', '3️⃣'][index] || '•';
                            label.textContent = `${priorityEmoji} ${label.textContent.split(' ', 1)[0]} (${source === 'minishare' ? '实时数据' : '历史数据'})`;
                        }
                    }
                });
            }

            // Load update schedule
            if (settings.update_schedule) {
                const autoUpdateCheckbox = document.getElementById('autoUpdateEnabled');
                if (autoUpdateCheckbox) {
                    autoUpdateCheckbox.checked = settings.update_schedule.enabled || false;
                }

                const updateTimeInput = document.getElementById('updateTime');
                if (updateTimeInput) {
                    updateTimeInput.value = settings.update_schedule.time || '15:05';
                }
            }

            // Load strategy defaults
            if (settings.strategy) {
                const defaultStrategySelect = document.getElementById('defaultStrategy');
                if (defaultStrategySelect) {
                    defaultStrategySelect.value = settings.strategy.default_strategy || 'macd_aggressive';
                }

                const initialCapitalInput = document.getElementById('initialCapital');
                if (initialCapitalInput) {
                    initialCapitalInput.value = settings.strategy.default_initial_capital || 2000;
                }

                const totalPositionsInput = document.getElementById('totalPositions');
                if (totalPositionsInput) {
                    totalPositionsInput.value = settings.strategy.default_positions || 10;
                }
            }
        } else {
            console.error('Failed to load settings:', data.message);
            showToast('加载设置失败', 'error');
        }
    } catch (error) {
        console.error('Error loading settings:', error);
        showToast('加载设置失败: ' + error.message, 'error');
    }
}

// Save all settings
async function saveSettings() {
    try {
        // Collect all settings
        const settings = {
            tushare: {
                token: document.getElementById('tushareToken')?.value || ''
            },
            minishare: {
                token: document.getElementById('minishareToken')?.value || ''
            },
            data_source: {
                priority: getDataSourcePriority()
            },
            update_schedule: {
                enabled: document.getElementById('autoUpdateEnabled')?.checked || false,
                time: document.getElementById('updateTime')?.value || '15:05'
            },
            strategy: {
                default_strategy: document.getElementById('defaultStrategy')?.value || 'macd_aggressive',
                default_initial_capital: parseFloat(document.getElementById('initialCapital')?.value) || 2000,
                default_positions: parseInt(document.getElementById('totalPositions')?.value) || 10
            }
        };

        console.log('Saving settings:', settings);

        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });

        const data = await response.json();

        if (data.success) {
            showToast('设置已保存');
            await loadDataSourceStatus(); // Refresh status
        } else {
            console.error('Failed to save settings:', data.message);
            showToast('保存失败: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error saving settings:', error);
        showToast('保存失败: ' + error.message, 'error');
    }
}

// Get data source priority from checkboxes
function getDataSourcePriority() {
    const priority = [];
    const checkboxes = document.querySelectorAll('.priority-item input[type="checkbox"]:checked');

    checkboxes.forEach(checkbox => {
        const source = checkbox.closest('.priority-item')?.dataset.source;
        if (source) {
            priority.push(source);
        }
    });

    return priority;
}

// Setup priority checkbox behavior
function setupPriorityCheckboxes() {
    const checkboxes = document.querySelectorAll('.priority-item input[type="checkbox"]');

    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', () => {
            updatePriorityLabels();
        });
    });
}

// Update priority labels with numbers
function updatePriorityLabels() {
    const checkedItems = document.querySelectorAll('.priority-item input[type="checkbox"]:checked');

    checkedItems.forEach((checkbox, index) => {
        const label = checkbox.parentElement?.querySelector('label');
        if (label) {
            const sourceName = label.textContent.split(' ', 2)[1] || label.textContent;
            const priorityEmoji = ['1️⃣', '2️⃣', '3️⃣'][index] || '•';
            const source = checkbox.closest('.priority-item')?.dataset.source;
            const description = source === 'minishare' ? '（实时数据）' : '（历史数据）';
            label.textContent = `${priorityEmoji} ${sourceName} ${description}`;
        }
    });
}

// Test token connection
async function testToken(source) {
    try {
        const tokenInput = document.getElementById(`${source}Token`);
        const token = tokenInput?.value;

        if (!token) {
            showToast('请先输入Token', 'error');
            return;
        }

        showToast('正在测试连接...');

        // Send test request
        const response = await fetch('/api/settings/test-token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                source: source,
                token: token
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast(`${source === 'tushare' ? 'Tushare' : 'Minishare'} 连接成功`);
        } else {
            showToast(`${source === 'tushare' ? 'Tushare' : 'Minishare'} 连接失败: ${data.message}`, 'error');
        }
    } catch (error) {
        console.error('Error testing token:', error);
        showToast('测试失败: ' + error.message, 'error');
    }
}

// Load data source status
async function loadDataSourceStatus() {
    try {
        const response = await fetch('/api/settings/data-source/status');
        const data = await response.json();

        const statusBox = document.getElementById('dataSourceStatus');
        if (!statusBox) return;

        if (data.success) {
            const status = data.data;

            // Build status HTML
            let html = '';

            if (status.sources) {
                status.sources.forEach(source => {
                    const isActive = source.active;
                    const indicatorClass = isActive ? 'active' : 'inactive';

                    html += `
                        <div class="status-item">
                            <span class="status-source">${source.name}</span>
                            <div class="status-indicator ${indicatorClass}">
                                <span class="status-dot ${indicatorClass}"></span>
                                ${isActive ? '已启用' : '未启用'}
                            </div>
                        </div>
                    `;
                });
            }

            if (status.active_source) {
                html += `
                    <div class="status-item" style="border-top: 2px solid #e5e7eb; margin-top: 10px; padding-top: 15px;">
                        <span class="status-source">当前数据源</span>
                        <div class="status-indicator active">
                            <span class="status-dot active"></span>
                            ${status.active_source}
                        </div>
                    </div>
                `;
            }

            statusBox.innerHTML = html;
        } else {
            statusBox.innerHTML = `<div class="status-indicator inactive">加载失败: ${data.message}</div>`;
        }
    } catch (error) {
        console.error('Error loading data source status:', error);
        const statusBox = document.getElementById('dataSourceStatus');
        if (statusBox) {
            statusBox.innerHTML = `<div class="status-indicator inactive">加载失败: ${error.message}</div>`;
        }
    }
}

// Show toast message
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    const toastMessage = document.getElementById('toastMessage');

    if (!toast || !toastMessage) return;

    toastMessage.textContent = message;
    toast.className = 'toast ' + type;

    // Auto hide after 3 seconds
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 3000);
}

// Reset button handler
function resetSettings() {
    if (confirm('确定要重置所有设置吗？此操作将恢复默认值。')) {
        loadSettings();
        showToast('设置已重置');
    }
}

// Update data source priority
async function updateDataSource() {
    try {
        const priority = getDataSourcePriority();

        const response = await fetch('/api/settings/data-source', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                priority: priority
            })
        });

        const data = await response.json();

        if (data.success) {
            showToast('数据源优先级已更新');
            await loadDataSourceStatus(); // Refresh status
        } else {
            showToast('更新失败: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error updating data source:', error);
        showToast('更新失败: ' + error.message, 'error');
    }
}
