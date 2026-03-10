// Settings page JavaScript

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

// Load settings on page load
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Settings page loaded');
    await loadSettings();
    await loadDataSourceStatus();
    await loadFeishuConfig();  // Load Feishu config

    // Setup data source priority checkboxes
    setupPriorityCheckboxes();
});

// Load all settings
async function loadSettings() {
    try {
        const data = await fetchAPI('/api/config');

        if (data.success) {
            const config = data.data;
            console.log('Config loaded:', config);

            // Load tokens
            if (config.tushare) {
                const tushareInput = document.getElementById('tushareToken');
                if (tushareInput) {
                    tushareInput.value = config.tushare.token || '';
                    tushareInput.placeholder = config.tushare.token ? '已配置' : '输入Tushare Token';

                    // Show/hide status
                    const statusSpan = tushareInput.parentElement?.querySelector('.setting-status');
                    if (statusSpan) {
                        statusSpan.textContent = config.tushare.token ? '✓ 已配置' : '';
                    }
                }
            }

            if (config.minishare) {
                const minishareInput = document.getElementById('minishareToken');
                if (minishareInput) {
                    minishareInput.value = config.minishare.token || '';
                    minishareInput.placeholder = config.minishare.token ? '已配置' : '输入Minishare Token';

                    // Show/hide status
                    const statusSpan = minishareInput.parentElement?.querySelector('.setting-status');
                    if (statusSpan) {
                        statusSpan.textContent = config.minishare.token ? '✓ 已配置' : '';
                    }
                }
            }

            // Load API settings
            if (config.api) {
                const apiHostInput = document.getElementById('apiHost');
                if (apiHostInput) {
                    apiHostInput.value = config.api.host || '0.0.0.0';
                }

                const apiPortInput = document.getElementById('apiPort');
                if (apiPortInput) {
                    apiPortInput.value = config.api.port || 8000;
                }
            }

            // Load auth settings (with masked values)
            if (config.auth) {
                const authKeyInput = document.getElementById('authKey');
                if (authKeyInput) {
                    // Show masked value if available
                    authKeyInput.value = config.auth.auth_key && config.auth.auth_key !== '******' ? config.auth.auth_key : '';
                    authKeyInput.placeholder = config.auth.auth_key ? '已配置' : '输入登录密码';

                    const statusSpan = authKeyInput.parentElement?.querySelector('.setting-status');
                    if (statusSpan) {
                        statusSpan.textContent = config.auth.auth_key ? '✓ 已配置' : '';
                    }
                }

                const maxAttemptsInput = document.getElementById('maxAttempts');
                if (maxAttemptsInput) {
                    maxAttemptsInput.value = config.auth.max_login_attempts || 5;
                }

                const lockoutDurationInput = document.getElementById('lockoutDuration');
                if (lockoutDurationInput) {
                    lockoutDurationInput.value = config.auth.lockout_duration || 900;
                }
            }

            // Load data source priority (if data_source config exists)
            if (config.data_source?.priority) {
                config.data_source.priority.forEach((source, index) => {
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

            // Load update schedule (if update_schedule config exists)
            if (config.update_schedule) {
                const autoUpdateCheckbox = document.getElementById('autoUpdateEnabled');
                if (autoUpdateCheckbox) {
                    autoUpdateCheckbox.checked = config.update_schedule.enabled || false;
                }

                const updateTimeInput = document.getElementById('updateTime');
                if (updateTimeInput) {
                    updateTimeInput.value = config.update_schedule.time || '15:05';
                }
            }

            // Load strategy defaults (if strategy config exists)
            if (config.strategy) {
                const defaultStrategySelect = document.getElementById('defaultStrategy');
                if (defaultStrategySelect) {
                    defaultStrategySelect.value = config.strategy.default_strategy || 'macd_aggressive';
                }

                const initialCapitalInput = document.getElementById('initialCapital');
                if (initialCapitalInput) {
                    initialCapitalInput.value = config.strategy.default_initial_capital || 2000;
                }

                const totalPositionsInput = document.getElementById('totalPositions');
                if (totalPositionsInput) {
                    totalPositionsInput.value = config.strategy.default_positions || 10;
                }
            }
        } else {
            console.error('Failed to load config:', data.message);
            showToast('加载配置失败', 'error');
        }
    } catch (error) {
        console.error('Error loading config:', error);
        showToast('加载配置失败: ' + error.message, 'error');
    }
}

// Save all settings
async function saveSettings() {
    try {
        // Get current config first to preserve unchanged fields
        const currentConfigData = await fetchAPI('/api/config');
        if (!currentConfigData.success) {
            showToast('获取当前配置失败', 'error');
            return;
        }

        const currentConfig = currentConfigData.data;

        // Collect all settings to update
        const updates = {
            tushare: {
                token: document.getElementById('tushareToken')?.value || currentConfig.tushare?.token || ''
            },
            minishare: {
                token: document.getElementById('minishareToken')?.value || currentConfig.minishare?.token || ''
            }
        };

        // Add API settings if inputs exist
        const apiHostInput = document.getElementById('apiHost');
        const apiPortInput = document.getElementById('apiPort');
        if (apiHostInput || apiPortInput) {
            updates.api = {
                host: apiHostInput?.value || currentConfig.api?.host || '0.0.0.0',
                port: parseInt(apiPortInput?.value) || currentConfig.api?.port || 8000,
                title: currentConfig.api?.title || 'ETF预测系统API',
                version: currentConfig.api?.version || '1.0.0'
            };
        }

        // Add auth settings if inputs exist
        const authKeyInput = document.getElementById('authKey');
        const maxAttemptsInput = document.getElementById('maxAttempts');
        const lockoutDurationInput = document.getElementById('lockoutDuration');
        if (authKeyInput || maxAttemptsInput || lockoutDurationInput) {
            updates.auth = {
                session_secret_key: currentConfig.auth?.session_secret_key || 'change-this-in-production',
                auth_key: authKeyInput?.value || currentConfig.auth?.auth_key || 'admin123',
                max_login_attempts: parseInt(maxAttemptsInput?.value) || currentConfig.auth?.max_login_attempts || 5,
                login_attempt_window: currentConfig.auth?.login_attempt_window || 300,
                lockout_duration: parseInt(lockoutDurationInput?.value) || currentConfig.auth?.lockout_duration || 900
            };
        }

        // Add data source priority if changed
        const priority = getDataSourcePriority();
        if (priority.length > 0) {
            updates.data_source = {
                priority: priority
            };
        }

        // Add update schedule if changed
        const autoUpdateCheckbox = document.getElementById('autoUpdateEnabled');
        const updateTimeInput = document.getElementById('updateTime');
        if (autoUpdateCheckbox || updateTimeInput) {
            updates.update_schedule = {
                enabled: autoUpdateCheckbox?.checked ?? currentConfig.update_schedule?.enabled ?? false,
                time: updateTimeInput?.value || currentConfig.update_schedule?.time || '15:05'
            };
        }

        // Add strategy defaults if changed
        const defaultStrategySelect = document.getElementById('defaultStrategy');
        const initialCapitalInput = document.getElementById('initialCapital');
        const totalPositionsInput = document.getElementById('totalPositions');
        if (defaultStrategySelect || initialCapitalInput || totalPositionsInput) {
            updates.strategy = {
                default_strategy: defaultStrategySelect?.value || currentConfig.strategy?.default_strategy || 'macd_aggressive',
                default_initial_capital: parseFloat(initialCapitalInput?.value) || currentConfig.strategy?.default_initial_capital || 2000,
                default_positions: parseInt(totalPositionsInput?.value) || currentConfig.strategy?.default_positions || 10
            };
        }

        console.log('Saving config updates:', updates);

        const data = await fetchAPI('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(updates)
        });

        if (data.success) {
            showToast('配置已保存');
            await loadDataSourceStatus(); // Refresh status
            await saveFeishuSettings(); // Save Feishu config
        } else {
            console.error('Failed to save config:', data.message);
            showToast('保存失败: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error saving config:', error);
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

        // Send test request using fetchAPI
        const data = await fetchAPI('/api/settings/test-token', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                source: source,
                token: token
            })
        });

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
        const data = await fetchAPI('/api/settings/data-source/status');

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

        const data = await fetchAPI('/api/settings/data-source', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                priority: priority
            })
        });

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

