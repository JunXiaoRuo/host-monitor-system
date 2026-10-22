let configurationPreviewFile = null;
const configurationMaxBytes = 10 * 1024 * 1024;

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('configIncludePasswords').addEventListener('change', event => {
        document.getElementById('configPasswordNotice').hidden = !event.target.checked;
    });
    document.getElementById('configImportFile').addEventListener('change', resetConfigurationPreview);
    document.getElementById('configExportBtn').addEventListener('click', exportConfiguration);
    document.getElementById('configPreviewBtn').addEventListener('click', () => importConfiguration(true));
    document.getElementById('configImportBtn').addEventListener('click', () => importConfiguration(false));
});

function setConfigurationStatus(id, message, failed = false) {
    const element = document.getElementById(id);
    element.textContent = message;
    element.classList.toggle('text-danger', failed);
    element.classList.toggle('text-success', !failed && Boolean(message));
}

function resetConfigurationPreview() {
    configurationPreviewFile = null;
    document.getElementById('configImportBtn').disabled = true;
    document.getElementById('configImportPreview').hidden = true;
    document.getElementById('configImportWarnings').replaceChildren();
    setConfigurationStatus('configImportStatus', '');
}

async function exportConfiguration() {
    const button = document.getElementById('configExportBtn');
    button.disabled = true;
    setConfigurationStatus('configExportStatus', '');
    try {
        const response = await safeFetch('/api/config/export', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                include_server_passwords: document.getElementById('configIncludePasswords').checked
            })
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.message || '导出失败');
        }
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        const disposition = response.headers.get('Content-Disposition') || '';
        const filename = disposition.match(/filename="?([^";]+)"?/i);
        link.href = url;
        link.download = filename ? filename[1] : 'host-monitor-config.json';
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        setConfigurationStatus('configExportStatus', '配置已导出');
    } catch (error) {
        setConfigurationStatus('configExportStatus', error.message || '导出失败，请稍后重试', true);
    } finally {
        button.disabled = false;
    }
}

function renderConfigurationSummary(data) {
    const body = document.getElementById('configImportSummary');
    body.replaceChildren();
    Object.values(data.sections).forEach(section => {
        const row = document.createElement('tr');
        [section.label, section.created, section.updated].forEach((value, index) => {
            const cell = document.createElement('td');
            cell.textContent = value;
            if (index > 0) cell.className = 'text-end';
            row.appendChild(cell);
        });
        body.appendChild(row);
    });
    const missingPasswords = document.getElementById('configMissingPasswords');
    missingPasswords.hidden = !data.servers_without_password;
    missingPasswords.textContent = `${data.servers_without_password} 台新增服务器未包含密码或私钥路径，密码登录前需补充凭据。`;
    const warnings = document.getElementById('configImportWarnings');
    warnings.replaceChildren();
    (data.warnings || []).forEach(message => {
        const paragraph = document.createElement('p');
        paragraph.textContent = message;
        warnings.appendChild(paragraph);
    });
    document.getElementById('configImportPreview').hidden = false;
}

async function importConfiguration(preview) {
    const input = document.getElementById('configImportFile');
    const file = input.files[0];
    if (!file || !file.name.toLowerCase().endsWith('.json')) {
        setConfigurationStatus('configImportStatus', '请选择 JSON 配置文件', true);
        return;
    }
    if (file.size > configurationMaxBytes) {
        setConfigurationStatus('configImportStatus', '配置文件不能超过 10 MB', true);
        return;
    }
    if (!preview && configurationPreviewFile !== file) {
        setConfigurationStatus('configImportStatus', '请先校验当前配置文件', true);
        return;
    }
    const previewButton = document.getElementById('configPreviewBtn');
    const importButton = document.getElementById('configImportBtn');
    resetConfigurationPreview();
    input.disabled = true;
    previewButton.disabled = true;
    setConfigurationStatus('configImportStatus', preview ? '正在校验...' : '正在导入...');
    try {
        const form = new FormData();
        form.append('file', file);
        form.append('preview', String(preview));
        const response = await safeFetch('/api/config/import', {method: 'POST', body: form});
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.message || '操作失败');
        renderConfigurationSummary(result.data);
        setConfigurationStatus('configImportStatus', result.message);
        if (preview) {
            configurationPreviewFile = file;
        } else {
            loadThresholds();
        }
    } catch (error) {
        setConfigurationStatus('configImportStatus', error.message || '操作失败，请稍后重试', true);
    } finally {
        input.disabled = false;
        previewButton.disabled = false;
        importButton.disabled = configurationPreviewFile !== file;
    }
}
