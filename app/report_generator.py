import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from jinja2 import Template
import logging

logger = logging.getLogger(__name__)

class ReportGenerator:
    """HTML报告生成器"""
    
    def __init__(self, report_dir: str = "reports"):
        self.report_dir = report_dir
        self._ensure_report_dir()
    
    def _ensure_report_dir(self):
        """确保报告目录存在"""
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)
    
    def generate_html_report(self, monitor_data: Dict[str, Any], report_name: str = None) -> Optional[str]:
        """
        生成HTML监控报告
        
        Args:
            monitor_data: 监控数据
            report_name: 报告名称
            
        Returns:
            报告文件路径或None
        """
        try:
            if not report_name:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                report_name = f"monitor_report_{timestamp}"
            
            # 生成HTML内容
            html_content = self._generate_html_content(monitor_data)
            
            # 保存文件
            file_path = os.path.join(self.report_dir, f"{report_name}.html")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"HTML报告生成成功: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"生成HTML报告失败: {str(e)}")
            return None
    
    def _generate_html_content(self, monitor_data: Dict[str, Any]) -> str:
        """生成HTML内容"""
        
        # HTML模板
        html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>主机巡视报告 - {{ monitor_time }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .summary-card {
            background: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
            border-left: 4px solid #ddd;
        }
        
        .summary-card.success {
            border-left-color: #28a745;
        }
        
        .summary-card.warning {
            border-left-color: #ffc107;
        }
        
        .summary-card.error {
            border-left-color: #dc3545;
        }
        
        .summary-card.total {
            border-left-color: #007bff;
        }
        
        .summary-card h3 {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        .summary-card.success h3 {
            color: #28a745;
        }
        
        .summary-card.warning h3 {
            color: #ffc107;
        }
        
        .summary-card.error h3 {
            color: #dc3545;
        }
        
        .summary-card.total h3 {
            color: #007bff;
        }
        
        .threshold-info {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .threshold-info h2 {
            color: #333;
            margin-bottom: 15px;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }
        
        .threshold-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .threshold-item {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
        }
        
        .server-results {
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .server-results h2 {
            background: #343a40;
            color: white;
            padding: 20px;
            margin: 0;
        }
        
        .server-item {
            border-bottom: 1px solid #eee;
            padding: 20px;
        }
        
        .server-item:last-child {
            border-bottom: none;
        }
        
        .server-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }
        
        .server-name-section {
            flex: 1;
        }
        
        .server-name {
            font-size: 1.3em;
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .server-ip {
            color: #6c757d;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .server-ip i {
            color: #007bff;
        }
        
        .server-status {
            padding: 5px 15px;
            border-radius: 20px;
            color: white;
            font-weight: bold;
            text-transform: uppercase;
        }
        
        .status-success {
            background-color: #28a745;
        }
        
        .status-warning {
            background-color: #ffc107;
        }
        
        .status-failed {
            background-color: #dc3545;
        }
        
        .server-details {
            display: block;
        }
        
        .detail-section {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }
        
        .detail-section .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
        }
        
        .detail-section h4 {
            color: #495057;
            margin-bottom: 10px;
            border-bottom: 1px solid #dee2e6;
            padding-bottom: 5px;
        }
        
        .metric {
            display: block;
            margin-bottom: 0;
            padding: 8px;
            background: white;
            border-radius: 4px;
            border-left: 3px solid #007bff;
        }
        
        .metric-label {
            font-weight: bold;
            display: block;
            margin-bottom: 4px;
            color: #495057;
            font-size: 0.9em;
        }
        
        .metric-value {
            color: #6c757d;
            display: block;
            word-break: break-word;
            font-size: 1.1em;
        }
        
        .metric-high {
            color: #dc3545;
            font-weight: bold;
        }
        
        .disk-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            table-layout: fixed;
            max-width: 100%;
            overflow: hidden;
        }
        
        .disk-table th,
        .disk-table td {
            padding: 8px 12px;
            border: 1px solid #dee2e6;
            text-align: left;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        
        .disk-table th:nth-child(1),
        .disk-table td:nth-child(1) {
            width: 25%;
        }
        
        .disk-table th:nth-child(2),
        .disk-table td:nth-child(2) {
            width: 20%;
        }
        
        .disk-table th:nth-child(3),
        .disk-table td:nth-child(3) {
            width: 15%;
        }
        
        .disk-table th:nth-child(4),
        .disk-table td:nth-child(4) {
            width: 15%;
        }
        
        .disk-table th:nth-child(5),
        .disk-table td:nth-child(5) {
            width: 15%;
        }
        
        .disk-table th:nth-child(6),
        .disk-table td:nth-child(6) {
            width: 10%;
        }
        
        .disk-table th {
            background-color: #e9ecef;
            font-weight: bold;
        }
        
        .disk-high {
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .alerts {
            margin-top: 15px;
        }
        
        .alert {
            padding: 10px 15px;
            border-radius: 5px;
            margin-bottom: 10px;
            border-left: 4px solid #ffc107;
            background-color: #fff3cd;
            color: #856404;
        }
        
        .alert.error {
            border-left-color: #dc3545;
            background-color: #f8d7da;
            color: #721c24;
        }
        
        .system-info {
            margin-top: 15px;
        }
        
        .system-info-grid {
            display: block;
        }
        
        .system-info .metric {
            margin-bottom: 8px;
            padding: 6px;
            font-size: 0.9em;
        }
        
        .system-info .metric-label {
            font-size: 0.8em;
        }
        
        .system-info .metric-value {
            font-size: 0.9em;
        }
        
        .footer {
            margin-top: 40px;
            text-align: center;
            color: #6c757d;
            padding: 20px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .execution-time {
            font-style: italic;
            color: #6c757d;
            margin-top: 10px;
        }
        
        /* 告警段落样式 */
        .alert-section {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 5px solid #dc3545;
        }
        
        .alert-server-item {
            margin-bottom: 25px;
            padding: 15px;
            background: #fef2f2;
            border-radius: 8px;
            border: 1px solid #fecaca;
        }
        
        .server-alert-header {
            margin-bottom: 15px;
        }
        
        .alert-server-summary {
            margin-top: 10px;
            padding: 8px;
            background: #fee2e2;
            border-radius: 4px;
            font-size: 0.9em;
            color: #991b1b;
        }
        
        /* 连接失败段落样式 */
        .failed-section {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-left: 5px solid #dc3545;
        }
        
        .failed-server-item {
            margin-bottom: 20px;
            padding: 15px;
            background: #fef2f2;
            border-radius: 8px;
            border: 1px solid #fecaca;
        }
        
        .server-failed-header {
            margin-bottom: 15px;
        }
        
        .failed-server-info {
            margin-top: 10px;
            padding: 8px;
            background: #fee2e2;
            border-radius: 4px;
            font-size: 0.9em;
            color: #991b1b;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            
            .summary {
                grid-template-columns: 1fr;
            }
            
            .server-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 10px;
            }
            
            .server-details {
                grid-template-columns: 1fr;
            }
            
            .metric {
                margin-bottom: 8px;
                padding: 6px;
            }
            
            .metric-label {
                font-size: 0.75em;
            }
            
            .metric-value {
                font-size: 0.85em;
            }
            
            .system-info .metric {
                margin-bottom: 6px;
                padding: 5px;
            }
            
            .system-info .metric-label {
                font-size: 0.7em;
            }
            
            .system-info .metric-value {
                font-size: 0.8em;
            }
            
            .disk-table {
                font-size: 0.8em;
            }
            
            .disk-table th,
            .disk-table td {
                padding: 6px 4px;
                word-break: break-word;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>主机巡视报告</h1>
            <p>生成时间: {{ monitor_time }}</p>
        </div>
        
        <div class="summary">
            <div class="summary-card total">
                <h3>{{ total_servers }}</h3>
                <p>总服务器数</p>
            </div>
            <div class="summary-card success">
                <h3>{{ success_count }}</h3>
                <p>正常服务器</p>
            </div>
            <div class="summary-card warning">
                <h3>{{ warning_count }}</h3>
                <p>告警服务器</p>
            </div>
            <div class="summary-card error">
                <h3>{{ failed_count }}</h3>
                <p>失败服务器</p>
            </div>
        </div>
        
        <!-- 告警信息段 - 放在前面 -->
        {% set alert_servers = [] %}
        {% for result in results %}
            {% if result.alerts and result.alerts|length > 0 %}
                {% set _ = alert_servers.append(result) %}
            {% endif %}
        {% endfor %}
        
        {% if alert_servers|length > 0 %}
        <div class="alert-section">
            <h2 style="color: #dc3545; border-bottom: 2px solid #dc3545; padding-bottom: 10px;">
                <i class="fas fa-exclamation-triangle"></i> 重要告警 ({{ alert_servers|length }} 台服务器)
            </h2>
            {% for server in alert_servers %}
            <div class="alert-server-item">
                <div class="server-alert-header">
                    <h3 style="color: #dc3545;">
                        {{ server.server_name }} 
                        <span style="font-size: 0.8em; color: #6c757d;">
                            ({{ server.server_ip or '未知IP' }})
                        </span>
                    </h3>
                </div>
                {% for alert in server.alerts %}
                <div class="alert {{ alert.level }}">
                    <strong>{{ alert.type.upper() }}告警:</strong> {{ alert.message }}
                    {% if alert.filesystem %}
                    <br><small>文件系统: {{ alert.filesystem }} | 挂载点: {{ alert.mounted_on }}</small>
                    {% endif %}
                </div>
                {% endfor %}
                <div class="alert-server-summary">
                    <span>CPU: {{ server.cpu_usage|round(1) if server.cpu_usage is not none else 'N/A' }}%</span> | 
                    <span>内存: {{ server.memory_usage|round(1) if server.memory_usage is not none else 'N/A' }}%</span> | 
                    <span>磁盘告警: {{ server.alerts|selectattr('type', 'equalto', 'disk')|list|length }}个</span>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        <!-- 连接失败信息段 - 放在告警后面 -->
        {% set failed_servers = [] %}
        {% for result in results %}
            {% if result.error_message %}
                {% set _ = failed_servers.append(result) %}
            {% endif %}
        {% endfor %}
        
        {% if failed_servers|length > 0 %}
        <div class="failed-section">
            <h2 style="color: #dc3545; border-bottom: 2px solid #dc3545; padding-bottom: 10px;">
                <i class="fas fa-times-circle"></i> 连接失败 ({{ failed_servers|length }} 台服务器)
            </h2>
            {% for server in failed_servers %}
            <div class="failed-server-item">
                <div class="server-failed-header">
                    <h3 style="color: #dc3545;">
                        {{ server.server_name }}
                        <span style="font-size: 0.8em; color: #6c757d;">
                            ({{ server.server_ip or '未知IP' }})
                        </span>
                    </h3>
                </div>
                <div class="alert error">
                    <strong>连接失败:</strong> {{ server.error_message }}
                </div>
                <div class="failed-server-info">
                    <span>状态: {{ server.status }}</span>
                    {% if server.execution_time %}
                     | <span>耗时: {{ "%.2f"|format(server.execution_time) }}秒</span>
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        <div class="threshold-info">
            <h2>阈值配置</h2>
            <div class="threshold-grid">
                <div class="threshold-item">
                    <strong>CPU阈值</strong><br>
                    {{ thresholds.cpu_threshold }}%
                </div>
                <div class="threshold-item">
                    <strong>内存阈值</strong><br>
                    {{ thresholds.memory_threshold }}%
                </div>
                <div class="threshold-item">
                    <strong>磁盘阈值</strong><br>
                    {{ thresholds.disk_threshold }}%
                </div>
            </div>
        </div>
        
        <div class="server-results">
            <h2>服务器详细信息</h2>
            {% for result in results %}
            <div class="server-item">
                <div class="server-header">
                    <div class="server-name-section">
                        <div class="server-name">{{ result.server_name }}</div>
                        <div class="server-ip">
                            <i class="fas fa-network-wired"></i> {{ result.server_ip }}
                        </div>
                    </div>
                    <div class="server-status status-{{ result.status }}">{{ result.status }}</div>
                </div>
                
                {% if result.error_message %}
                <div class="alerts">
                    <div class="alert error">
                        <strong>连接失败:</strong> {{ result.error_message }}
                    </div>
                </div>
                {% else %}
                <div class="server-details">
                    <div class="detail-section">
                        <h4>系统资源</h4>
                        <div class="metrics-grid">
                            {% if result.cpu_usage is not none %}
                            <div class="metric">
                                <span class="metric-label">CPU使用率:</span>
                                <span class="metric-value {% if result.cpu_usage > thresholds.cpu_threshold %}metric-high{% endif %}">
                                    {{ "%.2f"|format(result.cpu_usage) }}%
                                </span>
                            </div>
                            {% endif %}
                            
                            {% if result.memory_usage is not none %}
                            <div class="metric">
                                <span class="metric-label">内存使用率:</span>
                                <span class="metric-value {% if result.memory_usage > thresholds.memory_threshold %}metric-high{% endif %}">
                                    {{ "%.2f"|format(result.memory_usage) }}%
                                </span>
                            </div>
                            {% endif %}
                            
                            {% if result.memory_info %}
                            <div class="metric">
                                <span class="metric-label">总内存:</span>
                                <span class="metric-value">
                                    {% if result.memory_info.total_mb %}
                                        {{ result.memory_info.total_mb }}MB ({{ result.memory_info.total_gb }}GB)
                                    {% else %}
                                        N/A
                                    {% endif %}
                                </span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">使用内存:</span>
                                <span class="metric-value">
                                    {% if result.memory_info.used_mb %}
                                        {{ result.memory_info.used_mb }}MB ({{ result.memory_info.used_gb }}GB)
                                    {% else %}
                                        N/A
                                    {% endif %}
                                </span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">空闲内存:</span>
                                <span class="metric-value">
                                    {% if result.memory_info.free_mb %}
                                        {{ result.memory_info.free_mb }}MB ({{ result.memory_info.free_gb }}GB)
                                    {% else %}
                                        N/A
                                    {% endif %}
                                </span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">可用内存:</span>
                                <span class="metric-value">
                                    {% if result.memory_info.available_mb %}
                                        {{ result.memory_info.available_mb }}MB ({{ result.memory_info.available_gb }}GB)
                                    {% else %}
                                        N/A
                                    {% endif %}
                                </span>
                            </div>
                            {% endif %}
                            
                            <div class="metric">
                                <span class="metric-label">执行耗时:</span>
                                <span class="metric-value">{{ "%.2f"|format(result.execution_time) }}秒</span>
                            </div>
                        </div>
                    </div>
                    
                    {% if result.disk_info %}
                    <div class="detail-section">
                        <h4>磁盘使用情况</h4>
                        <table class="disk-table">
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
                                {% for disk in result.disk_info %}
                                <tr {% if disk.use_percent > thresholds.disk_threshold %}class="disk-high"{% endif %}>
                                    <td>{{ disk.filesystem }}</td>
                                    <td>{{ disk.mounted_on }}</td>
                                    <td>{{ disk.size }}</td>
                                    <td>{{ disk.used }}</td>
                                    <td>{{ disk.available }}</td>
                                    <td>{{ "%.1f"|format(disk.use_percent) }}%</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                    {% endif %}
                </div>
                
                {% if result.alerts %}
                <div class="alerts">
                    <h4>告警信息</h4>
                    {% for alert in result.alerts %}
                    <div class="alert">
                        <strong>{{ alert.type|upper }}告警:</strong> {{ alert.message }}
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
                
                {% if result.system_info %}
                <div class="system-info">
                    <h4>系统信息</h4>
                    <div class="system-info-grid">
                        {% for key, value in result.system_info.items() %}
                        <div class="metric">
                            <span class="metric-label">{{ key }}:</span>
                            <span class="metric-value">{{ value }}</span>
                        </div>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}
                {% endif %}
            </div>
            {% endfor %}
        </div>
        
        <div class="footer">
            <p>主机巡视系统自动生成</p>
            <p class="execution-time">总执行时间: {{ "%.2f"|format(execution_time) }}秒</p>
        </div>
    </div>
</body>
</html>
        """
        
        # 渲染模板
        template = Template(html_template)
        
        # 格式化监控时间
        monitor_time = monitor_data.get('monitor_time', datetime.now().isoformat())
        if isinstance(monitor_time, str):
            try:
                dt = datetime.fromisoformat(monitor_time.replace('Z', '+00:00'))
                monitor_time = dt.strftime('%Y年%m月%d日 %H:%M:%S')
            except:
                monitor_time = monitor_time
        
        html_content = template.render(
            monitor_time=monitor_time,
            total_servers=monitor_data.get('total_servers', 0),
            success_count=monitor_data.get('success_count', 0),
            warning_count=monitor_data.get('warning_count', 0),
            failed_count=monitor_data.get('failed_count', 0),
            execution_time=monitor_data.get('execution_time', 0),
            thresholds=monitor_data.get('thresholds', {}),
            results=monitor_data.get('results', [])
        )
        
        return html_content
    
    def generate_summary_report(self, start_date: datetime, end_date: datetime, 
                              server_stats: List[Dict[str, Any]]) -> Optional[str]:
        """
        生成汇总报告
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            server_stats: 服务器统计数据
            
        Returns:
            报告文件路径或None
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_name = f"summary_report_{timestamp}"
            
            # 生成汇总HTML内容
            html_content = self._generate_summary_html_content(
                start_date, end_date, server_stats
            )
            
            # 保存文件
            file_path = os.path.join(self.report_dir, f"{report_name}.html")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"汇总报告生成成功: {file_path}")
            return file_path
            
        except Exception as e:
            logger.error(f"生成汇总报告失败: {str(e)}")
            return None
    
    def _generate_summary_html_content(self, start_date: datetime, 
                                     end_date: datetime, 
                                     server_stats: List[Dict[str, Any]]) -> str:
        """生成汇总HTML内容"""
        
        # 简化的汇总报告模板
        html_template = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>主机巡视汇总报告</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f5f5f5;
            margin: 0;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .content {
            padding: 30px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 5px;
            text-align: center;
            border-left: 4px solid #007bff;
        }
        
        .stat-card h3 {
            font-size: 2em;
            margin-bottom: 10px;
            color: #007bff;
        }
        
        .server-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        
        .server-table th,
        .server-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #dee2e6;
        }
        
        .server-table th {
            background-color: #e9ecef;
            font-weight: bold;
        }
        
        .footer {
            background: #f8f9fa;
            padding: 20px;
            text-align: center;
            color: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>主机巡视汇总报告</h1>
            <p>统计期间: {{ start_date }} - {{ end_date }}</p>
        </div>
        
        <div class="content">
            <div class="stats-grid">
                <div class="stat-card">
                    <h3>{{ total_servers }}</h3>
                    <p>监控服务器总数</p>
                </div>
                <div class="stat-card">
                    <h3>{{ total_checks }}</h3>
                    <p>总监控次数</p>
                </div>
                <div class="stat-card">
                    <h3>{{ "%.1f"|format(avg_success_rate) }}%</h3>
                    <p>平均成功率</p>
                </div>
                <div class="stat-card">
                    <h3>{{ total_alerts }}</h3>
                    <p>总告警次数</p>
                </div>
            </div>
            
            <h2>服务器统计详情</h2>
            <table class="server-table">
                <thead>
                    <tr>
                        <th>服务器名称</th>
                        <th>监控次数</th>
                        <th>成功次数</th>
                        <th>告警次数</th>
                        <th>失败次数</th>
                        <th>成功率</th>
                    </tr>
                </thead>
                <tbody>
                    {% for stat in server_stats %}
                    <tr>
                        <td>{{ stat.server_name }}</td>
                        <td>{{ stat.total_checks }}</td>
                        <td>{{ stat.success_count }}</td>
                        <td>{{ stat.warning_count }}</td>
                        <td>{{ stat.failed_count }}</td>
                        <td>{{ "%.1f"|format(stat.success_rate) }}%</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>报告生成时间: {{ generate_time }}</p>
            <p>主机巡视系统自动生成</p>
        </div>
    </div>
</body>
</html>
        """
        
        # 计算统计数据
        total_servers = len(server_stats)
        total_checks = sum(stat.get('total_checks', 0) for stat in server_stats)
        total_alerts = sum(stat.get('warning_count', 0) for stat in server_stats)
        
        success_rates = [stat.get('success_rate', 0) for stat in server_stats if stat.get('total_checks', 0) > 0]
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
        
        # 渲染模板
        template = Template(html_template)
        html_content = template.render(
            start_date=start_date.strftime('%Y年%m月%d日'),
            end_date=end_date.strftime('%Y年%m月%d日'),
            total_servers=total_servers,
            total_checks=total_checks,
            avg_success_rate=avg_success_rate,
            total_alerts=total_alerts,
            server_stats=server_stats,
            generate_time=datetime.now().strftime('%Y年%m月%d日 %H:%M:%S')
        )
        
        return html_content
    
    def get_report_list(self) -> List[Dict[str, Any]]:
        """获取报告文件列表"""
        try:
            reports = []
            
            if not os.path.exists(self.report_dir):
                return reports
            
            for filename in os.listdir(self.report_dir):
                if filename.endswith('.html'):
                    file_path = os.path.join(self.report_dir, filename)
                    file_stat = os.stat(file_path)
                    
                    reports.append({
                        'filename': filename,
                        'file_path': file_path,
                        'size': file_stat.st_size,
                        'created_time': datetime.fromtimestamp(file_stat.st_ctime),
                        'modified_time': datetime.fromtimestamp(file_stat.st_mtime)
                    })
            
            # 按修改时间倒序排列
            reports.sort(key=lambda x: x['modified_time'], reverse=True)
            
            return reports
            
        except Exception as e:
            logger.error(f"获取报告列表失败: {str(e)}")
            return []
    
    def delete_report(self, filename: str) -> bool:
        """删除报告文件"""
        try:
            file_path = os.path.join(self.report_dir, filename)
            
            if os.path.exists(file_path) and filename.endswith('.html'):
                os.remove(file_path)
                logger.info(f"报告文件删除成功: {filename}")
                return True
            else:
                logger.warning(f"报告文件不存在: {filename}")
                return False
                
        except Exception as e:
            logger.error(f"删除报告文件失败: {str(e)}")
            return False