from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import hashlib
import secrets

db = SQLAlchemy()

# 获取本地时间的辅助函数
def get_local_time():
    """获取本地时间"""
    return datetime.now()

class Server(db.Model):
    """服务器信息表"""
    __tablename__ = 'servers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='服务器名称')
    host = db.Column(db.String(100), nullable=False, comment='主机地址')
    port = db.Column(db.Integer, default=22, comment='SSH端口')
    username = db.Column(db.String(50), nullable=False, comment='用户名')
    password = db.Column(db.Text, comment='密码')
    private_key_path = db.Column(db.String(200), comment='私钥文件路径')
    description = db.Column(db.Text, comment='描述')
    status = db.Column(db.String(20), default='active', comment='状态: active/inactive')
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    
    # 关联关系
    monitor_logs = db.relationship('MonitorLog', backref='server', lazy=True, cascade='all, delete-orphan')
    service_configs = db.relationship('ServiceConfig', backref='server', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'description': self.description,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Threshold(db.Model):
    """阈值配置表"""
    __tablename__ = 'thresholds'
    
    id = db.Column(db.Integer, primary_key=True)
    cpu_threshold = db.Column(db.Float, default=80.0, comment='CPU使用率阈值(%)')
    memory_threshold = db.Column(db.Float, default=80.0, comment='内存使用率阈值(%)')
    disk_threshold = db.Column(db.Float, default=80.0, comment='磁盘使用率阈值(%)')
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    
    def to_dict(self):
        return {
            'id': self.id,
            'cpu_threshold': self.cpu_threshold,
            'memory_threshold': self.memory_threshold,
            'disk_threshold': self.disk_threshold,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ScheduleTask(db.Model):
    """计划任务表"""
    __tablename__ = 'schedule_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='任务名称')
    task_type = db.Column(db.String(20), nullable=False, comment='任务类型: daily/weekly/monthly')
    schedule_config = db.Column(db.Text, comment='调度配置JSON')
    is_active = db.Column(db.Boolean, default=True, comment='是否启用')
    last_run = db.Column(db.DateTime, comment='最后执行时间')
    next_run = db.Column(db.DateTime, comment='下次执行时间')
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    
    def get_schedule_config(self):
        if self.schedule_config:
            return json.loads(self.schedule_config)
        return {}
    
    def set_schedule_config(self, config):
        self.schedule_config = json.dumps(config)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'task_type': self.task_type,
            'schedule_config': self.get_schedule_config(),
            'is_active': self.is_active,
            'last_run': self.last_run.isoformat() if self.last_run else None,
            'next_run': self.next_run.isoformat() if self.next_run else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class MonitorLog(db.Model):
    """监控日志表"""
    __tablename__ = 'monitor_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    monitor_time = db.Column(db.DateTime, default=get_local_time, comment='监控时间')
    status = db.Column(db.String(20), comment='状态: success/failed/warning')
    cpu_usage = db.Column(db.Float, comment='CPU使用率')
    memory_usage = db.Column(db.Float, comment='内存使用率')
    memory_info = db.Column(db.Text, comment='详细内存信息JSON')
    disk_info = db.Column(db.Text, comment='磁盘信息JSON')
    system_info = db.Column(db.Text, comment='系统信息JSON')
    alert_info = db.Column(db.Text, comment='告警信息JSON')
    error_message = db.Column(db.Text, comment='错误信息')
    execution_time = db.Column(db.Float, comment='执行耗时(秒)')
    
    def get_disk_info(self):
        if self.disk_info:
            return json.loads(self.disk_info)
        return []
    
    def set_disk_info(self, disk_data):
        self.disk_info = json.dumps(disk_data)
    
    def get_memory_info(self):
        if self.memory_info:
            return json.loads(self.memory_info)
        return {}
    
    def set_memory_info(self, memory_data):
        self.memory_info = json.dumps(memory_data)
    
    def get_system_info(self):
        if self.system_info:
            return json.loads(self.system_info)
        return {}
    
    def set_system_info(self, system_data):
        self.system_info = json.dumps(system_data)
    
    def get_alert_info(self):
        if self.alert_info:
            return json.loads(self.alert_info)
        return []
    
    def set_alert_info(self, alert_data):
        self.alert_info = json.dumps(alert_data)
    
    def to_dict(self):
        return {
            'id': self.id,
            'server_id': self.server_id,
            'server_name': self.server.name if self.server else None,
            'server_ip': self.server.host if self.server else None,
            'monitor_time': self.monitor_time.isoformat() if self.monitor_time else None,
            'status': self.status,
            'cpu_usage': self.cpu_usage,
            'memory_usage': self.memory_usage,
            'memory_info': self.get_memory_info(),
            'disk_info': self.get_disk_info(),
            'system_info': self.get_system_info(),
            'alert_info': self.get_alert_info(),
            'error_message': self.error_message,
            'execution_time': self.execution_time
        }

class MonitorReport(db.Model):
    """监控报告表"""
    __tablename__ = 'monitor_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    report_name = db.Column(db.String(200), nullable=False, comment='报告名称')
    report_type = db.Column(db.String(20), default='scheduled', comment='报告类型: scheduled/manual')
    report_path = db.Column(db.String(500), comment='报告文件路径')
    server_count = db.Column(db.Integer, default=0, comment='服务器数量')
    success_count = db.Column(db.Integer, default=0, comment='成功数量')
    failed_count = db.Column(db.Integer, default=0, comment='失败数量')
    warning_count = db.Column(db.Integer, default=0, comment='告警数量')
    created_at = db.Column(db.DateTime, default=get_local_time)
    
    def to_dict(self):
        return {
            'id': self.id,
            'report_name': self.report_name,
            'report_type': self.report_type,
            'report_path': self.report_path,
            'server_count': self.server_count,
            'success_count': self.success_count,
            'failed_count': self.failed_count,
            'warning_count': self.warning_count,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class AdminUser(db.Model):
    """管理员账户表"""
    __tablename__ = 'admin_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False, comment='用户名')
    password_hash = db.Column(db.String(128), nullable=False, comment='密码哈希')
    salt = db.Column(db.String(32), nullable=False, comment='盐值')
    is_active = db.Column(db.Boolean, default=True, comment='是否激活')
    last_login = db.Column(db.DateTime, comment='最后登录时间')
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    
    def set_password(self, password):
        """设置密码"""
        self.salt = secrets.token_hex(16)
        self.password_hash = hashlib.sha256((password + self.salt).encode()).hexdigest()
    
    def check_password(self, password):
        """验证密码"""
        return self.password_hash == hashlib.sha256((password + self.salt).encode()).hexdigest()
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'is_active': self.is_active,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class NotificationChannel(db.Model):
    """通知通道表"""
    __tablename__ = 'notification_channels'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='通道名称')
    webhook_url = db.Column(db.String(500), nullable=False, comment='Webhook URL')
    method = db.Column(db.String(10), default='POST', comment='请求方式: GET/POST')
    request_body = db.Column(db.Text, comment='请求体模板(JSON格式)')
    # content_template字段已移除，用户可直接在请求体模板中使用变量
    is_enabled = db.Column(db.Boolean, default=True, comment='是否启用')
    timeout = db.Column(db.Integer, default=30, comment='超时时间(秒)')
    
    # OSS配置已移至全局配置表 oss_config
    
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    
    def get_request_body_template(self):
        """获取请求体模板"""
        if self.request_body:
            try:
                return json.loads(self.request_body)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_request_body_template(self, template):
        """设置请求体模板"""
        if isinstance(template, dict):
            self.request_body = json.dumps(template, ensure_ascii=False)
        else:
            self.request_body = template
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'webhook_url': self.webhook_url,
            'method': self.method,
            'request_body': self.request_body,
            # content_template字段已移除
            'is_enabled': self.is_enabled,
            'timeout': self.timeout,
            # OSS配置已移至全局配置表
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ServiceConfig(db.Model):
    """服务配置表"""
    __tablename__ = 'service_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('servers.id'), nullable=False)
    service_name = db.Column(db.String(100), nullable=False, comment='服务名称')
    process_name = db.Column(db.String(100), nullable=False, comment='进程名称')
    is_monitoring = db.Column(db.Boolean, default=True, comment='是否监控')
    description = db.Column(db.Text, comment='服务描述')
    last_monitor_time = db.Column(db.DateTime, comment='最新监控时间')
    first_error_time = db.Column(db.DateTime, comment='首次异常时间')
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    
    # 关联关系
    service_logs = db.relationship('ServiceMonitorLog', backref='service_config', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'server_id': self.server_id,
            'server_name': self.server.name if self.server else None,
            'service_name': self.service_name,
            'process_name': self.process_name,
            'is_monitoring': self.is_monitoring,
            'description': self.description,
            'last_monitor_time': self.last_monitor_time.isoformat() if self.last_monitor_time else None,
            'first_error_time': self.first_error_time.isoformat() if self.first_error_time else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ServiceMonitorLog(db.Model):
    """服务监控日志表"""
    __tablename__ = 'service_monitor_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    service_config_id = db.Column(db.Integer, db.ForeignKey('service_configs.id'), nullable=False)
    monitor_time = db.Column(db.DateTime, default=get_local_time, comment='监控时间')
    status = db.Column(db.String(20), comment='服务状态: running/stopped/error')
    process_count = db.Column(db.Integer, default=0, comment='进程数量')
    process_info = db.Column(db.Text, comment='进程信息JSON')
    error_message = db.Column(db.Text, comment='错误信息')
    
    def get_process_info(self):
        if self.process_info:
            return json.loads(self.process_info)
        return []
    
    def set_process_info(self, process_data):
        self.process_info = json.dumps(process_data, ensure_ascii=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'service_config_id': self.service_config_id,
            'service_name': self.service_config.service_name if self.service_config else None,
            'server_name': self.service_config.server.name if self.service_config and self.service_config.server else None,
            'monitor_time': self.monitor_time.isoformat() if self.monitor_time else None,
            'status': self.status,
            'process_count': self.process_count,
            'process_info': self.get_process_info(),
            'error_message': self.error_message
        }

class OSSConfig(db.Model):
    """OSS全局配置表"""
    __tablename__ = 'oss_config'
    
    id = db.Column(db.Integer, primary_key=True)
    is_enabled = db.Column(db.Boolean, default=False, comment='是否启用OSS上传')
    endpoint = db.Column(db.String(200), comment='OSS Endpoint')
    access_key_id = db.Column(db.String(100), comment='OSS Access Key ID')
    access_key_secret = db.Column(db.String(100), comment='OSS Access Key Secret')
    bucket_name = db.Column(db.String(100), comment='OSS Bucket名称')
    folder_path = db.Column(db.String(200), comment='OSS存储文件夹路径')
    expires_in_hours = db.Column(db.Integer, default=24, comment='OSS报告下载链接有效期(小时)')
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    
    def to_dict(self):
        return {
            'id': self.id,
            'is_enabled': self.is_enabled,
            'endpoint': self.endpoint,
            'access_key_id': self.access_key_id,
            'access_key_secret': self.access_key_secret,
            'bucket_name': self.bucket_name,
            'folder_path': self.folder_path,
            'expires_in_hours': self.expires_in_hours,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class GlobalSettings(db.Model):
    """全局设置表"""
    __tablename__ = 'global_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False, comment='设置键')
    setting_value = db.Column(db.Text, comment='设置值')
    description = db.Column(db.String(200), comment='设置描述')
    created_at = db.Column(db.DateTime, default=get_local_time)
    updated_at = db.Column(db.DateTime, default=get_local_time, onupdate=get_local_time)
    
    def to_dict(self):
        return {
            'id': self.id,
            'setting_key': self.setting_key,
            'setting_value': self.setting_value,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }