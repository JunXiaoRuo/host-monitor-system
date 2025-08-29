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
    loadThresholds(); // 初始化时加载阈值数据，确保监控日志详情弹窗能使用正确阈值
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
                    <div class="d-flex align-items-center">
                        <small class="me-2">${status.monitor_time ? new Date(status.monitor_time).toLocaleString('zh-CN') : '未监控'}</small>
                        <button class="btn btn-sm btn-outline-primary" onclick="monitorSingleServerFromDashboard('${serverId}', '${status.server_name || '服务器'}')"
                                title="监控该服务器">
                            <i class="bi bi-play-circle"></i>
                        </button>
                    </div>
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
            showAlert('监控执行成功，请刷新页面', 'success');
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

// 从仪表盘监控单个服务器
function monitorSingleServerFromDashboard(serverId, serverName) {
    if (!confirm(`确定要立即监控服务器 "${serverName}" 吗？`)) {
        return;
    }
    
    const btn = event.target.closest('button');
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i>';
    btn.disabled = true;
    
    safeFetch(`/api/monitor/server/${serverId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(`服务器 "${serverName}" 监控完成！`, 'success');
            // 刷新仪表盘数据
            setTimeout(refreshDashboard, 1000);
        } else {
            showAlert(`监控失败: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        if (error.message !== 'Unauthorized') {
            showAlert('监控失败', 'danger');
        }
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

// 从服务器管理表监控单个服务器
function monitorSingleServerFromTable(serverId, serverName) {
    if (!confirm(`确定要立即监控服务器 "${serverName}" 吗？`)) {
        return;
    }
    
    const btn = event.target.closest('button');
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i>';
    btn.disabled = true;
    
    safeFetch(`/api/monitor/server/${serverId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert(`服务器 "${serverName}" 监控完成！`, 'success');
            // 刷新服务器列表
            loadServers();
        } else {
            showAlert(`监控失败: ${data.message}`, 'danger');
        }
    })
    .catch(error => {
        if (error.message !== 'Unauthorized') {
            showAlert('监控失败', 'danger');
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
    // 使用包含服务统计的API
    safeFetch('/api/servers/with-services')
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
                <td colspan="10" class="text-center text-muted">
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
        
        // 服务数统计显示
        const totalServices = server.total_services || 0;
        const errorServices = server.error_services || 0;
        let serviceCountDisplay = `<span class="badge bg-info ms-1">总数:${totalServices}</span>`;
        if (errorServices > 0) {
            serviceCountDisplay += ` <span class="badge bg-danger ms-1">异常:${errorServices}</span>`;
        }
        
        html += `
            <tr>
                <td>
                    <input type="checkbox" class="server-checkbox" value="${server.id}" onchange="updateServersSelection()">
                </td>
                <td>${server.name}</td>
                <td>${server.host}</td>
                <td>${server.port}</td>
                <td>${server.username}</td>
                <td>
                    <span class="badge bg-${statusClass}">${statusText}</span>
                </td>
                <td>${serviceCountDisplay}</td>
                <td>${server.updated_at ? new Date(server.updated_at).toLocaleString('zh-CN') : '-'}</td>
                <td>
                    <button class="btn btn-sm btn-outline-success me-1" onclick="monitorSingleServerFromTable(${server.id}, '${server.name}')" title="监控该服务器">
                        <i class="bi bi-play-circle"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="testConnection(${server.id})" title="测试连接">
                        <i class="bi bi-wifi"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-info me-1" onclick="showServerServicesModal(${server.id}, '${server.name}')" title="服务管理">
                        <i class="bi bi-gear"></i>
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
    
    // 使用延迟重置选择状态，确保DOM元素渲染完成
    setTimeout(() => {
        clearServersSelection();
    }, 10);
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

// 显示服务器服务管理弹窗
function showServerServicesModal(serverId, serverName) {
    const modalHtml = `
        <div class="modal fade" id="serverServicesModal" tabindex="-1">
            <div class="modal-dialog modal-xl">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="bi bi-gear me-2"></i>服务管理 - ${serverName}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <!-- 提示信息 -->
                        <div class="alert alert-info d-flex align-items-center mb-3" role="alert">
                            <i class="bi bi-info-circle-fill me-3"></i>
                            <div>
                                <strong>提示：</strong>更多配置管理，请使用左侧菜单中的 
                                <strong class="text-primary">
                                    <i class="bi bi-gear"></i> 服务配置
                                </strong> 功能
                            </div>
                        </div>
                        
                        <!-- 控制按钮区域 -->
                        <div class="d-flex justify-content-between align-items-center mb-3">
                            <div>
                                <button type="button" class="btn btn-primary" onclick="addServerService(${serverId})">
                                    <i class="bi bi-plus-circle"></i> 添加服务
                                </button>
                                <button type="button" class="btn btn-outline-success ms-2" onclick="monitorServerServices(${serverId})">
                                    <i class="bi bi-play-circle"></i> 监控所有
                                </button>
                            </div>
                            <div>
                                <button type="button" class="btn btn-outline-primary" onclick="refreshServerServices(${serverId})">
                                    <i class="bi bi-arrow-clockwise"></i> 刷新
                                </button>
                            </div>
                        </div>
                        
                        <!-- 服务列表 -->
                        <div id="serverServicesList">
                            <div class="text-center py-4">
                                <div class="spinner-border text-primary" role="status">
                                    <span class="visually-hidden">加载中...</span>
                                </div>
                                <p class="mt-2">正在加载服务列表...</p>
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
    
    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('serverServicesModal'));
    modal.show();
    
    // 加载服务列表
    loadServerServices(serverId);
}

// 加载服务器的服务列表
function loadServerServices(serverId) {
    safeFetch(`/api/servers/${serverId}/services`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                renderServerServicesList(data.data || [], serverId);
            } else {
                showServerServicesError('加载服务列表失败: ' + data.message);
            }
        })
        .catch(error => {
            console.error('加载服务列表失败:', error);
            showServerServicesError('加载服务列表失败');
        });
}

// 渲染服务器服务列表
function renderServerServicesList(services, serverId) {
    const container = document.getElementById('serverServicesList');
    
    if (!services || services.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info text-center">
                <i class="bi bi-info-circle me-2"></i>
                该服务器暂无服务配置
            </div>
        `;
        return;
    }
    
    let html = `
        <div class="table-responsive">
            <table class="table table-hover">
                <thead>
                    <tr>
                        <th>服务名称</th>
                        <th>进程名称</th>
                        <th>状态</th>
                        <th>进程数</th>
                        <th>最后监控</th>
                        <th>操作</th>
                    </tr>
                </thead>
                <tbody>
    `;
    
    services.forEach(service => {
        const statusClass = getServiceStatusClass(service.latest_status, service.is_monitoring);
        const statusText = getServiceStatusText(service.latest_status, service.is_monitoring);
        const monitorTime = service.latest_monitor_time ? 
            new Date(service.latest_monitor_time).toLocaleString('zh-CN') : '未监控';
        
        html += `
            <tr>
                <td>
                    <strong>${service.service_name}</strong>
                    ${!service.is_monitoring ? '<span class="badge bg-secondary ms-2">未启用</span>' : ''}
                </td>
                <td><code>${service.process_name}</code></td>
                <td>
                    <span class="badge ${statusClass}">${statusText}</span>
                </td>
                <td>${service.latest_process_count || 0}</td>
                <td><small>${monitorTime}</small></td>
                <td>
                    <button class="btn btn-sm btn-outline-success me-1" onclick="monitorSingleServerService(${service.id})" title="监控">
                        <i class="bi bi-play-circle"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-primary me-1" onclick="editServerService(${service.id})" title="编辑">
                        <i class="bi bi-pencil"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="deleteServerService(${service.id}, '${service.service_name}')" title="删除">
                        <i class="bi bi-trash"></i>
                    </button>
                </td>
            </tr>
        `;
    });
    
    html += `
                </tbody>
            </table>
        </div>
    `;
    
    container.innerHTML = html;
}

// 获取服务状态样式类
function getServiceStatusClass(status, isMonitoring) {
    if (!isMonitoring) return 'bg-secondary';
    
    switch(status) {
        case 'running': return 'bg-success';
        case 'stopped': return 'bg-warning';
        case 'error': return 'bg-danger';
        default: return 'bg-info';
    }
}

// 获取服务状态文本
function getServiceStatusText(status, isMonitoring) {
    if (!isMonitoring) return '未启用';
    
    switch(status) {
        case 'running': return '正常';
        case 'stopped': return '停止';
        case 'error': return '错误';
        default: return '未知';
    }
}

// 显示服务列表错误
function showServerServicesError(message) {
    const container = document.getElementById('serverServicesList');
    container.innerHTML = `
        <div class="alert alert-danger text-center">
            <i class="bi bi-exclamation-triangle me-2"></i>
            ${message}
        </div>
    `;
}

// 添加服务器服务
function addServerService(serverId) {
    // 确保服务器ID有效
    if (!serverId) {
        serverId = getCurrentServerIdFromModal();
        if (!serverId) {
            showAlert('无法获取服务器ID', 'danger');
            return;
        }
    }
    showServiceModal(null, serverId);
}

// 编辑服务器服务
function editServerService(serviceId) {
    console.log('开始编辑服务:', serviceId, typeof serviceId);
    
    // 确保 serviceId 是数字
    const numericServiceId = parseInt(serviceId);
    if (isNaN(numericServiceId)) {
        showAlert('无效的服务ID', 'danger');
        console.error('无效的服务ID:', serviceId);
        return;
    }
    
    // 直接通过API获取服务详情
    safeFetch(`/api/services/${numericServiceId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const service = data.data;
                console.log('获取到服务数据:', service);
                
                // 直接传递服务数据给模态框
                showServiceModal(numericServiceId, service.server_id, service);
            } else {
                showAlert('获取服务信息失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('获取服务信息失败:', error);
            showAlert('获取服务信息失败', 'danger');
        });
}

// 删除服务器服务
function deleteServerService(serviceId, serviceName) {
    if (!confirm(`确定要删除服务 "${serviceName}" 吗？`)) {
        return;
    }
    
    safeFetch(`/api/services/${serviceId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('服务删除成功', 'success');
            // 重新加载当前服务器的服务列表
            const modalElement = document.getElementById('serverServicesModal');
            if (modalElement) {
                const serverId = getCurrentServerIdFromModal();
                if (serverId) {
                    loadServerServices(serverId);
                }
            }
        } else {
            showAlert('删除服务失败: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('删除服务失败:', error);
        showAlert('删除服务失败', 'danger');
    });
}

// 监控单个服务（在服务管理弹窗中）
function monitorSingleServerService(serviceId) {
    const btn = event.target.closest('button');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i>';
    btn.disabled = true;
    
    safeFetch(`/api/services/monitor/single/${serviceId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('服务监控完成', 'success');
            // 重新加载当前服务器的服务列表
            const serverId = getCurrentServerIdFromModal();
            if (serverId) {
                loadServerServices(serverId);
            }
        } else {
            showAlert(data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('监控单个服务失败:', error);
        showAlert('监控单个服务失败', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    });
}

// 监控服务器所有服务
function monitorServerServices(serverId) {
    const btn = event.target.closest('button');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 监控中...';
    btn.disabled = true;
    
    safeFetch(`/api/services/monitor/${serverId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('服务器服务监控完成', 'success');
            // 重新加载服务列表
            loadServerServices(serverId);
        } else {
            showAlert(data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('监控服务器服务失败:', error);
        showAlert('监控服务器服务失败', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalHtml;
        btn.disabled = false;
    });
}

// 刷新服务器服务列表
function refreshServerServices(serverId) {
    loadServerServices(serverId);
}

// 从模态框中获取当前服务器ID
function getCurrentServerIdFromModal() {
    // 从按钮中提取serverId，这里简化处理，实际中可以使用更好的方法
    const addBtn = document.querySelector('#serverServicesModal button[onclick*="addServerService"]');
    if (addBtn) {
        const match = addBtn.getAttribute('onclick').match(/addServerService\((\d+)\)/);
        if (match) {
            return parseInt(match[1]);
        }
    }
    return null;
}

// 显示服务模态框（新增/编辑）
function showServiceModal(serviceId = null, serverId = null, serviceData = null) {
    const isEdit = serviceId !== null;
    const title = isEdit ? '编辑服务' : '添加服务';
    
    // 如果没有传入serverId，尝试从当前弹窗获取
    if (!serverId && !isEdit) {
        serverId = getCurrentServerIdFromModal();
    }
    
    const modalHtml = `
        <div class="modal fade" id="serviceModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="serviceForm">
                            <input type="hidden" id="serviceId" value="${serviceId || ''}">
                            <input type="hidden" id="serviceServerId" value="${serverId || ''}">
                            
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
                        <button type="button" class="btn btn-primary" onclick="saveServiceFromModal()">保存</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 将新模态框添加到页面中
    const tempContainer = document.createElement('div');
    tempContainer.innerHTML = modalHtml;
    document.body.appendChild(tempContainer.firstElementChild);
    
    // 如果是编辑模式，填充数据
    if (isEdit) {
        if (serviceData) {
            console.log('直接填充服务数据:', serviceData);
            // 如果已有服务数据，延迟一点填充确保 DOM 元素完全创建
            setTimeout(() => {
                fillServiceFormData(serviceData);
            }, 200); // 增加延迟时间
        } else {
            console.log('通过API加载服务数据');
            // 否则通过API加载
            setTimeout(() => {
                loadServiceDataForEdit(serviceId);
            }, 200); // 增加延迟时间
        }
    }
    
    const modal = new bootstrap.Modal(document.getElementById('serviceModal'));
    modal.show();
    
    // 模态框关闭时清理DOM
    modal._element.addEventListener('hidden.bs.modal', function () {
        modal._element.remove();
    });
}

// 填充服务表单数据
function fillServiceFormData(service) {
    console.log('填充服务表单数据:', service);
    
    // 尝试多次查找元素，确保 DOM 元素存在
    const tryFillData = (attempts = 0) => {
        const serviceIdEl = document.getElementById('serviceId');
        const serviceNameEl = document.getElementById('serviceName');
        const processNameEl = document.getElementById('processName');
        const isMonitoringEl = document.getElementById('isMonitoring');
        const serviceDescriptionEl = document.getElementById('serviceDescription');
        const serviceServerIdEl = document.getElementById('serviceServerId');
        
        // 检查关键元素是否存在
        if (!serviceNameEl || !processNameEl) {
            if (attempts < 5) {
                console.log(`第 ${attempts + 1} 次尝试填充数据，元素尚未存在，等待 50ms...`);
                setTimeout(() => tryFillData(attempts + 1), 50);
                return;
            } else {
                console.error('多次尝试后仍无法找到必要的表单元素');
                return;
            }
        }
        
        console.log('开始填充数据，元素已存在');
        
        if (serviceIdEl) {
            serviceIdEl.value = service.id || '';
            console.log('填充服务ID:', service.id);
        } else {
            console.warn('服务ID元素不存在');
        }
        
        if (serviceNameEl) {
            serviceNameEl.value = service.service_name || '';
            console.log('填充服务名称:', service.service_name);
        }
        
        if (processNameEl) {
            processNameEl.value = service.process_name || '';
            console.log('填充进程名称:', service.process_name);
        }
        
        if (isMonitoringEl) {
            isMonitoringEl.checked = service.is_monitoring !== false;
            console.log('填充监控状态:', service.is_monitoring);
        }
        
        if (serviceDescriptionEl) {
            serviceDescriptionEl.value = service.description || '';
            console.log('填充描述:', service.description);
        }
        
        if (serviceServerIdEl) {
            serviceServerIdEl.value = service.server_id || '';
            console.log('填充服务器ID:', service.server_id);
        } else {
            console.warn('服务器ID元素不存在');
        }
        
        console.log('数据填充完成');
    };
    
    tryFillData();
}

// 加载服务数据用于编辑
function loadServiceDataForEdit(serviceId) {
    safeFetch(`/api/services/${serviceId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const service = data.data;
                fillServiceFormData(service);
            } else {
                showAlert('加载服务数据失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('加载服务数据失败:', error);
            showAlert('加载服务数据失败', 'danger');
        });
}

// 从模态框保存服务
function saveServiceFromModal() {
    const serviceId = document.getElementById('serviceId').value;
    const serverId = document.getElementById('serviceServerId').value;
    const serviceName = document.getElementById('serviceName').value.trim();
    const processName = document.getElementById('processName').value.trim();
    const isMonitoring = document.getElementById('isMonitoring').checked;
    const description = document.getElementById('serviceDescription').value.trim();
    
    console.log('保存服务数据:', {
        serviceId: serviceId,
        serverId: serverId,
        serviceName: serviceName,
        processName: processName,
        isMonitoring: isMonitoring,
        description: description
    });
    
    if (!serviceName || !processName) {
        showAlert('请填写必填字段', 'warning');
        return;
    }
    
    if (!serverId) {
        showAlert('服务器ID不能为空', 'warning');
        return;
    }
    
    const data = {
        server_id: parseInt(serverId),
        service_name: serviceName,
        process_name: processName,
        is_monitoring: isMonitoring,
        description: description
    };
    
    // 确保 serviceId 是数字或空字符串
    const numericServiceId = serviceId && serviceId.toString().trim() !== '' ? parseInt(serviceId) : null;
    const url = numericServiceId ? `/api/services/${numericServiceId}` : '/api/services';
    const method = numericServiceId ? 'PUT' : 'POST';
    
    console.log('请求信息:', {
        url: url,
        method: method,
        serviceId: numericServiceId,
        data: data
    });
    
    // 禁用保存按钮，防止重复提交
    const saveBtn = document.querySelector('#serviceModal .btn-primary');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 保存中...';
    }
    
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
            
            // 关闭模态框
            const serviceModal = bootstrap.Modal.getInstance(document.getElementById('serviceModal'));
            if (serviceModal) {
                serviceModal.hide();
            }
            
            // 延迟刷新，确保模态框完全关闭后再刷新
            setTimeout(() => {
                // 检查是否在服务器服务管理弹窗中
                const serverServicesModal = document.getElementById('serverServicesModal');
                if (serverServicesModal && serverServicesModal.style.display !== 'none') {
                    const currentServerId = getCurrentServerIdFromModal();
                    if (currentServerId) {
                        loadServerServices(currentServerId);
                    }
                }
                
                // 检查是否在服务配置页面
                if (currentSection === 'services') {
                    loadServices();
                }
                
                // 检查是否在服务器管理页面
                if (currentSection === 'servers') {
                    loadServers();
                }
            }, 300);
        } else {
            showAlert(result.message, 'danger');
        }
    })
    .catch(error => {
        console.error('保存服务失败:', error);
        showAlert('保存服务失败', 'danger');
    })
    .finally(() => {
        // 恢复保存按钮
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.innerHTML = '保存';
        }
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
                
                // 只有在阈值设置页面时才更新DOM元素
                const cpuThresholdElement = document.getElementById('cpuThreshold');
                const memoryThresholdElement = document.getElementById('memoryThreshold');
                const diskThresholdElement = document.getElementById('diskThreshold');
                
                if (cpuThresholdElement) {
                    cpuThresholdElement.value = data.data.cpu_threshold;
                }
                if (memoryThresholdElement) {
                    memoryThresholdElement.value = data.data.memory_threshold;
                }
                if (diskThresholdElement) {
                    diskThresholdElement.value = data.data.disk_threshold;
                }
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
    
    // 使用延迟重置选择状态，确保DOM元素渲染完成
    setTimeout(() => {
        clearReportsSelection();
    }, 10);
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
                <td colspan="10" class="text-center text-muted">
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
                <td><code>${log.server_ip || 'N/A'}</code></td>
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
    
    // 使用延迟重置选择状态，确保DOM元素渲染完成
    setTimeout(() => {
        clearLogsSelection();
    }, 10);
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
                        <tr ${(() => {
                            const diskThreshold = thresholdsData?.disk_threshold || 80;
                            const isOverThreshold = disk.use_percent > diskThreshold;
                            return isOverThreshold ? 'class="table-warning"' : '';
                        })()}>
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
                                            <div class="col-4"><strong>服务器IP:</strong></div>
                                            <div class="col-8"><code>${logData.server_ip || 'N/A'}</code></div>
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
                                                    <span class="${(() => {
                                                        const cpuThreshold = thresholdsData?.cpu_threshold || 80;
                                                        const isOverThreshold = logData.cpu_usage > cpuThreshold;
                                                        return isOverThreshold ? 'text-danger' : '';
                                                    })()}">
                                                        ${logData.cpu_usage.toFixed(1)}%
                                                    </span>
                                                ` : 'N/A'}
                                            </div>
                                        </div>
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>内存使用率:</strong></div>
                                            <div class="col-8">
                                                ${logData.memory_usage ? `
                                                    <span class="${(() => {
                                                        const memoryThreshold = thresholdsData?.memory_threshold || 80;
                                                        const isOverThreshold = logData.memory_usage > memoryThreshold;
                                                        return isOverThreshold ? 'text-danger' : '';
                                                    })()}">
                                                        ${logData.memory_usage.toFixed(1)}%
                                                    </span>
                                                ` : 'N/A'}
                                            </div>
                                        </div>
                                        ${logData.memory_info ? `
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>总内存:</strong></div>
                                            <div class="col-8">
                                                ${logData.memory_info.total_mb ? 
                                                    `${logData.memory_info.total_mb}MB (${logData.memory_info.total_gb}GB)` : 
                                                    'N/A'
                                                }
                                            </div>
                                        </div>
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>使用内存:</strong></div>
                                            <div class="col-8">
                                                ${logData.memory_info.used_mb ? 
                                                    `${logData.memory_info.used_mb}MB (${logData.memory_info.used_gb}GB)` : 
                                                    'N/A'
                                                }
                                            </div>
                                        </div>
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>空闲内存:</strong></div>
                                            <div class="col-8">
                                                ${logData.memory_info.free_mb ? 
                                                    `${logData.memory_info.free_mb}MB (${logData.memory_info.free_gb}GB)` : 
                                                    'N/A'
                                                }
                                            </div>
                                        </div>
                                        <div class="row mb-2">
                                            <div class="col-4"><strong>可用内存:</strong></div>
                                            <div class="col-8">
                                                ${logData.memory_info.available_mb ? 
                                                    `${logData.memory_info.available_mb}MB (${logData.memory_info.available_gb}GB)` : 
                                                    'N/A'
                                                }
                                            </div>
                                        </div>
                                        ` : ''}
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

// 刷新报告
function refreshReports() {
    loadReports(currentReportsPage, currentReportsFilters);
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
    
    // 延迟一点获取状态，确保复选框状态已更新
    setTimeout(() => {
        const isChecked = selectAll.checked;
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
        });
        
        // 立即更新选择状态
        updateLogsSelection();
    }, 0);
}

// 更新日志选择状态
function updateLogsSelection() {
    const checkboxes = document.querySelectorAll('.log-checkbox');
    const checkedBoxes = document.querySelectorAll('.log-checkbox:checked');
    const selectAll = document.getElementById('logsSelectAll');
    const toolbar = document.getElementById('logsBulkToolbar');
    const selectedCount = document.getElementById('logsSelectedCount');
    
    // 确保元素存在
    if (!selectAll || !toolbar || !selectedCount) {
        return;
    }
    
    const totalCount = checkboxes.length;
    const checkedCount = checkedBoxes.length;
    
    // 更新全选复选框状态
    if (checkedCount === 0) {
        selectAll.indeterminate = false;
        selectAll.checked = false;
    } else if (checkedCount === totalCount) {
        selectAll.indeterminate = false;
        selectAll.checked = true;
    } else {
        selectAll.indeterminate = true;
        selectAll.checked = false;
    }
    
    // 显示/隐藏工具栏和更新计数
    if (checkedCount > 0) {
        toolbar.style.display = 'flex';
        selectedCount.textContent = checkedCount;
    } else {
        toolbar.style.display = 'none';
        selectedCount.textContent = '0';
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
    
    // 立即更新选择状态和计数
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

// ========== 服务器批量选择相关函数 ==========

// 切换所有服务器选择
function toggleAllServersSelection() {
    const selectAll = document.getElementById('serversSelectAll');
    const checkboxes = document.querySelectorAll('.server-checkbox');
    
    // 延迟一点获取状态，确保复选框状态已更新
    setTimeout(() => {
        const isChecked = selectAll.checked;
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
        });
        
        // 立即更新选择状态
        updateServersSelection();
    }, 0);
}

// 更新服务器选择状态
function updateServersSelection() {
    const checkboxes = document.querySelectorAll('.server-checkbox');
    const checkedBoxes = document.querySelectorAll('.server-checkbox:checked');
    const selectAll = document.getElementById('serversSelectAll');
    const toolbar = document.getElementById('serversBulkToolbar');
    const selectedCount = document.getElementById('serversSelectedCount');
    
    // 确保元素存在
    if (!selectAll || !toolbar || !selectedCount) {
        return;
    }
    
    const totalCount = checkboxes.length;
    const checkedCount = checkedBoxes.length;
    
    // 更新全选复选框状态
    if (checkedCount === 0) {
        selectAll.indeterminate = false;
        selectAll.checked = false;
    } else if (checkedCount === totalCount) {
        selectAll.indeterminate = false;
        selectAll.checked = true;
    } else {
        selectAll.indeterminate = true;
        selectAll.checked = false;
    }
    
    // 显示/隐藏工具栏和更新计数
    if (checkedCount > 0) {
        toolbar.style.display = 'flex';
        selectedCount.textContent = checkedCount;
    } else {
        toolbar.style.display = 'none';
        selectedCount.textContent = '0';
    }
}

// 清除服务器选择
function clearServersSelection() {
    const checkboxes = document.querySelectorAll('.server-checkbox');
    const selectAll = document.getElementById('serversSelectAll');
    
    checkboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    selectAll.checked = false;
    selectAll.indeterminate = false;
    
    // 立即更新选择状态和计数
    updateServersSelection();
}

// 批量删除服务器
function bulkDeleteServers() {
    const checkedBoxes = document.querySelectorAll('.server-checkbox:checked');
    
    if (checkedBoxes.length === 0) {
        showAlert('请选择要删除的服务器', 'warning');
        return;
    }
    
    const serverIds = Array.from(checkedBoxes).map(checkbox => parseInt(checkbox.value));
    
    // 获取选中的服务器名称
    const selectedServerNames = Array.from(checkedBoxes).map(checkbox => {
        const serverId = parseInt(checkbox.value);
        const server = serversData.find(s => s.id === serverId);
        return server ? server.name : `服务器${serverId}`;
    });
    
    const serverNamesList = selectedServerNames.length > 5 
        ? selectedServerNames.slice(0, 5).join('、') + `等${selectedServerNames.length}个服务器`
        : selectedServerNames.join('、');
    
    if (confirm(`确定要删除选中的 ${serverIds.length} 个服务器吗？\n\n将删除：${serverNamesList}\n\n此操作不可撤销，同时会删除相关的服务配置和监控日志。`)) {
        const deleteBtn = document.getElementById('serversBulkDeleteBtn');
        const originalText = deleteBtn.innerHTML;
        
        deleteBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 删除中...';
        deleteBtn.disabled = true;
        
        safeFetch('/api/servers/bulk-delete', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                server_ids: serverIds
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showAlert(data.message, 'success');
                loadServers(); // 重新加载服务器列表
            } else {
                showAlert('批量删除失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('批量删除服务器失败:', error);
            showAlert('批量删除服务器失败', 'danger');
        })
        .finally(() => {
            deleteBtn.innerHTML = originalText;
            deleteBtn.disabled = false;
        });
    }
}

// ========== 批量导入和一键检测相关函数 ==========

// 全局变量用于记录当前导入类型
let currentImportType = '';

// 下载服务器导入模板
function downloadServerTemplate() {
    window.open('/api/servers/template/download', '_blank');
}

// 下载服务配置导入模板
function downloadServiceTemplate() {
    window.open('/api/services/template/download', '_blank');
}

// 显示批量导入模态框
function showBatchImportModal(type) {
    currentImportType = type;
    const modal = document.getElementById('batchImportModal');
    const title = document.getElementById('batchImportModalTitle');
    
    if (type === 'server') {
        title.innerHTML = '<i class="bi bi-upload"></i> 批量导入服务器';
    } else if (type === 'service') {
        title.innerHTML = '<i class="bi bi-upload"></i> 批量导入服务配置';
    }
    
    // 重置表单
    document.getElementById('batchImportForm').reset();
    document.getElementById('importResults').style.display = 'none';
    document.getElementById('importBtn').disabled = false;
    
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// 执行批量导入
function executeBatchImport() {
    const fileInput = document.getElementById('importFile');
    const file = fileInput.files[0];
    
    if (!file) {
        showAlert('请选择要上传的Excel文件', 'warning');
        return;
    }
    
    if (!file.name.endsWith('.xlsx')) {
        showAlert('只支持.xlsx格式的Excel文件', 'warning');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    const importBtn = document.getElementById('importBtn');
    const originalText = importBtn.innerHTML;
    
    importBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 导入中...';
    importBtn.disabled = true;
    
    let apiUrl = '';
    if (currentImportType === 'server') {
        apiUrl = '/api/servers/batch-import';
    } else if (currentImportType === 'service') {
        apiUrl = '/api/services/batch-import';
    }
    
    safeFetch(apiUrl, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showImportResults(data.data);
            showAlert(data.message, 'success');
            
            // 刷新相关列表
            if (currentImportType === 'server') {
                if (currentSection === 'servers') {
                    loadServers();
                }
            } else if (currentImportType === 'service') {
                if (currentSection === 'services') {
                    loadServices();
                }
            }
        } else {
            showAlert('导入失败: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('批量导入失败:', error);
        showAlert('批量导入失败', 'danger');
    })
    .finally(() => {
        importBtn.innerHTML = originalText;
        importBtn.disabled = false;
    });
}

// 显示导入结果
function showImportResults(result) {
    const resultsDiv = document.getElementById('importResults');
    const summaryDiv = document.getElementById('importSummary');
    const detailsDiv = document.getElementById('importDetails');
    
    // 显示统计信息
    let summaryHtml = `
        <div class="row">
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 text-primary">${result.total}</div>
                    <div class="text-muted">总数</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 text-success">${result.success}</div>
                    <div class="text-muted">成功</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 text-danger">${result.failed}</div>
                    <div class="text-muted">失败</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 text-info">${((result.success / result.total) * 100).toFixed(1)}%</div>
                    <div class="text-muted">成功率</div>
                </div>
            </div>
        </div>
    `;
    
    summaryDiv.innerHTML = summaryHtml;
    
    // 显示失败详情
    if (result.failed_items && result.failed_items.length > 0) {
        let detailsHtml = '<div class="alert alert-warning"><h6>失败详情：</h6><ul class="mb-0">';
        result.failed_items.forEach(item => {
            detailsHtml += `<li><strong>${item.name}</strong>: ${item.error}</li>`;
        });
        detailsHtml += '</ul></div>';
        detailsDiv.innerHTML = detailsHtml;
    } else {
        detailsDiv.innerHTML = '<div class="alert alert-success">所有数据都导入成功！</div>';
    }
    
    resultsDiv.style.display = 'block';
}

// 一键检测服务器连接
function batchTestServers() {
    const btn = event.target.closest('button');
    const originalText = btn.innerHTML;
    
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 检测中...';
    btn.disabled = true;
    
    safeFetch('/api/servers/batch-test', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            server_ids: [] // 空数组表示测试所有活跃服务器
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showBatchTestResults(data.data);
        } else {
            showAlert('检测失败: ' + data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('一键检测失败:', error);
        showAlert('一键检测失败', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalText;
        btn.disabled = false;
    });
}

// 显示批量检测结果
function showBatchTestResults(data) {
    const modal = document.getElementById('batchTestModal');
    const summaryDiv = document.getElementById('testSummary');
    const resultsDiv = document.getElementById('testResults');
    
    // 显示统计信息
    const summary = data.summary;
    let summaryHtml = `
        <div class="row mb-3">
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 text-primary">${summary.total}</div>
                    <div class="text-muted">总数</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 text-success">${summary.success}</div>
                    <div class="text-muted">成功</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 text-danger">${summary.failed}</div>
                    <div class="text-muted">失败</div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="text-center">
                    <div class="h4 text-info">${summary.total > 0 ? ((summary.success / summary.total) * 100).toFixed(1) : 0}%</div>
                    <div class="text-muted">成功率</div>
                </div>
            </div>
        </div>
    `;
    
    summaryDiv.innerHTML = summaryHtml;
    
    // 显示详细结果
    let resultsHtml = '<div class="table-responsive"><table class="table table-sm"><thead><tr><th>服务器名称</th><th>主机地址</th><th>状态</th><th>响应时间</th><th>消息</th></tr></thead><tbody>';
    
    for (const [serverId, result] of Object.entries(data.results)) {
        const statusBadge = result.success ? 
            '<span class="badge bg-success">成功</span>' : 
            '<span class="badge bg-danger">失败</span>';
        
        const responseTime = result.response_time > 0 ? 
            `${(result.response_time * 1000).toFixed(0)}ms` : '-';
        
        const serverName = result.server_name || `服务器${serverId}`;
        const serverHost = result.server_host || 'N/A';
        
        resultsHtml += `
            <tr class="${result.success ? 'table-light' : 'table-danger'}">
                <td><strong>${serverName}</strong></td>
                <td><code>${serverHost}</code></td>
                <td>${statusBadge}</td>
                <td>${responseTime}</td>
                <td>${result.message}</td>
            </tr>
        `;
    }
    
    resultsHtml += '</tbody></table></div>';
    resultsDiv.innerHTML = resultsHtml;
    
    // 显示模态框
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();
}

// 导出检测结果
function exportTestResults() {
    // 这里可以实现导出功能，例如生成CSV或Excel文件
    showAlert('导出功能待实现', 'info');
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
    const errorOverview = document.getElementById('errorServicesOverview');
    const errorServicesList = document.getElementById('errorServicesList');
    const errorServiceCount = document.getElementById('errorServiceCount');
    
    if (!servicesData || servicesData.length === 0) {
        container.innerHTML = `
            <div class="alert alert-info text-center">
                <i class="bi bi-info-circle me-2"></i>
                暂无服务器配置，请先在<a href="#" onclick="showSection('servers')" class="alert-link">服务器管理</a>中添加服务器
            </div>
        `;
        if (errorOverview) {
            errorOverview.style.display = 'none';
        }
        return;
    }
    
    // 收集所有异常服务
    let errorServices = [];
    servicesData.forEach(server => {
        if (server.services) {
            server.services.forEach(service => {
                if (service.is_monitoring && 
                    (service.latest_status === 'stopped' || service.latest_status === 'error')) {
                    errorServices.push({
                        ...service,
                        server_name: server.name,
                        server_id: server.id,
                        server_host: server.host,
                        server_port: server.port
                    });
                }
            });
        }
    });
    
    // 显示/隐藏异常服务概览
    if (errorOverview && errorServicesList && errorServiceCount) {
        if (errorServices.length > 0) {
            errorOverview.style.display = 'block';
            errorServiceCount.textContent = errorServices.length;
            
            let errorHtml = '';
            errorServices.forEach(service => {
                const statusText = service.latest_status === 'stopped' ? '异常' : '错误';
                
                // 格式化首次异常时间
                const firstErrorTime = service.first_error_time ? 
                    new Date(service.first_error_time).toLocaleString('zh-CN') : '未知';
                
                // 计算异常持续时间
                let durationText = '';
                if (service.first_error_time) {
                    const errorDate = new Date(service.first_error_time);
                    const now = new Date();
                    const diffMs = now - errorDate;
                    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
                    const diffDays = Math.floor(diffHours / 24);
                    
                    if (diffDays > 0) {
                        durationText = `已持续 ${diffDays} 天 ${diffHours % 24} 小时`;
                    } else if (diffHours > 0) {
                        durationText = `已持续 ${diffHours} 小时`;
                    } else {
                        const diffMinutes = Math.floor(diffMs / (1000 * 60));
                        durationText = `已持续 ${diffMinutes} 分钟`;
                    }
                }
                
                errorHtml += `
                    <div class="error-service-item mb-3">
                        <div class="row align-items-center">
                            <div class="col-md-1 text-center">
                                <i class="bi bi-exclamation-circle-fill" style="font-size: 2rem; color: #dc3545;"></i>
                            </div>
                            <div class="col-md-2">
                                <h6 class="mb-1 text-danger">
                                    <strong>${service.service_name}</strong>
                                </h6>
                                <span class="badge bg-danger">${statusText}</span>
                            </div>
                            <div class="col-md-2">
                                <small class="text-muted">
                                    <i class="bi bi-hdd-stack me-1"></i><strong>${service.server_name}</strong><br>
                                    <i class="bi bi-router me-1"></i>${service.server_host}:${service.server_port}
                                </small>
                            </div>
                            <div class="col-md-2">
                                <small class="text-muted">
                                    <i class="bi bi-gear me-1"></i>进程: ${service.process_name}
                                </small>
                            </div>
                            <div class="col-md-2">
                                <small class="text-danger">
                                    <i class="bi bi-clock-history me-1"></i><strong>首次异常:</strong><br>
                                    ${firstErrorTime}<br>
                                    ${durationText ? `<span class="text-warning">${durationText}</span>` : ''}
                                </small>
                            </div>
                            <div class="col-md-3 text-end">
                                <button class="btn btn-sm btn-danger me-2" onclick="editService(${service.id})" title="编辑服务">
                                    <i class="bi bi-pencil"></i> 编辑
                                </button>
                                <button class="btn btn-sm btn-warning" onclick="monitorSingleService(${service.id})" title="重新检查">
                                    <i class="bi bi-arrow-clockwise"></i> 重检
                                </button>
                            </div>
                        </div>
                    </div>
                `;
            });
            
            errorServicesList.innerHTML = errorHtml;
        } else {
            errorOverview.style.display = 'none';
        }
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

// 保存服务
function saveService() {
    const serviceId = document.getElementById('serviceId').value;
    // 尝试获取两种可能的服务器ID字段
    let serverId = document.getElementById('serverId') ? document.getElementById('serverId').value : null;
    if (!serverId) {
        serverId = document.getElementById('serviceServerId') ? document.getElementById('serviceServerId').value : null;
    }
    
    const serviceName = document.getElementById('serviceName').value.trim();
    const processName = document.getElementById('processName').value.trim();
    const isMonitoring = document.getElementById('isMonitoring').checked;
    const description = document.getElementById('serviceDescription').value.trim();
    
    console.log('保存服务数据:', {
        serviceId: serviceId,
        serverId: serverId,
        serviceName: serviceName,
        processName: processName,
        isMonitoring: isMonitoring,
        description: description
    });
    
    if (!serverId) {
        showAlert('服务器ID不能为空', 'warning');
        return;
    }
    
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
    
    // 确保 serviceId 是数字或空字符串
    const numericServiceId = serviceId && serviceId.toString().trim() !== '' ? parseInt(serviceId) : null;
    const url = numericServiceId ? `/api/services/${numericServiceId}` : '/api/services';
    const method = numericServiceId ? 'PUT' : 'POST';
    
    console.log('请求信息:', {
        url: url,
        method: method,
        serviceId: numericServiceId,
        data: data
    });
    
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

// ========== 服务配置页面专用函数 ==========

// 添加服务（服务配置页面专用）
function addService(serverId) {
    console.log('服务配置页面 - 添加服务:', serverId);
    
    if (!serverId) {
        showAlert('无效的服务器ID', 'danger');
        return;
    }
    
    // 创建服务配置模态框
    showServiceConfigModal(null, serverId);
}

// 编辑服务（服务配置页面专用）
function editService(serviceId) {
    console.log('服务配置页面 - 编辑服务:', serviceId, typeof serviceId);
    
    // 确保 serviceId 是数字
    const numericServiceId = parseInt(serviceId);
    if (isNaN(numericServiceId)) {
        showAlert('无效的服务ID', 'danger');
        console.error('无效的服务ID:', serviceId);
        return;
    }
    
    // 通过API获取服务详情
    safeFetch(`/api/services/${numericServiceId}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const service = data.data;
                console.log('获取到服务数据:', service);
                
                // 创建编辑服务的模态框
                showServiceConfigModal(numericServiceId, service.server_id, service);
            } else {
                showAlert('获取服务信息失败: ' + data.message, 'danger');
            }
        })
        .catch(error => {
            console.error('获取服务信息失败:', error);
            showAlert('获取服务信息失败', 'danger');
        });
}

