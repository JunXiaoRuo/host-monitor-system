// 全局变量
let currentSection = 'dashboard';
let serversData = [];
let schedulesData = [];
let reportsData = [];
let logsData = [];
let thresholdsData = {};
let servicesData = [];
let expandedServers = new Set();
let currentServiceModal = null;

// 全局变量用于跟踪当前分页和筛选状态
let currentLogsPage = 1;
let currentLogsFilters = {};
let currentReportsPage = 1;
let currentReportsFilters = {};

// 全局fetch包装器，处理401未授权错误
function safeFetch(url, options = {}) {
    return fetch(url, options)
        .then(response => {
            if (response.status === 401) {
                // 检查响应是否包含need_login标志
                return response.json().then(data => {
                    if (data.need_login) {
                        showAlert('登录已过期，请重新登录', 'warning');
                        setTimeout(() => {
                            window.location.href = '/login';
                        }, 2000);
                    }
                    throw new Error('Unauthorized');
                }).catch(() => {
                    // 如果解析JSON失败，直接跳转到登录页
                    window.location.href = '/login';
                    throw new Error('Unauthorized');
                });
            }
            return response;
        });
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);
    getCurrentUser(); // 获取当前用户信息
    initDashboard();
    initEventListeners();
    setInterval(refreshDashboard, 30000);
});

// 初始化事件监听器
function initEventListeners() {
    // 阈值设置表单提交
    const thresholdForm = document.getElementById('thresholdForm');
    if (thresholdForm) {
        thresholdForm.addEventListener('submit', function(e) {
            e.preventDefault();
            saveThresholds();
        });
    }
}

// 更新当前时间
function updateCurrentTime() {
    const now = new Date();
    document.getElementById('currentTime').textContent = now.toLocaleString('zh-CN');
}

// 显示指定的页面部分
function showSection(sectionName) {
    document.querySelectorAll('.section').forEach(section => {
        section.style.display = 'none';
    });
    
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    
    document.getElementById(sectionName).style.display = 'block';
    document.querySelector(`[href="#${sectionName}"]`).classList.add('active');
    
    currentSection = sectionName;
    
    switch(sectionName) {
        case 'dashboard': refreshDashboard(); break;
        case 'servers': loadServers(); break;
        case 'schedules': loadSchedules(); break;
        case 'services': loadServices(); break;
        case 'thresholds': loadThresholds(); break;
        case 'reports': loadReports(1, {}); break; // 使用新的分页API
        case 'logs': loadLogs(1, {}); break; // 使用新的分页API
        case 'notifications': loadNotifications(); break; // 加载通知通道
    }
}

// 初始化仪表板
function initDashboard() {
    refreshDashboard();
}

// 刷新仪表板
function refreshDashboard() {
    if (currentSection !== 'dashboard') return;
    
    safeFetch('/api/dashboard')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateDashboardMetrics(data.data);
                updateServerStatusList(data.data.server_status);
                updateLastUpdateTime();
            } else {
                showAlert('获取仪表板数据失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            if (error.message !== 'Unauthorized') {
                showAlert('刷新仪表板失败', 'danger');
            }
        });
}

// 更新仪表板指标
function updateDashboardMetrics(data) {
    document.getElementById('totalServers').textContent = data.total_servers || 0;
    document.getElementById('successServers').textContent = data.success_count || 0;
    document.getElementById('warningServers').textContent = data.warning_count || 0;
    document.getElementById('failedServers').textContent = data.failed_count || 0;
    
    // 更新服务总览
    if (data.services_overview) {
        updateServicesOverview(data.services_overview);
    }
}