// ==================== 飞书通知配置 ====================

// Load Feishu configuration
async function loadFeishuConfig() {
    try {
        const data = await fetchAPI('/api/feishu/config');

        if (data.success) {
            const config = data.data;
            console.log('Feishu config loaded:', config);

            // Load enabled status
            const enabledCheckbox = document.getElementById('feishuEnabled');
            if (enabledCheckbox) {
                enabledCheckbox.checked = config.enabled || false;
            }

            // Load bots
            renderFeishuBots(config.bots || []);

            // Load notification types
            const notifications = config.notifications || {};
            document.getElementById('notifySignals').checked = notifications.signal_alerts !== false;
            document.getElementById('notifyDataUpdates').checked = notifications.data_updates === true;
            document.getElementById('notifyBacktest').checked = notifications.backtest_complete === true;
            document.getElementById('notifyErrors').checked = notifications.error_alerts !== false;

            // Update test bot select
            updateFeishuTestBotSelect(config.bots || []);
        }
    } catch (error) {
        console.error('Error loading Feishu config:', error);
    }

    // Load Feishu notification scheduler config
    try {
        const data = await fetchAPI('/api/data-update/scheduler/status');

        if (data.success) {
            const status = data.data;
            const feishuNotif = status.feishu_notification || {};

            // Load enabled status
            const notifEnabledCheckbox = document.getElementById('feishuNotificationEnabled');
            if (notifEnabledCheckbox) {
                notifEnabledCheckbox.checked = feishuNotif.enabled || false;
            }

            // Load notification times
            const timesInput = document.getElementById('feishuNotificationTimes');
            if (timesInput && feishuNotif.times) {
                timesInput.value = feishuNotif.times.join(',');
            }

            console.log('Feishu notification scheduler loaded:', feishuNotif);
        }
    } catch (error) {
        console.error('Error loading Feishu notification scheduler:', error);
    }
}