// 服务配置页面专用的模态框
function showServiceConfigModal(serviceId = null, serverId = null, serviceData = null) {
    const isEdit = serviceId !== null;
    const title = isEdit ? '编辑服务' : '添加服务';
    
    const modalHtml = `
        <div class="modal fade" id="serviceConfigModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">${title}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <form id="serviceConfigForm">
                            <input type="hidden" id="configServiceId" value="${serviceId || ''}">
                            <input type="hidden" id="configServerId" value="${serverId || ''}">
                            
                            <div class="mb-3">
                                <label for="configServiceName" class="form-label">服务名称 <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="configServiceName" required>
                            </div>
                            
                            <div class="mb-3">
                                <label for="configProcessName" class="form-label">进程名称 <span class="text-danger">*</span></label>
                                <input type="text" class="form-control" id="configProcessName" required>
                                <div class="form-text">用于监控的进程名称，支持部分匹配</div>
                            </div>
                            
                            <div class="mb-3">
                                <div class="form-check">
                                    <input class="form-check-input" type="checkbox" id="configIsMonitoring" checked>
                                    <label class="form-check-label" for="configIsMonitoring">
                                        启用监控
                                    </label>
                                </div>
                            </div>
                            
                            <div class="mb-3">
                                <label for="configServiceDescription" class="form-label">服务描述</label>
                                <textarea class="form-control" id="configServiceDescription" rows="3"></textarea>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">取消</button>
                        <button type="button" class="btn btn-primary" onclick="saveServiceFromConfig()">保存</button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // 移除已存在的模态框
    const existingModal = document.getElementById('serviceConfigModal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // 将新模态框添加到页面中
    const tempContainer = document.createElement('div');
    tempContainer.innerHTML = modalHtml;
    document.body.appendChild(tempContainer.firstElementChild);
    
    // 显示模态框
    const modal = new bootstrap.Modal(document.getElementById('serviceConfigModal'));
    modal.show();
    
    // 如果是编辑模式，填充数据
    if (isEdit && serviceData) {
        setTimeout(() => {
            fillServiceConfigFormData(serviceData);
        }, 200);
    }
}

// 填充服务配置表单数据
function fillServiceConfigFormData(service) {
    const serviceNameEl = document.getElementById('configServiceName');
    const processNameEl = document.getElementById('configProcessName');
    const isMonitoringEl = document.getElementById('configIsMonitoring');
    const serviceDescriptionEl = document.getElementById('configServiceDescription');
    
    if (serviceNameEl) {
        serviceNameEl.value = service.service_name || '';
    }
    
    if (processNameEl) {
        processNameEl.value = service.process_name || '';
    }
    
    if (isMonitoringEl) {
        isMonitoringEl.checked = service.is_monitoring || false;
    }
    
    if (serviceDescriptionEl) {
        serviceDescriptionEl.value = service.description || '';
    }
}

// 从服务配置模态框保存服务
function saveServiceFromConfig() {
    const serviceId = document.getElementById('configServiceId').value;
    const serverId = document.getElementById('configServerId').value;
    const serviceName = document.getElementById('configServiceName').value.trim();
    const processName = document.getElementById('configProcessName').value.trim();
    const isMonitoring = document.getElementById('configIsMonitoring').checked;
    const description = document.getElementById('configServiceDescription').value.trim();
    
    if (!serverId) {
        showAlert('服务器ID不能为空', 'warning');
        return;
    }
    
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
    
    const numericServiceId = serviceId && serviceId.toString().trim() !== '' ? parseInt(serviceId) : null;
    const url = numericServiceId ? `/api/services/${numericServiceId}` : '/api/services';
    const method = numericServiceId ? 'PUT' : 'POST';
    
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
            // 关闭模态框
            const modal = bootstrap.Modal.getInstance(document.getElementById('serviceConfigModal'));
            if (modal) {
                modal.hide();
            }
            // 刷新服务列表
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

// 监控单个服务
function monitorSingleService(serviceId) {
    const btn = event.target.closest('button');
    const originalHtml = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-hourglass-split"></i> 检查中...';
    btn.disabled = true;
    
    safeFetch(`/api/services/monitor/single/${serviceId}`, {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showAlert('服务重检完成', 'success');
            loadServices(); // 重新加载数据
        } else {
            showAlert(data.message, 'danger');
        }
    })
    .catch(error => {
        console.error('监控单个服务失败:', error);
        showAlert('监控单个服务失败', 'danger');
    })
    .finally(() => {
        btn.innerHTML = originalHtml;
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
                            
                            <!-- 内容模板字段已移除，用户可直接在请求体模板中使用变量 -->
                            
                            <div class="mb-3">
                                <label for="notificationRequestBody" class="form-label">请求体模板 (JSON格式)</label>
                                <textarea class="form-control" id="notificationRequestBody" rows="4" 
                                          placeholder='{
  "text": "#context#",
  "channel": "#general"
}'></textarea>
                                <div class="form-text">可选，用于自定义请求体格式，留空将使用默认格式。可使用 #url# 变量获取报告下载链接</div>
                            </div>
                            
                            <!-- OSS配置区域 -->
                            <div class="card mt-4">
                                <div class="card-header">
                                    <div class="form-check form-switch">
                                        <input class="form-check-input" type="checkbox" id="ossEnabled">
                                        <label class="form-check-label" for="ossEnabled">
                                            <i class="bi bi-cloud-upload"></i> 启用阿里云OSS上传
                                        </label>
                                    </div>
                                </div>
                                <div class="card-body" id="ossConfigSection" style="display: none;">
                                    <div class="row">
                                        <div class="col-md-6">
                                            <div class="mb-3">
                                                <label for="ossEndpoint" class="form-label">OSS Endpoint *</label>
                                                <input type="text" class="form-control" id="ossEndpoint" 
                                                       placeholder="https://oss-cn-hangzhou.aliyuncs.com">
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="mb-3">
                                                <label for="ossBucketName" class="form-label">Bucket名称 *</label>
                                                <input type="text" class="form-control" id="ossBucketName" 
                                                       placeholder="my-bucket">
                                            </div>
                                        </div>
                                    </div>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <div class="mb-3">
                                                <label for="ossAccessKeyId" class="form-label">Access Key ID *</label>
                                                <input type="text" class="form-control" id="ossAccessKeyId" 
                                                       placeholder="LTAI...">
                                            </div>
                                        </div>
                                        <div class="col-md-6">
                                            <div class="mb-3">
                                                <label for="ossAccessKeySecret" class="form-label">Access Key Secret *</label>
                                                <input type="password" class="form-control" id="ossAccessKeySecret" 
                                                       placeholder="密钥">
                                            </div>
                                        </div>
                                    </div>
                                    <div class="mb-3">
                                        <label for="ossFolderPath" class="form-label">存储文件夹路径</label>
                                        <input type="text" class="form-control" id="ossFolderPath" 
                                               placeholder="reports" value="reports">
                                        <div class="form-text">可选，默认为 reports，用于组织文件存储结构</div>
                                    </div>
                                    <div class="alert alert-info">
                                        <i class="bi bi-info-circle"></i>
                                        启用OSS上传后，系统会自动将生成的巡检报告上传到阿里云OSS，并在通知中提供 #url# 变量用于获取下载链接。
                                    </div>
                                </div>
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
    
    // 添加OSS开关事件监听器
    document.getElementById('ossEnabled').addEventListener('change', function() {
        const ossConfigSection = document.getElementById('ossConfigSection');
        if (this.checked) {
            ossConfigSection.style.display = 'block';
        } else {
            ossConfigSection.style.display = 'none';
        }
    });
    
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
        // content_template字段已移除，直接在请求体模板中使用变量
        request_body: document.getElementById('notificationRequestBody').value.trim(),
        // OSS配置
        oss_enabled: document.getElementById('ossEnabled').checked,
        oss_endpoint: document.getElementById('ossEndpoint').value.trim(),
        oss_access_key_id: document.getElementById('ossAccessKeyId').value.trim(),
        oss_access_key_secret: document.getElementById('ossAccessKeySecret').value.trim(),
        oss_bucket_name: document.getElementById('ossBucketName').value.trim(),
        oss_folder_path: document.getElementById('ossFolderPath').value.trim()
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
    
    // 验证OSS配置
    if (data.oss_enabled) {
        if (!data.oss_endpoint || !data.oss_access_key_id || !data.oss_access_key_secret || !data.oss_bucket_name) {
            showAlert('启用OSS上传时，请填写完整的OSS配置信息', 'warning');
            return;
        }
        
        // 验证Endpoint格式
        if (!data.oss_endpoint.startsWith('http://') && !data.oss_endpoint.startsWith('https://')) {
            showAlert('OSS Endpoint格式不正确，请以http://或https://开头', 'warning');
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
                            
                            <!-- 内容模板字段已移除，用户可直接在请求体模板中使用变量 -->
                            
                            <div class="mb-3">
                                <label for="notificationRequestBody" class="form-label">请求体模板 (JSON格式)</label>
                                <textarea class="form-control" id="notificationRequestBody" rows="4">${channel.request_body || ''}</textarea>
                                <div class="form-text">可选，用于自定义请求体格式，留空将使用默认格式。支持变量：#context#（巡检结果）、#url#（报告下载链接，需启用OSS）</div>
                            </div>
                            
                            <!-- 阿里云OSS配置 -->
                            <div class="card mt-3">
                                <div class="card-header">
                                    <h6 class="mb-0">
                                        <i class="bi bi-cloud-upload"></i>
                                        阿里云OSS配置
                                    </h6>
                                </div>
                                <div class="card-body">
                                    <div class="mb-3">
                                        <div class="form-check form-switch">
                                            <input class="form-check-input" type="checkbox" id="ossEnabled" ${channel.oss_enabled ? 'checked' : ''}>
                                            <label class="form-check-label" for="ossEnabled">启用OSS上传报告</label>
                                        </div>
                                        <div class="form-text">启用后，生成的巡检报告将自动上传到阿里云OSS，并在通知中提供下载链接</div>
                                    </div>
                                    
                                    <div id="ossConfigSection" style="display: ${channel.oss_enabled ? 'block' : 'none'}">
                                        <div class="row">
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label for="ossEndpoint" class="form-label">Endpoint *</label>
                                                    <input type="text" class="form-control" id="ossEndpoint" value="${channel.oss_endpoint || ''}" placeholder="https://oss-cn-hangzhou.aliyuncs.com">
                                                    <div class="form-text">OSS服务的访问域名</div>
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label for="ossBucketName" class="form-label">Bucket名称 *</label>
                                                    <input type="text" class="form-control" id="ossBucketName" value="${channel.oss_bucket_name || ''}" placeholder="my-bucket">
                                                    <div class="form-text">存储报告的Bucket名称</div>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <div class="row">
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label for="ossAccessKeyId" class="form-label">Access Key ID *</label>
                                                    <input type="text" class="form-control" id="ossAccessKeyId" value="${channel.oss_access_key_id || ''}">
                                                    <div class="form-text">阿里云访问密钥ID</div>
                                                </div>
                                            </div>
                                            <div class="col-md-6">
                                                <div class="mb-3">
                                                    <label for="ossAccessKeySecret" class="form-label">Access Key Secret *</label>
                                                    <input type="password" class="form-control" id="ossAccessKeySecret" value="${channel.oss_access_key_secret || ''}">
                                                    <div class="form-text">阿里云访问密钥Secret</div>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <div class="mb-3">
                                            <label for="ossFolderPath" class="form-label">存储文件夹路径</label>
                                            <input type="text" class="form-control" id="ossFolderPath" value="${channel.oss_folder_path || ''}" placeholder="reports/">
                                            <div class="form-text">可选，报告在OSS中的存储路径，留空则存储在根目录</div>
                                        </div>
                                    </div>
                                </div>
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
    
    // 为OSS开关添加事件监听器
    document.getElementById('ossEnabled').addEventListener('change', function() {
        const ossConfigSection = document.getElementById('ossConfigSection');
        if (this.checked) {
            ossConfigSection.style.display = 'block';
        } else {
            ossConfigSection.style.display = 'none';
        }
    });
    
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
    
    // 延迟一点获取状态，确保复选框状态已更新
    setTimeout(() => {
        const isChecked = selectAll.checked;
        
        checkboxes.forEach(checkbox => {
            checkbox.checked = isChecked;
        });
        
        // 立即更新选择状态
        updateReportsSelection();
    }, 0);
}

// 更新报告选择状态
function updateReportsSelection() {
    const checkboxes = document.querySelectorAll('.report-checkbox');
    const checkedBoxes = document.querySelectorAll('.report-checkbox:checked');
    const selectAll = document.getElementById('reportsSelectAll');
    const toolbar = document.getElementById('reportsBulkToolbar');
    const selectedCount = document.getElementById('reportsSelectedCount');
    
    // 确保元素存在
    if (!selectAll || !toolbar || !selectedCount) {
        return;
    }
    
    const totalCount = checkboxes.length;
    const checkedCount = checkedBoxes.length;
    
    // 更新全选复选框状态
    if (checkedCount === 0) {
        selectAll.indeterminate = false;
        selectAll.checked = false;
    } else if (checkedCount === totalCount) {
        selectAll.indeterminate = false;
        selectAll.checked = true;
    } else {
        selectAll.indeterminate = true;
        selectAll.checked = false;
    }
    
    // 显示/隐藏工具栏和更新计数
    if (checkedCount > 0) {
        toolbar.style.display = 'flex';
        selectedCount.textContent = checkedCount;
    } else {
        toolbar.style.display = 'none';
        selectedCount.textContent = '0';
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
    
    // 立即更新选择状态和计数
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