// 更新服务器状态列表
function updateServerStatusList(serverStatus) {
    const container = document.getElementById('serverStatusList');
    
    if (!serverStatus || Object.keys(serverStatus).length === 0) {
        container.innerHTML = '<div class="text-center text-muted">暂无服务器状态数据</div>';
        return;
    }
    
    let html = '';
    for (const [serverId, status] of Object.entries(serverStatus)) {
        const statusClass = status.status === 'success' ? 'success' : 
                           status.status === 'warning' ? 'warning' : 'failed';
        
        html += `
            <div class="server-status ${statusClass}">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong>${status.server_name || '未知服务器'}</strong>
                        <span class="badge bg-${statusClass === 'success' ? 'success' : statusClass === 'warning' ? 'warning' : 'danger'} ms-2">
                            ${status.status}
                        </span>
                    </div>
                    <small>${status.monitor_time ? new Date(status.monitor_time).toLocaleString('zh-CN') : '未监控'}</small>
                </div>
                <div class="row mt-2">
                    <div class="col-md-3"><small>CPU: ${status.cpu_usage ? status.cpu_usage.toFixed(1) + '%' : 'N/A'}</small></div>
                    <div class="col-md-3"><small>内存: ${status.memory_usage ? status.memory_usage.toFixed(1) + '%' : 'N/A'}</small></div>
                    <div class="col-md-3"><small>告警: ${status.alert_count || 0}个</small></div>
                    <div class="col-md-3"><small>耗时: ${status.execution_time ? status.execution_time.toFixed(2) + 's' : 'N/A'}</small></div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

// 更新最后更新时间
function updateLastUpdateTime() {
    document.getElementById('lastUpdateTime').textContent = new Date().toLocaleString('zh-CN');
}

// 执行立即监控
function executeMonitor() {
    const btn = event.target.closest('button');
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 执行中...';
    btn.disabled = true;
    
    safeFetch('/api/monitor/execute', {method: 'POST'})
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('监控执行成功', 'success');
            setTimeout(refreshDashboard, 2000);
        } else {
            showAlert('监控执行失败: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        if (error.message !== 'Unauthorized') {
            showAlert('执行监控失败', 'danger');
        }
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

// 显示警告信息
function showAlert(message, type) {
    const alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show position-fixed" style="top: 20px; right: 20px; z-index: 9999;">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    document.body.insertAdjacentHTML('beforeend', alertHtml);
    
    // 自动消失
    setTimeout(() => {
        const alert = document.querySelector('.alert:last-child');
        if (alert) {
            new bootstrap.Alert(alert).close();
        }
    }, 5000);
}

// 加载服务器列表
function loadServers() {
    safeFetch('/api/servers')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                serversData = data.data.servers;
                renderServersTable(serversData);
            } else {
                showAlert('加载服务器列表失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            if (error.message !== 'Unauthorized') {
                console.error('加载服务器列表失败:', error);
                showAlert('加载服务器列表失败', 'danger');
            }
        });
}

// 渲染服务器表格
function renderServersTable(servers) {
    const tbody = document.getElementById('serversTableBody');
    
    if (!servers || servers.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted">
                    <i class="bi bi-inbox"></i>
                    暂无服务器数据
                </td>
            </tr>
        `;
        return;
    }
    
    let html = '';
    servers.forEach(server => {
        const statusClass = server.status === 'active' ? 'success' : 'secondary';
        const statusText = server.status === 'active' ? '启用' : '禁用';
        
        html += `
            <tr>
                <td>${server.name}</td>
                <td>${server.host}</td>
                <td>${server.port}</td>
                <td>${server.username}</td>
                <td>
                    <span class="badge bg-${statusClass}">${statusText}</span>
                </td>
                <td>${server.updated_at ? new Date(server.updated_at).toLocaleString('zh-CN') : '-'}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="testConnection(${server.id})" title="测试连接">
                        <i class="bi bi-wifi"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-secondary me-1" onclick="editServer(${server.id})" title="编辑">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteServer(${server.id})" title="删除">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// 显示添加服务器模态框
function showAddServerModal() {
    showServerModal();
}

// 显示服务器模态框（添加/编辑）
function showServerModal(serverId = null) {
    const isEdit = serverId !== null;
    const title = isEdit ? '编辑服务器' : '添加服务器';
    
    const modalHtml = `
        <div class="modal fade" id="serverModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="serverForm">
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="serverName" class="form-label">服务器名称 *</label>
                                        <input type="text" class="form-control" id="serverName" required>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="serverHost" class="form-label">主机地址 *</label>
                                        <input type="text" class="form-control" id="serverHost" required>
                                    </div>
                                </div>
                            </div>
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="serverPort" class="form-label">SSH端口</label>
                                        <input type="number" class="form-control" id="serverPort" value="22" min="1" max="65535">
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="serverUsername" class="form-label">用户名 *</label>
                                        <input type="text" class="form-control" id="serverUsername" required>
                                    </div>
                                </div>
                            </div>
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="serverPassword" class="form-label">密码</label>
                                        <input type="password" class="form-control" id="serverPassword">
                                        <div class="form-text">密码和私钥文件至少填写一项</div>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="serverPrivateKey" class="form-label">私钥文件路径</label>
                                        <input type="text" class="form-control" id="serverPrivateKey">
                                        <div class="form-text">如: /home/user/.ssh/id_rsa</div>
                                    </div>
                                </div>
                            </div>
                            <div class="mb-3">
                                <label for="serverDescription" class="form-label">描述</label>
                                <textarea class="form-control" id="serverDescription" rows="3"></textarea>
                            </div>
                            <div class="mb-3">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="serverActive" checked>
                                    <label class="form-check-label" for="serverActive">
                                        启用服务器
                                    </label>
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-outline-info" onclick="testServerConnection()">测试连接</button>
                        <button type="button" class="btn btn-primary" onclick="saveServer(${serverId})">${isEdit ? '更新' : '保存'}</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('modalContainer').innerHTML = modalHtml;
    
    // 如果是编辑模式，填充数据
    if (isEdit) {
        const server = serversData.find(s => s.id === serverId);
        if (server) {
            document.getElementById('serverName').value = server.name;
            document.getElementById('serverHost').value = server.host;
            document.getElementById('serverPort').value = server.port;
            document.getElementById('serverUsername').value = server.username;
            document.getElementById('serverDescription').value = server.description || '';
            document.getElementById('serverActive').checked = server.status === 'active';
        }
    }
    
    const modal = new bootstrap.Modal(document.getElementById('serverModal'));
    modal.show();
}

// 测试服务器连接（在模态框中）
function testServerConnection() {
    const formData = {
        host: document.getElementById('serverHost').value,
        port: parseInt(document.getElementById('serverPort').value) || 22,
        username: document.getElementById('serverUsername').value,
        password: document.getElementById('serverPassword').value,
        private_key_path: document.getElementById('serverPrivateKey').value
    };
    
    if (!formData.host || !formData.username) {
        showAlert('请填写主机地址和用户名', 'warning');
        return;
    }
    
    if (!formData.password && !formData.private_key_path) {
        showAlert('请填写密码或私钥文件路径', 'warning');
        return;
    }
    
    const btn = event.target;
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 测试中...';
    btn.disabled = true;
    
    safeFetch('/api/servers/test', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('连接测试成功', 'success');
        } else {
            showAlert('连接测试失败: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('测试连接失败:', error);
        showAlert('测试连接失败', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

// 保存服务器
function saveServer(serverId = null) {
    const formData = {
        name: document.getElementById('serverName').value,
        host: document.getElementById('serverHost').value,
        port: parseInt(document.getElementById('serverPort').value) || 22,
        username: document.getElementById('serverUsername').value,
        password: document.getElementById('serverPassword').value,
        private_key_path: document.getElementById('serverPrivateKey').value,
        description: document.getElementById('serverDescription').value,
        status: document.getElementById('serverActive').checked ? 'active' : 'inactive'
    };
    
    if (!formData.name || !formData.host || !formData.username) {
        showAlert('请填写必填字段', 'warning');
        return;
    }
    
    if (!formData.password && !formData.private_key_path) {
        showAlert('请填写密码或私钥文件路径', 'warning');
        return;
    }
    
    const url = serverId ? `/api/servers/${serverId}` : '/api/servers';
    const method = serverId ? 'PUT' : 'POST';
    
    safeFetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(serverId ? '服务器更新成功' : '服务器添加成功', 'success');
            bootstrap.Modal.getInstance(document.getElementById('serverModal')).hide();
            loadServers();
        } else {
            showAlert((serverId ? '服务器更新失败' : '服务器添加失败') + ': ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('保存服务器失败:', error);
        showAlert('保存服务器失败', 'danger');
    });
}

// 编辑服务器
function editServer(serverId) {
    showServerModal(serverId);
}

// 测试连接
function testConnection(serverId) {
    const btn = event.target.closest('button');
    const originalHtml = btn.innerHTML;
    
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i>';
    btn.disabled = true;
    
    safeFetch(`/api/servers/${serverId}/test`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('连接测试成功', 'success');
        } else {
            showAlert('连接测试失败: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('测试连接失败:', error);
        showAlert('测试连接失败', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    });
}

// 删除服务器
function deleteServer(serverId) {
    const server = serversData.find(s => s.id === serverId);
    if (!server) return;
    
    if (confirm(`确定要删除服务器 "${server.name}" 吗？此操作不可撤销。`)) {
        safeFetch(`/api/servers/${serverId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('服务器删除成功', 'success');
                loadServers();
            } else {
                showAlert('删除服务器失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('删除服务器失败:', error);
            showAlert('删除服务器失败', 'danger');
        });
    }
}

// 加载计划任务
function loadSchedules() {
    safeFetch('/api/schedules')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                schedulesData = data.data;
                renderSchedulesTable(schedulesData);
            } else {
                showAlert('加载计划任务失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('加载计划任务失败:', error);
            showAlert('加载计划任务失败', 'danger');
        });
}

// 渲染计划任务表格
function renderSchedulesTable(schedules) {
    const tbody = document.getElementById('schedulesTableBody');
    
    if (!schedules || schedules.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted">
                    <i class="bi bi-inbox"></i>
                    暂无计划任务
                </td>
            </tr>
        `;
        return;
    }
    
    let html = '';
    schedules.forEach(schedule => {
        const statusClass = schedule.is_active ? 'success' : 'secondary';
        const statusText = schedule.is_active ? '启用' : '禁用';
        
        const nextRun = schedule.next_run ? 
            new Date(schedule.next_run).toLocaleString('zh-CN') : '-';
        const lastRun = schedule.last_run ? 
            new Date(schedule.last_run).toLocaleString('zh-CN') : '-';
        
        let configText = '';
        const config = schedule.schedule_config;
        if (schedule.task_type === 'daily') {
            configText = `每日 ${config.hour || 0}:${(config.minute || 0).toString().padStart(2, '0')}`;
        } else if (schedule.task_type === 'weekly') {
            const days = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
            configText = `${days[config.day_of_week || 0]} ${config.hour || 0}:${(config.minute || 0).toString().padStart(2, '0')}`;
        } else if (schedule.task_type === 'monthly') {
            configText = `每月${config.day || 1}日 ${config.hour || 0}:${(config.minute || 0).toString().padStart(2, '0')}`;
        }
        
        html += `
            <tr>
                <td>${schedule.name}</td>
                <td>
                    <span class="badge bg-info">${schedule.task_type}</span>
                </td>
                <td>${configText}</td>
                <td>
                    <span class="badge bg-${statusClass}">${statusText}</span>
                </td>
                <td>${nextRun}</td>
                <td>${lastRun}</td>
                <td>
                    <button class="btn btn-sm btn-outline-secondary me-1" onclick="editSchedule(${schedule.id})" title="编辑">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteSchedule(${schedule.id})" title="删除">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// 显示添加计划任务模态框
function showAddScheduleModal() {
    showScheduleModal();
}

// 显示计划任务模态框（添加/编辑）
function showScheduleModal(scheduleId = null) {
    const isEdit = scheduleId !== null;
    const title = isEdit ? '编辑计划任务' : '添加计划任务';
    
    const modalHtml = `
        <div class="modal fade" id="scheduleModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="scheduleForm">
                            <div class="mb-3">
                                <label for="scheduleName" class="form-label">任务名称 *</label>
                                <input type="text" class="form-control" id="scheduleName" required>
                            </div>
                            <div class="mb-3">
                                <label for="scheduleType" class="form-label">任务类型 *</label>
                                <select class="form-select" id="scheduleType" onchange="updateScheduleConfig()" required>
                                    <option value="">请选择</option>
                                    <option value="daily">每日</option>
                                    <option value="weekly">每周</option>
                                    <option value="monthly">每月</option>
                                </select>
                            </div>
                            <div id="scheduleConfig"></div>
                            <div class="mb-3">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="scheduleActive" checked>
                                    <label class="form-check-label" for="scheduleActive">
                                        启用任务
                                    </label>
                                </div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" onclick="saveSchedule(${scheduleId})">${isEdit ? '更新' : '保存'}</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('modalContainer').innerHTML = modalHtml;
    
    // 如果是编辑模式，填充数据
    if (isEdit) {
        const schedule = schedulesData.find(s => s.id === scheduleId);
        if (schedule) {
            document.getElementById('scheduleName').value = schedule.name;
            document.getElementById('scheduleType').value = schedule.task_type;
            document.getElementById('scheduleActive').checked = schedule.is_active;
            updateScheduleConfig();
            
            // 填充配置数据
            const config = schedule.schedule_config;
            if (schedule.task_type === 'daily') {
                document.getElementById('dailyHour').value = config.hour || 0;
                document.getElementById('dailyMinute').value = config.minute || 0;
            } else if (schedule.task_type === 'weekly') {
                document.getElementById('weeklyDay').value = config.day_of_week || 0;
                document.getElementById('weeklyHour').value = config.hour || 0;
                document.getElementById('weeklyMinute').value = config.minute || 0;
            } else if (schedule.task_type === 'monthly') {
                document.getElementById('monthlyDay').value = config.day || 1;
                document.getElementById('monthlyHour').value = config.hour || 0;
                document.getElementById('monthlyMinute').value = config.minute || 0;
            }
        }
    }
    
    const modal = new bootstrap.Modal(document.getElementById('scheduleModal'));
    modal.show();
}

// 更新计划任务配置界面
function updateScheduleConfig() {
    const type = document.getElementById('scheduleType').value;
    const container = document.getElementById('scheduleConfig');
    
    let html = '';
    
    if (type === 'daily') {
        html = `
            <div class="row">
                <div class="col-md-6">
                    <div class="mb-3">
                        <label for="dailyHour" class="form-label">小时</label>
                        <select class="form-select" id="dailyHour">
                            ${Array.from({length: 24}, (_, i) => 
                                `<option value="${i}">${i.toString().padStart(2, '0')}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="mb-3">
                        <label for="dailyMinute" class="form-label">分钟</label>
                        <select class="form-select" id="dailyMinute">
                            ${Array.from({length: 60}, (_, i) => 
                                `<option value="${i}">${i.toString().padStart(2, '0')}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
            </div>
        `;
    } else if (type === 'weekly') {
        html = `
            <div class="mb-3">
                <label for="weeklyDay" class="form-label">星期</label>
                <select class="form-select" id="weeklyDay">
                    <option value="0">周一</option>
                    <option value="1">周二</option>
                    <option value="2">周三</option>
                    <option value="3">周四</option>
                    <option value="4">周五</option>
                    <option value="5">周六</option>
                    <option value="6">周日</option>
                </select>
            </div>
            <div class="row">
                <div class="col-md-6">
                    <div class="mb-3">
                        <label for="weeklyHour" class="form-label">小时</label>
                        <select class="form-select" id="weeklyHour">
                            ${Array.from({length: 24}, (_, i) => 
                                `<option value="${i}">${i.toString().padStart(2, '0')}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="mb-3">
                        <label for="weeklyMinute" class="form-label">分钟</label>
                        <select class="form-select" id="weeklyMinute">
                            ${Array.from({length: 60}, (_, i) => 
                                `<option value="${i}">${i.toString().padStart(2, '0')}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
            </div>
        `;
    } else if (type === 'monthly') {
        html = `
            <div class="mb-3">
                <label for="monthlyDay" class="form-label">日期</label>
                <select class="form-select" id="monthlyDay">
                    ${Array.from({length: 31}, (_, i) => 
                        `<option value="${i + 1}">${i + 1}日</option>`
                    ).join('')}
                </select>
            </div>
            <div class="row">
                <div class="col-md-6">
                    <div class="mb-3">
                        <label for="monthlyHour" class="form-label">小时</label>
                        <select class="form-select" id="monthlyHour">
                            ${Array.from({length: 24}, (_, i) => 
                                `<option value="${i}">${i.toString().padStart(2, '0')}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="mb-3">
                        <label for="monthlyMinute" class="form-label">分钟</label>
                        <select class="form-select" id="monthlyMinute">
                            ${Array.from({length: 60}, (_, i) => 
                                `<option value="${i}">${i.toString().padStart(2, '0')}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

// 保存计划任务
function saveSchedule(scheduleId = null) {
    const taskType = document.getElementById('scheduleType').value;
    
    if (!taskType) {
        showAlert('请选择任务类型', 'warning');
        return;
    }
    
    let scheduleConfig = {};
    
    if (taskType === 'daily') {
        scheduleConfig = {
            hour: parseInt(document.getElementById('dailyHour').value),
            minute: parseInt(document.getElementById('dailyMinute').value)
        };
    } else if (taskType === 'weekly') {
        scheduleConfig = {
            day_of_week: parseInt(document.getElementById('weeklyDay').value),
            hour: parseInt(document.getElementById('weeklyHour').value),
            minute: parseInt(document.getElementById('weeklyMinute').value)
        };
    } else if (taskType === 'monthly') {
        scheduleConfig = {
            day: parseInt(document.getElementById('monthlyDay').value),
            hour: parseInt(document.getElementById('monthlyHour').value),
            minute: parseInt(document.getElementById('monthlyMinute').value)
        };
    }
    
    const formData = {
        name: document.getElementById('scheduleName').value,
        task_type: taskType,
        schedule_config: scheduleConfig,
        is_active: document.getElementById('scheduleActive').checked
    };
    
    if (!formData.name) {
        showAlert('请填写任务名称', 'warning');
        return;
    }
    
    const url = scheduleId ? `/api/schedules/${scheduleId}` : '/api/schedules';
    const method = scheduleId ? 'PUT' : 'POST';
    
    safeFetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(scheduleId ? '任务更新成功' : '任务添加成功', 'success');
            bootstrap.Modal.getInstance(document.getElementById('scheduleModal')).hide();
            loadSchedules();
        } else {
            showAlert((scheduleId ? '任务更新失败' : '任务添加失败') + ': ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('保存任务失败:', error);
        showAlert('保存任务失败', 'danger');
    });
}

// 编辑计划任务
function editSchedule(scheduleId) {
    showScheduleModal(scheduleId);
}

// 删除计划任务
function deleteSchedule(scheduleId) {
    const schedule = schedulesData.find(s => s.id === scheduleId);
    if (!schedule) return;
    
    if (confirm(`确定要删除任务 "${schedule.name}" 吗？此操作不可撤销。`)) {
        safeFetch(`/api/schedules/${scheduleId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('任务删除成功', 'success');
                loadSchedules();
            } else {
                showAlert('删除任务失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('删除任务失败:', error);
            showAlert('删除任务失败', 'danger');
        });
    }
}

// 加载阈值设置
function loadThresholds() {
    safeFetch('/api/thresholds')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                thresholdsData = data.data;
                document.getElementById('cpuThreshold').value = data.data.cpu_threshold;
                document.getElementById('memoryThreshold').value = data.data.memory_threshold;
                document.getElementById('diskThreshold').value = data.data.disk_threshold;
            } else {
                showAlert('加载阈值配置失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('加载阈值配置失败:', error);
            showAlert('加载阈值配置失败', 'danger');
        });
}

// 保存阈值设置
function saveThresholds() {
    const formData = {
        cpu_threshold: parseFloat(document.getElementById('cpuThreshold').value),
        memory_threshold: parseFloat(document.getElementById('memoryThreshold').value),
        disk_threshold: parseFloat(document.getElementById('diskThreshold').value)
    };
    
    // 验证数据
    if (formData.cpu_threshold < 1 || formData.cpu_threshold > 100 ||
        formData.memory_threshold < 1 || formData.memory_threshold > 100 ||
        formData.disk_threshold < 1 || formData.disk_threshold > 100) {
        showAlert('阈值必须在1-100之间', 'warning');
        return;
    }
    
    safeFetch('/api/thresholds', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('阈值配置保存成功', 'success');
            thresholdsData = formData;
        } else {
            showAlert('保存阈值配置失败: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('保存阈值配置失败:', error);
        showAlert('保存阈值配置失败', 'danger');
    });
}


function loadReports(page = 1, filters = {}) {
    currentReportsPage = page;
    currentReportsFilters = filters;
    
    // 构建URL参数
    const params = new URLSearchParams();
    params.append('page', page);
    params.append('per_page', 20);
    
    // 添加筛选参数
    if (filters.type) {
        params.append('type', filters.type);
    }
    if (filters.start_date) {
        params.append('start_date', filters.start_date);
    }
    if (filters.end_date) {
        params.append('end_date', filters.end_date);
    }
    
    const url = `/api/reports?${params.toString()}`;
    
    safeFetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                reportsData = data.data.reports; // 适配新的API响应格式
                renderReportsTable(reportsData);
                renderReportsPagination(data.data.pagination);
            } else {
                showAlert('加载报告列表失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('加载报告列表失败:', error);
            showAlert('加载报告列表失败', 'danger');
        });
}

// 渲染报告表格
function renderReportsTable(reports) {
    const tbody = document.getElementById('reportsTableBody');
    
    // 确保 reportsData 全局变量更新
    reportsData = reports;
    
    if (!reports || reports.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-muted">
                    <i class="bi bi-inbox"></i>
                    暂无报告数据
                </td>
            </tr>
        `;
        return;
    }
    
    let html = '';
    reports.forEach(report => {
        const typeClass = report.report_type === 'manual' ? 'primary' : 'info';
        const typeText = report.report_type === 'manual' ? '手动' : '定时';
        
        html += `
            <tr>
                <td>
                    <input type="checkbox" class="report-checkbox" value="${report.id}" onchange="updateReportsSelection()">
                </td>
                <td>${report.report_name}</td>
                <td>
                    <span class="badge bg-${typeClass}">${typeText}</span>
                </td>
                <td>${new Date(report.created_at).toLocaleString('zh-CN')}</td>
                <td>${formatFileSize(report.server_count * 1024)}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="downloadReport(${report.id})" title="下载">
                        <i class="bi bi-download"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteReport(${report.id})" title="删除">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
    
    // 重置选择状态
    clearReportsSelection();
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 下载报告
function downloadReport(reportId) {
    window.open(`/api/reports/${reportId}/download`, '_blank');
}

// 删除报告
function deleteReport(reportId) {
    // 确保 reportId是数字
    const id = parseInt(reportId);
    
    console.log('尝试删除报告id:', id);
    console.log('当前 reportsData:', reportsData);
    
    const report = reportsData.find(r => r.id === id);
    if (!report) {
        console.error('找不到报告，ID:', id);
        showAlert('找不到指定的报告', 'warning');
        return;
    }
    
    if (confirm(`确定要删除报告 "${report.report_name}" 吗？此操作不可撤销。`)) {
        console.log('用户确认删除报告:', report.report_name);
        
        safeFetch(`/api/reports/${id}`, {
            method: 'DELETE'
        })
        .then(response => {
            console.log('删除报告响应状态:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('删除报告响应数据:', data);
            if (data.success) {
                showAlert('报告删除成功', 'success');
                loadReports(currentReportsPage, currentReportsFilters); // 使用当前页面和筛选条件重新加载
            } else {
                showAlert('删除报告失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('删除报告异常:', error);
            showAlert('删除报告失败', 'danger');
        });
    } else {
        console.log('用户取消删除操作');
    }
}

// 生成报告
function generateReport() {
    const btn = event.target;
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 生成中...';
    btn.disabled = true;
    
    safeFetch('/api/reports/generate', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('报告生成成功', 'success');
            loadReports(1, currentReportsFilters); // 使用新的分页加载方式
        } else {
            showAlert('生成报告失败: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('生成报告失败:', error);
        showAlert('生成报告失败', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}


function loadLogs(page = 1, filters = {}) {
    currentLogsPage = page;
    currentLogsFilters = filters;
    
    // 构建URL参数
    const params = new URLSearchParams();
    params.append('page', page);
    params.append('per_page', 20);
    
    // 添加筛选参数
    if (filters.server_id) {
        params.append('server_id', filters.server_id);
    }
    if (filters.status) {
        params.append('status', filters.status);
    }
    if (filters.start_date) {
        params.append('start_date', filters.start_date);
    }
    if (filters.end_date) {
        params.append('end_date', filters.end_date);
    }
    
    const url = `/api/logs?${params.toString()}`;
    
    safeFetch(url)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                logsData = data.data.logs; // 适配新的API响应格式
                renderLogsTable(logsData);
                renderLogsPagination(data.data.pagination);
                loadServerFilterOptions();
            } else {
                showAlert('加载监控日志失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('加载监控日志失败:', error);
            showAlert('加载监控日志失败', 'danger');
        });
}

// 加载服务器过滤器选项
function loadServerFilterOptions() {
    if (serversData.length === 0) {
        safeFetch('/api/servers')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    serversData = data.data.servers;
                    updateServerFilterOptions();
                }
            })
            .catch(error => {
                console.error('加载服务器列表失败:', error);
            });
    } else {
        updateServerFilterOptions();
    }
}

// 更新服务器过滤器选项
function updateServerFilterOptions() {
    const select = document.getElementById('logServerFilter');
    const currentValue = select.value;
    
    let html = '<option value="">所有服务器</option>';
    serversData.forEach(server => {
        html += `<option value="${server.id}">${server.name}</option>`;
    });
    
    select.innerHTML = html;
    select.value = currentValue;
}

// 渲染日志表格
function renderLogsTable(logs) {
    const tbody = document.getElementById('logsTableBody');
    
    // 确保 logsData 全局变量更新
    logsData = logs;
    
    if (!logs || logs.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="text-center text-muted">
                    <i class="bi bi-inbox"></i>
                    暂无日志数据
                </td>
            </tr>
        `;
        return;
    }
    
    let html = '';
    logs.forEach(log => {
        const statusClass = log.status === 'success' ? 'success' : 
                           log.status === 'warning' ? 'warning' : 'danger';
        
        html += `
            <tr>
                <td>
                    <input type="checkbox" class="log-checkbox" value="${log.id}" onchange="updateLogsSelection()">
                </td>
                <td>${new Date(log.monitor_time).toLocaleString('zh-CN')}</td>
                <td>${log.server_name}</td>
                <td>
                    <span class="badge bg-${statusClass}">${log.status}</span>
                </td>
                <td>${log.cpu_usage ? log.cpu_usage.toFixed(1) + '%' : 'N/A'}</td>
                <td>${log.memory_usage ? log.memory_usage.toFixed(1) + '%' : 'N/A'}</td>
                <td>${log.alert_info ? log.alert_info.length : 0}</td>
                <td>${log.execution_time ? log.execution_time.toFixed(2) + 's' : 'N/A'}</td>
                <td>
                    <button class="btn btn-sm btn-outline-info me-1" onclick="viewLogDetail(${log.id})" title="查看详情">
                        <i class="bi bi-eye"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteLog(${log.id})" title="删除">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
    
    // 重置选择状态
    clearLogsSelection();
}

// 查看日志详情
function viewLogDetail(logId) {
    safeFetch(`/api/logs/${logId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showLogDetailModal(data.data);
            } else {
                showAlert('获取日志详情失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('获取日志详情失败:', error);
            showAlert('获取日志详情失败', 'danger');
        });
}

// 显示日志详情模态框
function showLogDetailModal(logData) {
    const statusClass = logData.status === 'success' ? 'success' : 
                       logData.status === 'warning' ? 'warning' : 'danger';
    
    // 格式化磁盘信息
    let diskInfoHtml = '';
    if (logData.disk_info && logData.disk_info.length > 0) {
        diskInfoHtml = `
            <table class="table table-sm table-striped">
                <thead>
                    <tr>
                        <th>文件系统</th>
                        <th>挂载点</th>
                        <th>大小</th>
                        <th>已用</th>
                        <th>可用</th>
                        <th>使用率</th>
                    </tr>
                </thead>
                <tbody>
                    ${logData.disk_info.map(disk => `
                        <tr ${disk.use_percent > 80 ? 'class="table-warning"' : ''}>
                            <td>${disk.filesystem}</td>
                            <td>${disk.mounted_on}</td>
                            <td>${disk.size}</td>
                            <td>${disk.used}</td>
                            <td>${disk.available}</td>
                            <td>${disk.use_percent.toFixed(1)}%</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    } else {
        diskInfoHtml = '<p class="text-muted">无磁盘信息</p>';
    }
    
    // 格式化系统信息
    let systemInfoHtml = '';
    if (logData.system_info && Object.keys(logData.system_info).length > 0) {
        systemInfoHtml = Object.entries(logData.system_info).map(([key, value]) => `
            <div class="row mb-2">
                <div class="col-4"><strong>${key}:</strong></div>
                <div class="col-8">${value}</div>
            </div>
        `).join('');
    } else {
        systemInfoHtml = '<p class="text-muted">无系统信息</p>';
    }
    
    // 格式化告警信息
    let alertsHtml = '';
    if (logData.alert_info && logData.alert_info.length > 0) {
        alertsHtml = logData.alert_info.map(alert => `
            <div class="alert alert-warning alert-sm mb-2">
                <strong>${alert.type.toUpperCase()}告警:</strong> ${alert.message}
            </div>
        `).join('');
    } else {
        alertsHtml = '<p class="text-muted">无告警信息</p>';
    }
    
    const modalHtml = `
        <div class="modal fade" id="logDetailModal" tabindex="-1">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-list-ul"></i>
                            监控日志详情 - ${logData.server_name}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <!-- 基本信息 -->
                        <div class="row mb-4">
                            <div class="col-md-6">
                                <div class="card">
                                    <div class="card-header">
                                        <h6 class="mb-0"><i class="bi bi-info-circle"></i> 基本信息</h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>状态:</strong></div>
                                            <div class="col-8">
                                                <span class="badge bg-${statusClass}">${logData.status}</span>
                                            </div>
                                        </div>
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>监控时间:</strong></div>
                                            <div class="col-8">${new Date(logData.monitor_time).toLocaleString('zh-CN')}</div>
                                        </div>
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>执行耗时:</strong></div>
                                            <div class="col-8">${logData.execution_time ? logData.execution_time.toFixed(2) + '秒' : 'N/A'}</div>
                                        </div>
                                        ${logData.error_message ? `
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>错误信息:</strong></div>
                                            <div class="col-8 text-danger">${logData.error_message}</div>
                                        </div>
                                        ` : ''}
                                    </div>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div class="card">
                                    <div class="card-header">
                                        <h6 class="mb-0"><i class="bi bi-speedometer2"></i> 系统资源</h6>
                                    </div>
                                    <div class="card-body">
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>CPU使用率:</strong></div>
                                            <div class="col-8">
                                                ${logData.cpu_usage ? `
                                                    <span class="${logData.cpu_usage > 80 ? 'text-danger' : ''}">
                                                        ${logData.cpu_usage.toFixed(1)}%
                                                    </span>
                                                ` : 'N/A'}
                                            </div>
                                        </div>
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>内存使用率:</strong></div>
                                            <div class="col-8">
                                                ${logData.memory_usage ? `
                                                    <span class="${logData.memory_usage > 80 ? 'text-danger' : ''}">
                                                        ${logData.memory_usage.toFixed(1)}%
                                                    </span>
                                                ` : 'N/A'}
                                            </div>
                                        </div>
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>告警数量:</strong></div>
                                            <div class="col-8">
                                                <span class="badge bg-${logData.alert_info && logData.alert_info.length > 0 ? 'warning' : 'success'}">
                                                    ${logData.alert_info ? logData.alert_info.length : 0}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <!-- 磁盘信息 -->
                        <div class="card mb-4">
                            <div class="card-header">
                                <h6 class="mb-0"><i class="bi bi-hdd"></i> 磁盘使用情况</h6>
                            </div>
                            <div class="card-body">
                                ${diskInfoHtml}
                            </div>
                        </div>
                        
                        <!-- 告警信息 -->
                        <div class="card mb-4">
                            <div class="card-header">
                                <h6 class="mb-0"><i class="bi bi-exclamation-triangle"></i> 告警信息</h6>
                            </div>
                            <div class="card-body">
                                ${alertsHtml}
                            </div>
                        </div>
                        
                        <!-- 系统信息 -->
                        <div class="card">
                            <div class="card-header">
                                <h6 class="mb-0"><i class="bi bi-gear"></i> 系统信息</h6>
                            </div>
                            <div class="card-body">
                                ${systemInfoHtml}
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">关闭</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('modalContainer').innerHTML = modalHtml;
    const modal = new bootstrap.Modal(document.getElementById('logDetailModal'));
    modal.show();
}

// 删除日志
function deleteLog(logId) {
    // 确保 logId是数字
    const id = parseInt(logId);
    
    console.log('尝试删除日志ID:', id);
    console.log('当前 logsData:', logsData);
    
    const log = logsData.find(l => l.id === id);
    if (!log) {
        console.error('找不到日志，ID:', id);
        showAlert('找不到指定的日志', 'warning');
        return;
    }
    
    if (confirm(`确定要删除日志 "${log.server_name} - ${new Date(log.monitor_time).toLocaleString('zh-CN')}" 吗？此操作不可撤销。`)) {
        console.log('用户确认删除日志:', log.server_name);
        
        safeFetch(`/api/logs/${id}`, {
            method: 'DELETE'
        })
        .then(response => {
            console.log('删除日志响应状态:', response.status);
            return response.json();
        })
        .then(data => {
            console.log('删除日志响应数据:', data);
            if (data.success) {
                showAlert('日志删除成功', 'success');
                loadLogs(currentLogsPage, currentLogsFilters); // 使用当前页面和筛选条件重新加载
            } else {
                showAlert('删除日志失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('删除日志异常:', error);
            showAlert('删除日志失败', 'danger');
        });
    } else {
        console.log('用户取消删除操作');
    }
}

// 刷新日志
function refreshLogs() {
    loadLogs(currentLogsPage, currentLogsFilters);
}

// 渲染日志分页控件
function renderLogsPagination(pagination) {
    const container = document.getElementById('logsPagination');
    if (!container || !pagination) return;
    
    let html = '';
    
    // 上一页
    if (pagination.has_prev) {
        html += `<li class="page-item">
            <a class="page-link" href="#" onclick="loadLogs(${pagination.page - 1}, currentLogsFilters)">
                <i class="bi bi-chevron-left"></i>
            </a>
        </li>`;
    } else {
        html += `<li class="page-item disabled">
            <span class="page-link"><i class="bi bi-chevron-left"></i></span>
        </li>`;
    }
    
    // 页码
    const startPage = Math.max(1, pagination.page - 2);
    const endPage = Math.min(pagination.pages, pagination.page + 2);
    
    if (startPage > 1) {
        html += `<li class="page-item">
            <a class="page-link" href="#" onclick="loadLogs(1, currentLogsFilters)">1</a>
        </li>`;
        if (startPage > 2) {
            html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        if (i === pagination.page) {
            html += `<li class="page-item active">
                <span class="page-link">${i}</span>
            </li>`;
        } else {
            html += `<li class="page-item">
                <a class="page-link" href="#" onclick="loadLogs(${i}, currentLogsFilters)">${i}</a>
            </li>`;
        }
    }
    
    if (endPage < pagination.pages) {
        if (endPage < pagination.pages - 1) {
            html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
        html += `<li class="page-item">
            <a class="page-link" href="#" onclick="loadLogs(${pagination.pages}, currentLogsFilters)">${pagination.pages}</a>
        </li>`;
    }
    
    // 下一页
    if (pagination.has_next) {
        html += `<li class="page-item">
            <a class="page-link" href="#" onclick="loadLogs(${pagination.page + 1}, currentLogsFilters)">
                <i class="bi bi-chevron-right"></i>
            </a>
        </li>`;
    } else {
        html += `<li class="page-item disabled">
            <span class="page-link"><i class="bi bi-chevron-right"></i></span>
        </li>`;
    }
    
    container.innerHTML = html;
    
    // 更新分页信息
    const info = document.getElementById('logsPageInfo');
    if (info) {
        const start = (pagination.page - 1) * pagination.per_page + 1;
        const end = Math.min(pagination.page * pagination.per_page, pagination.total);
        info.textContent = `显示 ${start}-${end} 条，共 ${pagination.total} 条记录`;
    }
}

// 渲染报告分页控件
function renderReportsPagination(pagination) {
    const container = document.getElementById('reportsPagination');
    if (!container || !pagination) return;
    
    let html = '';
    
    // 上一页
    if (pagination.has_prev) {
        html += `<li class="page-item">
            <a class="page-link" href="#" onclick="loadReports(${pagination.page - 1}, currentReportsFilters)">
                <i class="bi bi-chevron-left"></i>
            </a>
        </li>`;
    } else {
        html += `<li class="page-item disabled">
            <span class="page-link"><i class="bi bi-chevron-left"></i></span>
        </li>`;
    }
    
    // 页码
    const startPage = Math.max(1, pagination.page - 2);
    const endPage = Math.min(pagination.pages, pagination.page + 2);
    
    if (startPage > 1) {
        html += `<li class="page-item">
            <a class="page-link" href="#" onclick="loadReports(1, currentReportsFilters)">1</a>
        </li>`;
        if (startPage > 2) {
            html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        if (i === pagination.page) {
            html += `<li class="page-item active">
                <span class="page-link">${i}</span>
            </li>`;
        } else {
            html += `<li class="page-item">
                <a class="page-link" href="#" onclick="loadReports(${i}, currentReportsFilters)">${i}</a>
            </li>`;
        }
    }
    
    if (endPage < pagination.pages) {
        if (endPage < pagination.pages - 1) {
            html += `<li class="page-item disabled"><span class="page-link">...</span></li>`;
        }
        html += `<li class="page-item">
            <a class="page-link" href="#" onclick="loadReports(${pagination.pages}, currentReportsFilters)">${pagination.pages}</a>
        </li>`;
    }
    
    // 下一页
    if (pagination.has_next) {
        html += `<li class="page-item">
            <a class="page-link" href="#" onclick="loadReports(${pagination.page + 1}, currentReportsFilters)">
                <i class="bi bi-chevron-right"></i>
            </a>
        </li>`;
    } else {
        html += `<li class="page-item disabled">
            <span class="page-link"><i class="bi bi-chevron-right"></i></span>
        </li>`;
    }
    
    container.innerHTML = html;
    
    // 更新分页信息
    const info = document.getElementById('reportsPageInfo');
    if (info) {
        const start = (pagination.page - 1) * pagination.per_page + 1;
        const end = Math.min(pagination.page * pagination.per_page, pagination.total);
        info.textContent = `显示 ${start}-${end} 条，共 ${pagination.total} 条记录`;
    }
}

// 应用日志筛选
function applyLogsFilter() {
    const filters = {
        server_id: document.getElementById('logServerFilter')?.value || '',
        status: document.getElementById('logStatusFilter')?.value || '',
        start_date: document.getElementById('logStartDate')?.value || '',
        end_date: document.getElementById('logEndDate')?.value || ''
    };
    
    // 移除空值
    Object.keys(filters).forEach(key => {
        if (!filters[key]) {
            delete filters[key];
        }
    });
    
    loadLogs(1, filters);
}

// 清除日志筛选
function clearLogsFilter() {
    // 清除筛选控件的值
    const serverFilter = document.getElementById('logServerFilter');
    const statusFilter = document.getElementById('logStatusFilter');
    const startDate = document.getElementById('logStartDate');
    const endDate = document.getElementById('logEndDate');
    
    if (serverFilter) serverFilter.value = '';
    if (statusFilter) statusFilter.value = '';
    if (startDate) startDate.value = '';
    if (endDate) endDate.value = '';
    
    // 重新加载数据
    loadLogs(1, {});
}

// 应用报告筛选
function applyReportsFilter() {
    const filters = {
        type: document.getElementById('reportTypeFilter')?.value || '',
        start_date: document.getElementById('reportStartDate')?.value || '',
        end_date: document.getElementById('reportEndDate')?.value || ''
    };
    
    // 移除空值
    Object.keys(filters).forEach(key => {
        if (!filters[key]) {
            delete filters[key];
        }
    });
    
    loadReports(1, filters);
}

// 清除报告筛选
function clearReportsFilter() {
    // 清除筛选控件的值
    const typeFilter = document.getElementById('reportTypeFilter');
    const startDate = document.getElementById('reportStartDate');
    const endDate = document.getElementById('reportEndDate');
    
    if (typeFilter) typeFilter.value = '';
    if (startDate) startDate.value = '';
    if (endDate) endDate.value = '';
    
    // 重新加载数据
    loadReports(1, {});
}

// ===== 批量删除相关功能 =====

// 日志批量选择相关函数

// 切换所有日志选择
function toggleAllLogsSelection() {
    const selectAll = document.getElementById('logsSelectAll');
    const checkboxes = document.querySelectorAll('.log-checkbox');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll.checked;
    });
    
    updateLogsSelection();
}

// 更新日志选择状态
function updateLogsSelection() {
    const checkboxes = document.querySelectorAll('.log-checkbox');
    const checkedBoxes = document.querySelectorAll('.log-checkbox:checked');
    const selectAll = document.getElementById('logsSelectAll');
    const toolbar = document.getElementById('logsBulkToolbar');
    const selectedCount = document.getElementById('logsSelectedCount');
    
    // 更新全选复选框状态
    if (checkedBoxes.length === 0) {
        selectAll.indeterminate = false;
        selectAll.checked = false;
    } else if (checkedBoxes.length === checkboxes.length) {
        selectAll.indeterminate = false;
        selectAll.checked = true;
    } else {
        selectAll.indeterminate = true;
        selectAll.checked = false;
    }
    
    // 显示/隐藏工具栏
    if (checkedBoxes.length > 0) {
        toolbar.style.display = 'flex';
        selectedCount.textContent = checkedBoxes.length;
    } else {
        toolbar.style.display = 'none';
    }
}

// 清除日志选择
function clearLogsSelection() {
    const checkboxes = document.querySelectorAll('.log-checkbox');
    const selectAll = document.getElementById('logsSelectAll');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    selectAll.checked = false;
    selectAll.indeterminate = false;
    
    updateLogsSelection();
}

// 批量删除日志
function bulkDeleteLogs() {
    const checkedBoxes = document.querySelectorAll('.log-checkbox:checked');
    
    if (checkedBoxes.length === 0) {
        showAlert('请选择要删除的日志', 'warning');
        return;
    }
    
    const logIds = Array.from(checkedBoxes).map(checkbox => parseInt(checkbox.value));
    
    if (confirm(`确定要删除选中的 ${logIds.length} 条日志吗？此操作不可撤销。`)) {
        const deleteBtn = document.getElementById('logsBulkDeleteBtn');
        const originalText = deleteBtn.innerHTML;
        
        deleteBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 删除中...';
        deleteBtn.disabled = true;
        
        safeFetch('/api/logs/bulk-delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                log_ids: logIds
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                loadLogs(currentLogsPage, currentLogsFilters); // 重新加载当前页
            } else {
                showAlert('批量删除失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('批量删除日志失败:', error);
            showAlert('批量删除日志失败', 'danger');
        })
        .finally(() => {
            deleteBtn.innerHTML = originalText;
            deleteBtn.disabled = false;
        });
    }
}

// ========== 服务配置相关函数 ==========

// 加载服务配置
function loadServices() {
    showServicesLoading(true);
    
    safeFetch('/api/services/servers')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                servicesData = data.data;
                renderServices();
                bindServicesEvents();
                loadServicesSettings();
            } else {
                showAlert('加载服务配置失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            if (error.message !== 'Unauthorized') {
                console.error('加载服务配置失败:', error);
                showAlert('加载服务配置失败', 'danger');
            }
        })
        .finally(() => {
            showServicesLoading(false);
        });
}

// 绑定服务配置相关事件
function bindServicesEvents() {
    // 一键展开/关闭
    const expandAllBtn = document.getElementById('expandAllServicesBtn');
    const collapseAllBtn = document.getElementById('collapseAllServicesBtn');
    
    if (expandAllBtn) {
        expandAllBtn.onclick = function() {
            servicesData.forEach(server => {
                expandedServers.add(server.id);
            });
            renderServices();
        };
    }
    
    if (collapseAllBtn) {
        collapseAllBtn.onclick = function() {
            expandedServers.clear();
            renderServices();
        };
    }
    
    // 刷新和监控按钮
    const refreshBtn = document.getElementById('refreshServicesBtn');
    const monitorAllBtn = document.getElementById('monitorAllServicesBtn');
    
    if (refreshBtn) {
        refreshBtn.onclick = loadServices;
    }
    
    if (monitorAllBtn) {
        monitorAllBtn.onclick = monitorAllServices;
    }
}

// 更新服务总览
function updateServicesOverview(servicesData) {
    const container = document.getElementById('servicesOverview');
    
    if (!container) {
        // 如果容器不存在，在服务器状态下方创建
        const serverStatusContainer = document.getElementById('serverStatusList').parentElement;
        const servicesOverviewHtml = `
            <div class="card dashboard-card mt-3" id="servicesOverview">
                <div class="card-header">
                    <h5 class="mb-0">
                        <i class="bi bi-gear me-2"></i>服务总览
                    </h5>
                </div>
                <div class="card-body" id="servicesOverviewContent">
                    <!-- 服务总览内容将由JavaScript填充 -->
                </div>
            </div>
        `;
        serverStatusContainer.insertAdjacentHTML('afterend', servicesOverviewHtml);
    }
    
    const content = document.getElementById('servicesOverviewContent');
    const monitoringStatus = servicesData.is_monitoring ? '运行中' : '已停止';
    const monitoringClass = servicesData.is_monitoring ? 'text-success' : 'text-secondary';
    
    const html = `
        <div class="row">
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 mb-0 text-primary">${servicesData.total_services}</div>
                    <small class="text-muted">总服务数</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 mb-0 text-info">${servicesData.monitoring_services}</div>
                    <small class="text-muted">监控服务</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 mb-0 text-success">${servicesData.normal_services}</div>
                    <small class="text-muted">正常服务</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 mb-0 text-danger">${servicesData.error_services}</div>
                    <small class="text-muted">异常服务</small>
                </div>
            </div>
        </div>
        <hr>
        <div class="row align-items-center">
            <div class="col-md-6">
                <span class="${monitoringClass}">
                    <i class="bi bi-circle-fill"></i> 监控状态: ${monitoringStatus}
                </span>
            </div>
            <div class="col-md-6 text-end">
                <small class="text-muted">监控间隔: ${servicesData.monitor_interval}分钟</small>
                <button class="btn btn-sm btn-outline-primary ms-2" onclick="showSection('services')">
                    <i class="bi bi-gear"></i> 管理服务
                </button>
            </div>
        </div>
    `;
    
    content.innerHTML = html;
}

// 渲染服务列表
function renderServices() {
    const container = document.getElementById('servicesContainer');
    
    if (!servicesData || servicesData.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info text-center">
                <i class="bi bi-info-circle me-2"></i>
                暂无服务器配置，请先在<a href="#" onclick="showSection('servers')" class="alert-link">服务器管理</a>中添加服务器
            </div>
        `;
        return;
    }
    
    let html = '';
    
    servicesData.forEach(server => {
        const isExpanded = expandedServers.has(server.id);
        const expandIcon = isExpanded ? 'bi-chevron-down' : 'bi-chevron-right';
        
        html += `
            <div class="card dashboard-card mb-3">
                <div class="card-header" style="cursor: pointer;" onclick="toggleServerExpansion(${server.id})">
                    <div class="row align-items-center">
                        <div class="col-md-6">
                            <h5 class="mb-1">
                                <i class="bi bi-server me-2"></i>${server.name}
                            </h5>
                            <small class="text-muted">${server.host}:${server.port}</small>
                        </div>
                        <div class="col-md-5">
                            <span class="badge bg-primary me-2">总：${server.total_services}</span>
                            <span class="badge bg-info me-2">监控：${server.monitoring_services}</span>
                            <span class="badge bg-success me-2">正常：${server.normal_services}</span>
                            <span class="badge bg-danger me-2">异常：${server.error_services}</span>
                        </div>
                        <div class="col-md-1 text-end">
                            <button class="btn btn-sm btn-outline-primary me-2" onclick="event.stopPropagation(); addService(${server.id})">
                                <i class="bi bi-plus"></i>
                            </button>
                            <i class="bi ${expandIcon}"></i>
                        </div>
                    </div>
                </div>
                
                ${isExpanded ? renderServicesList(server) : ''}
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// 渲染服务列表
function renderServicesList(server) {
    if (!server.services || server.services.length === 0) {
        return `
            <div class="card-body">
                <div class="text-center text-muted">
                    <em>暂无服务配置</em>
                </div>
            </div>
        `;
    }
    
    let html = '<div class="card-body">';
    
    server.services.forEach(service => {
        const statusClass = getServiceStatusClass(service.latest_status, service.is_monitoring);
        const statusText = getServiceStatusText(service.latest_status, service.is_monitoring);
        
        // 格式化时间
        const lastMonitorTime = service.last_monitor_time ? 
            new Date(service.last_monitor_time).toLocaleString('zh-CN') : '未监控';
        const firstErrorTime = service.first_error_time ? 
            new Date(service.first_error_time).toLocaleString('zh-CN') : null;
        
        html += `
            <div class="d-flex justify-content-between align-items-center border-bottom py-2">
                <div>
                    <div class="d-flex align-items-center mb-1">
                        <strong>${service.service_name}</strong>
                        <span class="badge ${statusClass} ms-2">${statusText}</span>
                    </div>
                    <div class="small text-muted">
                        进程: ${service.process_name}
                        ${service.latest_process_count > 0 ? ` | 进程数: ${service.latest_process_count}` : ''}
                    </div>
                    <div class="small text-muted">
                        最新监控: ${lastMonitorTime}
                        ${firstErrorTime ? `<br><span class="text-danger">首次异常: ${firstErrorTime}</span>` : ''}
                    </div>
                </div>
                <div>
                    <button class="btn btn-sm btn-outline-primary me-2" onclick="editService(${service.id})">
                        <i class="bi bi-pencil"></i> 编辑
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteService(${service.id}, '${service.service_name}')">
                        <i class="bi bi-trash"></i> 删除
                    </button>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    return html;
}

// 切换服务器展开/收起
function toggleServerExpansion(serverId) {
    if (expandedServers.has(serverId)) {
        expandedServers.delete(serverId);
    } else {
        expandedServers.add(serverId);
    }
    renderServices();
}

// 获取服务状态样式类
function getServiceStatusClass(status, isMonitoring) {
    if (!isMonitoring) return 'bg-secondary';
    
    switch(status) {
        case 'running': return 'bg-success';
        case 'stopped': return 'bg-danger';
        case 'error': return 'bg-danger';
        default: return 'bg-secondary';
    }
}

// 获取服务状态文本
function getServiceStatusText(status, isMonitoring) {
    if (!isMonitoring) return '关闭';
    
    switch(status) {
        case 'running': return '正常';
        case 'stopped': return '异常';
        case 'error': return '异常';
        default: return '未知';
    }
}

// 添加服务
function addService(serverId) {
    showServiceModal('add', serverId);
}

// 编辑服务
function editService(serviceId) {
    showServiceModal('edit', null, serviceId);
}

// 显示服务配置模态框
function showServiceModal(mode, serverId = null, serviceId = null) {
    const modalHtml = `
        <div class="modal fade" id="serviceModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${mode === 'add' ? '添加服务' : '编辑服务'}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="serviceForm">
                            <input type="hidden" id="serviceId" value="${serviceId || ''}">
                            <input type="hidden" id="serverId" value="${serverId || ''}">
                            
                            <div class="mb-3">
                                <label for="serviceName" class="form-label">服务名称 <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="serviceName" required>
                            </div>
                            
                            <div class="mb-3">
                                <label for="processName" class="form-label">进程名称 <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="processName" required>
                                <div class="form-text">程序将通过此进程名监控服务状态</div>
                            </div>
                            
                            <div class="mb-3">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="isMonitoring" checked>
                                    <label class="form-check-label" for="isMonitoring">
                                        启用监控
                                    </label>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="serviceDescription" class="form-label">服务描述</label>
                                <textarea class="form-control" id="serviceDescription" rows="3"></textarea>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" onclick="saveService()">保存</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 清除旧的模态框
    const oldModal = document.getElementById('serviceModal');
    if (oldModal) {
        oldModal.remove();
    }
    
    // 添加新的模态框
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // 如果是编辑模式，加载服务数据
    if (mode === 'edit' && serviceId) {
        loadServiceData(serviceId);
    }
    
    // 显示模态框
    currentServiceModal = new bootstrap.Modal(document.getElementById('serviceModal'));
    currentServiceModal.show();
}

// 加载服务数据（编辑模式）
function loadServiceData(serviceId) {
    safeFetch(`/api/services/${serviceId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const service = data.data;
                document.getElementById('serviceId').value = service.id;
                document.getElementById('serverId').value = service.server_id;
                document.getElementById('serviceName').value = service.service_name;
                document.getElementById('processName').value = service.process_name;
                document.getElementById('isMonitoring').checked = service.is_monitoring;
                document.getElementById('serviceDescription').value = service.description || '';
            } else {
                showAlert('获取服务信息失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('获取服务信息失败:', error);
            showAlert('获取服务信息失败', 'danger');
        });
}

// 保存服务
function saveService() {
    const serviceId = document.getElementById('serviceId').value;
    const serverId = document.getElementById('serverId').value;
    const serviceName = document.getElementById('serviceName').value.trim();
    const processName = document.getElementById('processName').value.trim();
    const isMonitoring = document.getElementById('isMonitoring').checked;
    const description = document.getElementById('serviceDescription').value.trim();
    
    if (!serviceName || !processName) {
        showAlert('请填写必填字段', 'warning');
        return;
    }
    
    const data = {
        server_id: parseInt(serverId),
        service_name: serviceName,
        process_name: processName,
        is_monitoring: isMonitoring,
        description: description
    };
    
    const url = serviceId ? `/api/services/${serviceId}` : '/api/services';
    const method = serviceId ? 'PUT' : 'POST';
    
    safeFetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(result => {
        if (result.success) {
            showAlert(result.message, 'success');
            if (currentServiceModal) {
                currentServiceModal.hide();
            }
            loadServices();
        } else {
            showAlert(result.message, 'danger');
        }
    })
    .catch(error => {
        console.error('保存服务失败:', error);
        showAlert('保存服务失败', 'danger');
    });
}

// 删除服务
function deleteService(serviceId, serviceName) {
    if (!confirm(`确定要删除服务 "${serviceName}" 吗？`)) {
        return;
    }
    
    safeFetch(`/api/services/${serviceId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(data.message, 'success');
            loadServices();
        } else {
            showAlert(data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('删除服务失败:', error);
        showAlert('删除服务失败', 'danger');
    });
}

// 监控所有服务
function monitorAllServices() {
    if (!confirm('确定要立即监控所有服务吗？这可能需要一些时间。')) {
        return;
    }
    
    const btn = document.getElementById('monitorAllServicesBtn');
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 监控中...';
    btn.disabled = true;
    
    safeFetch('/api/services/monitor/all', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('服务监控完成', 'success');
            loadServices();
        } else {
            showAlert(data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('监控服务失败:', error);
        showAlert('监控服务失败', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

// 加载服务设置
function loadServicesSettings() {
    safeFetch('/api/services/settings')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const interval = data.data.monitor_interval || 10;
                const intervalInput = document.getElementById('monitorInterval');
                if (intervalInput) {
                    intervalInput.value = interval;
                }
            }
        })
        .catch(error => {
            console.error('加载全局设置失败:', error);
        });
}

// 显示服务加载状态
function showServicesLoading(show) {
    const loadingIndicator = document.getElementById('servicesLoadingIndicator');
    const container = document.getElementById('servicesContainer');
    
    if (loadingIndicator) {
        loadingIndicator.style.display = show ? 'block' : 'none';
    }
    if (container) {
        container.style.display = show ? 'none' : 'block';
    }
}

// 保存服务设置
function saveServicesSettings() {
    const monitorInterval = document.getElementById('monitorInterval').value;
    
    if (!monitorInterval || monitorInterval < 1 || monitorInterval > 1440) {
        showAlert('监控间隔必须在1-1440分钟之间', 'warning');
        return;
    }
    
    safeFetch('/api/services/settings', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            monitor_interval: parseInt(monitorInterval)
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(data.message, 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('serviceSettingsModal'));
            if (modal) {
                modal.hide();
            }
        } else {
            showAlert(data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('保存设置失败:', error);
        showAlert('保存设置失败', 'danger');
    });
}

// ========== 通知管理相关函数 ==========

// 全局变量
 let notificationsData = [];

// 加载通知通道列表
function loadNotifications() {
    safeFetch('/api/notifications')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                notificationsData = data.data;
                renderNotificationsTable(notificationsData);
            } else {
                showAlert('加载通知通道失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('加载通知通道失败:', error);
            showAlert('加载通知通道失败', 'danger');
        });
}

// 渲染通知通道表格
function renderNotificationsTable(notifications) {
    const tbody = document.getElementById('notificationsTableBody');
    
    if (!notifications || notifications.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" class="text-center text-muted">
                    <i class="bi bi-inbox"></i>
                    暂无通知通道
                </td>
            </tr>
        `;
        return;
    }
    
    let html = '';
    notifications.forEach(channel => {
        const statusClass = channel.is_enabled ? 'success' : 'secondary';
        const statusText = channel.is_enabled ? '已启用' : '已禁用';
        
        html += `
            <tr>
                <td>${channel.name}</td>
                <td>
                    <span class="text-muted">${channel.webhook_url.length > 50 ? 
                        channel.webhook_url.substring(0, 50) + '...' : 
                        channel.webhook_url}</span>
                </td>
                <td>
                    <span class="badge bg-info">${channel.method}</span>
                </td>
                <td>
                    <span class="badge bg-${statusClass}">${statusText}</span>
                </td>
                <td>${channel.timeout}s</td>
                <td>${new Date(channel.created_at).toLocaleString('zh-CN')}</td>
                <td>
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="showEditNotificationModal(${channel.id})" title="编辑">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-success me-1" onclick="testNotificationChannel(${channel.id})" title="测试">
                        <i class="bi bi-play-circle"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteNotificationChannel(${channel.id})" title="删除">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// 显示添加通知通道模态框
function showAddNotificationModal() {
    const modalHtml = `
        <div class="modal fade" id="notificationModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-plus-circle"></i>
                            添加通知通道
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="notificationForm">
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="notificationName" class="form-label">通道名称 *</label>
                                        <input type="text" class="form-control" id="notificationName" required>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="notificationMethod" class="form-label">请求方式</label>
                                        <select class="form-select" id="notificationMethod">
                                            <option value="POST">POST</option>
                                            <option value="GET">GET</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="notificationWebhookUrl" class="form-label">Webhook URL *</label>
                                <input type="url" class="form-control" id="notificationWebhookUrl" required 
                                       placeholder="https://example.com/webhook">
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="notificationTimeout" class="form-label">超时时间(秒)</label>
                                        <input type="number" class="form-control" id="notificationTimeout" value="30" min="5" max="300">
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <div class="form-check form-switch mt-4">
                                            <input class="form-check-input" type="checkbox" id="notificationEnabled" checked>
                                            <label class="form-check-label" for="notificationEnabled">启用通道</label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="notificationContentTemplate" class="form-label">内容模板</label>
                                <textarea class="form-control" id="notificationContentTemplate" rows="3" 
                                          placeholder="使用 #context# 作为占位符，例如：主机巡检报告：#context#">主机巡检报告：#context#</textarea>
                                <div class="form-text">使用 #context# 作为占位符，将会被替换为实际的巡检结果</div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="notificationRequestBody" class="form-label">请求体模板 (JSON格式)</label>
                                <textarea class="form-control" id="notificationRequestBody" rows="4" 
                                          placeholder='{
  "text": "#context#",
  "channel": "#general"
}'></textarea>
                                <div class="form-text">可选，用于自定义请求体格式，留空将使用默认格式</div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" onclick="saveNotificationChannel()">保存</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('modalContainer').innerHTML = modalHtml;
    const modal = new bootstrap.Modal(document.getElementById('notificationModal'));
    modal.show();
}

// 保存通知通道
function saveNotificationChannel() {
    const channelId = document.getElementById('notificationId')?.value;
    const isEdit = !!channelId;
    
    const data = {
        name: document.getElementById('notificationName').value.trim(),
        webhook_url: document.getElementById('notificationWebhookUrl').value.trim(),
        method: document.getElementById('notificationMethod').value,
        timeout: parseInt(document.getElementById('notificationTimeout').value),
        is_enabled: document.getElementById('notificationEnabled').checked,
        content_template: document.getElementById('notificationContentTemplate').value.trim(),
        request_body: document.getElementById('notificationRequestBody').value.trim()
    };
    
    // 验证必填字段
    if (!data.name || !data.webhook_url) {
        showAlert('请填写通道名称和Webhook URL', 'warning');
        return;
    }
    
    // 验证URL格式
    try {
        new URL(data.webhook_url);
    } catch (e) {
        showAlert('请输入正确的Webhook URL', 'warning');
        return;
    }
    
    // 验证JSON格式
    if (data.request_body) {
        try {
            JSON.parse(data.request_body);
        } catch (e) {
            showAlert('请求体模板格式不正确，请输入正确的JSON格式', 'warning');
            return;
        }
    }
    
    const url = isEdit ? `/api/notifications/${channelId}` : '/api/notifications';
    const method = isEdit ? 'PUT' : 'POST';
    
    safeFetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(data.message, 'success');
            const modal = bootstrap.Modal.getInstance(document.getElementById('notificationModal'));
            modal.hide();
            loadNotifications(); // 重新加载列表
        } else {
            showAlert('保存失败: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('保存通知通道失败:', error);
        showAlert('保存通知通道失败', 'danger');
    });
}

// 显示编辑通知通道模态框
function showEditNotificationModal(channelId) {
    const channel = notificationsData.find(c => c.id === channelId);
    if (!channel) {
        showAlert('找不到指定的通知通道', 'danger');
        return;
    }
    
    const modalHtml = `
        <div class="modal fade" id="notificationModal" tabindex="-1">
            <div class="modal-dialog modal-lg">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-pencil"></i>
                            编辑通知通道
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="notificationForm">
                            <input type="hidden" id="notificationId" value="${channel.id}">
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="notificationName" class="form-label">通道名称 *</label>
                                        <input type="text" class="form-control" id="notificationName" value="${channel.name}" required>
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="notificationMethod" class="form-label">请求方式</label>
                                        <select class="form-select" id="notificationMethod">
                                            <option value="POST" ${channel.method === 'POST' ? 'selected' : ''}>POST</option>
                                            <option value="GET" ${channel.method === 'GET' ? 'selected' : ''}>GET</option>
                                        </select>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="notificationWebhookUrl" class="form-label">Webhook URL *</label>
                                <input type="url" class="form-control" id="notificationWebhookUrl" value="${channel.webhook_url}" required>
                            </div>
                            
                            <div class="row">
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <label for="notificationTimeout" class="form-label">超时时间(秒)</label>
                                        <input type="number" class="form-control" id="notificationTimeout" value="${channel.timeout}" min="5" max="300">
                                    </div>
                                </div>
                                <div class="col-md-6">
                                    <div class="mb-3">
                                        <div class="form-check form-switch mt-4">
                                            <input class="form-check-input" type="checkbox" id="notificationEnabled" ${channel.is_enabled ? 'checked' : ''}>
                                            <label class="form-check-label" for="notificationEnabled">启用通道</label>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="notificationContentTemplate" class="form-label">内容模板</label>
                                <textarea class="form-control" id="notificationContentTemplate" rows="3">${channel.content_template || ''}</textarea>
                                <div class="form-text">使用 #context# 作为占位符，将会被替换为实际的巡检结果</div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="notificationRequestBody" class="form-label">请求体模板 (JSON格式)</label>
                                <textarea class="form-control" id="notificationRequestBody" rows="4">${channel.request_body || ''}</textarea>
                                <div class="form-text">可选，用于自定义请求体格式，留空将使用默认格式</div>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" onclick="saveNotificationChannel()">保存</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.getElementById('modalContainer').innerHTML = modalHtml;
    const modal = new bootstrap.Modal(document.getElementById('notificationModal'));
    modal.show();
}

// 测试通知通道
function testNotificationChannel(channelId) {
    const channel = notificationsData.find(c => c.id === channelId);
    if (!channel) {
        showAlert('找不到指定的通知通道', 'danger');
        return;
    }
    
    if (confirm(`确定要测试通知通道 "${channel.name}" 吗？`)) {
        safeFetch(`/api/notifications/${channelId}/test`, {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
            } else {
                showAlert('测试失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('测试通知通道失败:', error);
            showAlert('测试通知通道失败', 'danger');
        });
    }
}

// 删除通知通道
function deleteNotificationChannel(channelId) {
    const channel = notificationsData.find(c => c.id === channelId);
    if (!channel) {
        showAlert('找不到指定的通知通道', 'danger');
        return;
    }
    
    if (confirm(`确定要删除通知通道 "${channel.name}" 吗？此操作不可撤销。`)) {
        safeFetch(`/api/notifications/${channelId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                loadNotifications(); // 重新加载列表
            } else {
                showAlert('删除失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('删除通知通道失败:', error);
            showAlert('删除通知通道失败', 'danger');
        });
    }
}

// ========== 用户认证相关函数 ==========

// 获取当前用户信息
function getCurrentUser() {
    safeFetch('/api/auth/user')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.user) {
                document.getElementById('currentUsername').textContent = data.user.username;
            }
        })
        .catch(error => {
            // 静默失败，不显示错误
            console.error('获取用户信息失败:', error);
        });
}

// 登出功能
function logout() {
    if (confirm('确定要登出吗？')) {
        safeFetch('/api/auth/logout', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert('登出成功', 'success');
                setTimeout(() => {
                    window.location.href = '/login';
                }, 1000);
            } else {
                showAlert('登出失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('登出失败:', error);
            // 即使登出失败，也跳转到登录页
            window.location.href = '/login';
        });
    }
}

// 报告批量选择相关函数

// 切换所有报告选择
function toggleAllReportsSelection() {
    const selectAll = document.getElementById('reportsSelectAll');
    const checkboxes = document.querySelectorAll('.report-checkbox');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = selectAll.checked;
    });
    
    updateReportsSelection();
}

// 更新报告选择状态
function updateReportsSelection() {
    const checkboxes = document.querySelectorAll('.report-checkbox');
    const checkedBoxes = document.querySelectorAll('.report-checkbox:checked');
    const selectAll = document.getElementById('reportsSelectAll');
    const toolbar = document.getElementById('reportsBulkToolbar');
    const selectedCount = document.getElementById('reportsSelectedCount');
    
    // 更新全选复选框状态
    if (checkedBoxes.length === 0) {
        selectAll.indeterminate = false;
        selectAll.checked = false;
    } else if (checkedBoxes.length === checkboxes.length) {
        selectAll.indeterminate = false;
        selectAll.checked = true;
    } else {
        selectAll.indeterminate = true;
        selectAll.checked = false;
    }
    
    // 显示/隐藏工具栏
    if (checkedBoxes.length > 0) {
        toolbar.style.display = 'flex';
        selectedCount.textContent = checkedBoxes.length;
    } else {
        toolbar.style.display = 'none';
    }
}

// 清除报告选择
function clearReportsSelection() {
    const checkboxes = document.querySelectorAll('.report-checkbox');
    const selectAll = document.getElementById('reportsSelectAll');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    selectAll.checked = false;
    selectAll.indeterminate = false;
    
    updateReportsSelection();
}

// 批量删除报告
function bulkDeleteReports() {
    const checkedBoxes = document.querySelectorAll('.report-checkbox:checked');
    
    if (checkedBoxes.length === 0) {
        showAlert('请选择要删除的报告', 'warning');
        return;
    }
    
    const reportIds = Array.from(checkedBoxes).map(checkbox => parseInt(checkbox.value));
    
    if (confirm(`确定要删除选中的 ${reportIds.length} 个报告吗？此操作不可撤销。`)) {
        const deleteBtn = document.getElementById('reportsBulkDeleteBtn');
        const originalText = deleteBtn.innerHTML;
        
        deleteBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 删除中...';
        deleteBtn.disabled = true;
        
        safeFetch('/api/reports/bulk-delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                report_ids: reportIds
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                loadReports(currentReportsPage, currentReportsFilters); // 重新加载当前页
            } else {
                showAlert('批量删除失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('批量删除报告失败:', error);
            showAlert('批量删除报告失败', 'danger');
        })
        .finally(() => {
            deleteBtn.innerHTML = originalText;
            deleteBtn.disabled = false;
        });
    }
}