// Render Feishu bots list
function renderFeishuBots(bots) {
    const container = document.getElementById('feishuBotsList');
    if (!container) return;

    if (!bots || bots.length === 0) {
        container.innerHTML = '<p style="color: #999; padding: 20px;">暂无飞书机器人，点击下方按钮添加</p>';
        return;
    }

    let html = '';
    bots.forEach((bot, index) => {
        html += `
            <div class="feishu-bot-card" data-bot-id="${bot.id}">
                <div class="bot-header">
                    <input type="text"
                           class="setting-input bot-name-input"
                           value="${bot.name || ''}"
                           placeholder="机器人名称"
                           data-bot-id="${bot.id}"
                           data-field="name">
                    <label class="toggle-switch" style="margin-left: auto;">
                        <input type="checkbox"
                               id="bot_enabled_${bot.id}"
                               ${bot.enabled !== false ? 'checked' : ''}
                               onchange="toggleFeishuBot('${bot.id}', this.checked)">
                        <label for="bot_enabled_${bot.id}" class="toggle"></label>
                    </label>
                </div>
                <div class="bot-fields">
                    <div class="bot-field">
                        <label>App ID</label>
                        <input type="text"
                               class="setting-input"
                               value="${bot.app_id || ''}"
                               placeholder="cli_xxxxxxxxx"
                               data-bot-id="${bot.id}"
                               data-field="app_id">
                    </div>
                    <div class="bot-field">
                        <label>App Secret</label>
                        <input type="password"
                               class="setting-input"
                               value="${bot.app_secret || ''}"
                               placeholder="应用密钥"
                               data-bot-id="${bot.id}"
                               data-field="app_secret">
                    </div>
                    <div class="bot-field">
                        <label>Chat ID</label>
                        <input type="text"
                               class="setting-input"
                               value="${bot.chat_id || ''}"
                               placeholder="oc_xxxxxxxxx"
                               data-bot-id="${bot.id}"
                               data-field="chat_id">
                    </div>
                </div>
                <div class="bot-actions">
                    <button class="btn btn-sm btn-secondary"
                            onclick="testFeishuBot('${bot.id}')">测试</button>
                    <button class="btn btn-sm btn-danger"
                            onclick="removeFeishuBot('${bot.id}')">删除</button>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;

    // Add event listeners for input changes
    container.querySelectorAll('input[data-bot-id]').forEach(input => {
        input.addEventListener('change', () => {
            const botId = input.dataset.botId;
            const field = input.dataset.field;
            const value = input.value;
            updateFeishuBotField(botId, field, value);
        });
    });
}

// Add new Feishu bot
function addFeishuBot() {
    const botId = 'bot_' + Date.now();

    // Get current config
    fetchAPI('/api/feishu/config').then(data => {
        if (data.success) {
            const config = data.data;
            const newBot = {
                id: botId,
                name: '新机器人',
                app_id: '',
                app_secret: '',
                chat_id: '',
                enabled: true
            };

            config.bots = config.bots || [];
            config.bots.push(newBot);

            // Save config
            saveFeishuConfig(config);

            // Re-render
            renderFeishuBots(config.bots);
            updateFeishuTestBotSelect(config.bots);
        }
    });
}

// Remove Feishu bot
function removeFeishuBot(botId) {
    if (!confirm('确定要删除这个机器人吗？')) return;

    fetchAPI('/api/feishu/config').then(data => {
        if (data.success) {
            const config = data.data;
            config.bots = (config.bots || []).filter(bot => bot.id !== botId);

            saveFeishuConfig(config);
            renderFeishuBots(config.bots);
            updateFeishuTestBotSelect(config.bots);
        }
    });
}

// Toggle Feishu bot enabled status
function toggleFeishuBot(botId, enabled) {
    fetchAPI('/api/feishu/config').then(data => {
        if (data.success) {
            const config = data.data;
            const bot = (config.bots || []).find(b => b.id === botId);
            if (bot) {
                bot.enabled = enabled;
                saveFeishuConfig(config);
            }
        }
    });
}

// Update Feishu bot field
function updateFeishuBotField(botId, field, value) {
    fetchAPI('/api/feishu/config').then(data => {
        if (data.success) {
            const config = data.data;
            const bot = (config.bots || []).find(b => b.id === botId);
            if (bot) {
                bot[field] = value;
                saveFeishuConfig(config);
            }
        }
    });
}

// Update Feishu test bot select
function updateFeishuTestBotSelect(bots) {
    const select = document.getElementById('feishuTestBot');
    if (!select) return;

    // Clear options
    select.innerHTML = '<option value="">选择机器人</option>';

    // Add enabled bots
    const enabledBots = bots.filter(bot => bot.enabled !== false);
    enabledBots.forEach(bot => {
        const option = document.createElement('option');
        option.value = bot.id;
        option.textContent = bot.name || bot.id;
        select.appendChild(option);
    });
}

// Test Feishu connection
async function testFeishuConnection() {
    const botId = document.getElementById('feishuTestBot')?.value;
    const message = document.getElementById('feishuTestMessage')?.value || '这是一条测试消息';

    if (!botId) {
        showToast('请选择要测试的机器人', 'error');
        return;
    }

    try {
        showToast('正在发送测试消息...');

        const data = await fetchAPI('/api/feishu/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                bot_id: botId,
                message: message
            })
        });

        if (data.success) {
            showToast('✓ 测试消息发送成功');
        } else {
            showToast('测试失败: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error testing Feishu:', error);
        showToast('测试失败: ' + error.message, 'error');
    }
}

// Test specific Feishu bot
async function testFeishuBot(botId) {
    try {
        showToast('正在测试连接...');

        const data = await fetchAPI('/api/feishu/test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                bot_id: botId,
                message: '这是一条测试消息'
            })
        });

        if (data.success) {
            showToast('✓ 测试成功');
        } else {
            showToast('测试失败: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Error testing bot:', error);
        showToast('测试失败: ' + error.message, 'error');
    }
}

// Save Feishu config
async function saveFeishuConfig(config) {
    try {
        await fetchAPI('/api/feishu/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
    } catch (error) {
        console.error('Error saving Feishu config:', error);
    }
}

// Save all Feishu settings
async function saveFeishuSettings() {
    try {
        const configData = await fetchAPI('/api/feishu/config');
        if (!configData.success) return;

        const feishuConfig = configData.data;

        // Update enabled status
        feishuConfig.enabled = document.getElementById('feishuEnabled')?.checked || false;

        // Update notification types
        feishuConfig.notifications = {
            signal_alerts: document.getElementById('notifySignals')?.checked !== false,
            data_updates: document.getElementById('notifyDataUpdates')?.checked === true,
            backtest_complete: document.getElementById('notifyBacktest')?.checked === true,
            error_alerts: document.getElementById('notifyErrors')?.checked !== false
        };

        // Save config
        await saveFeishuConfig(feishuConfig);

        // Save Feishu notification scheduler settings
        await saveFeishuNotificationSettings();

        showToast('飞书配置已保存');
    } catch (error) {
        console.error('Error saving Feishu settings:', error);
        showToast('保存失败: ' + error.message, 'error');
    }
}

// Save Feishu notification scheduler settings
async function saveFeishuNotificationSettings() {
    try {
        const enabled = document.getElementById('feishuNotificationEnabled')?.checked || false;
        const timesInput = document.getElementById('feishuNotificationTimes')?.value || '';
        const times = timesInput.split(',').map(t => t.trim()).filter(t => t);

        if (times.length === 0 && enabled) {
            showToast('请设置至少一个发送时间', 'error');
            return;
        }

        // Validate time format
        const timeRegex = /^([01]\d|2[0-3]):([0-5]\d)$/;
        for (const time of times) {
            if (!timeRegex.test(time)) {
                showToast(`无效的时间格式: ${time}，请使用 HH:MM 格式`, 'error');
                return;
            }
        }

        const data = await fetchAPI('/api/feishu/notification/configure', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                enabled: enabled,
                times: times
            })
        });

        if (data.success) {
            console.log('Feishu notification scheduler settings saved');
        } else {
            throw new Error(data.message || '保存失败');
        }
    } catch (error) {
        console.error('Error saving Feishu notification settings:', error);
        throw error;
    }
}

// Trigger Feishu notification immediately
async function triggerFeishuNotification() {
    try {
        const data = await fetchAPI('/api/feishu/notification/trigger', {
            method: 'POST'
        });

        if (data.success) {
            showToast('飞书消息发送任务已启动');
        } else {
            throw new Error(data.message || '发送失败');
        }
    } catch (error) {
        console.error('Error triggering Feishu notification:', error);
        showToast('发送失败: ' + error.message, 'error');
    }
}
