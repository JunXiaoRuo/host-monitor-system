"""Portable JSON backups for the configuration managed in the web UI."""

import base64
import io
import json
import logging
import math
from datetime import datetime
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken
from flask import jsonify, request, send_file
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Session

from app.models import (
    db, Server, ServiceConfig, ScheduleTask, Threshold, NotificationChannel,
    OSSConfig, GlobalSettings,
)
from app.sqlite_utils import run_sqlite_write

logger = logging.getLogger(__name__)
BACKUP_FORMAT = 'host-monitor-system.config'
BACKUP_VERSION = 1
MAX_BACKUP_BYTES = 10 * 1024 * 1024

# Explicit allowlists keep credentials and runtime state out of accidental exports.
SECTIONS = {
    'servers': (Server, ('name', 'host', 'port', 'username', 'private_key_path', 'description', 'status')),
    'services': (ServiceConfig, ('service_name', 'process_name', 'is_monitoring', 'description', 'start_command', 'auto_restart')),
    'schedules': (ScheduleTask, ('name', 'task_type', 'is_active')),
    'thresholds': (Threshold, ('cpu_threshold', 'memory_threshold', 'disk_threshold', 'inode_threshold', 'password_expiry_days')),
    'notifications': (NotificationChannel, ('name', 'webhook_url', 'method', 'request_body', 'is_enabled', 'timeout')),
    'oss': (OSSConfig, ('is_enabled', 'endpoint', 'access_key_id', 'access_key_secret', 'bucket_name', 'folder_path', 'expires_in_hours')),
    'global_settings': (GlobalSettings, ('setting_key', 'setting_value', 'description')),
}
LABELS = dict(zip(SECTIONS, ('服务器', '服务', '计划任务', '告警阈值', '通知通道', 'OSS', '全局设置')))
SINGLETONS = {'thresholds', 'oss'}


class ConfigValidationError(ValueError):
    pass


class ConfigTransferService:
    def __init__(self, server_service, scheduler_service, service_monitor_service):
        self.server_service = server_service
        self.scheduler_service = scheduler_service
        self.service_monitor_service = service_monitor_service

    def export_config(self, include_passwords=False):
        config = {}
        with Session(db.engine) as session:
            for section, (model, fields) in SECTIONS.items():
                rows = session.query(model).order_by(model.id).all()
                records = []
                for row in rows:
                    record = {field: getattr(row, field) for field in fields}
                    if section == 'servers':
                        record['id'] = row.id
                        if include_passwords:
                            record['password'] = self._export_password(row.password)
                    elif section == 'services':
                        record['server_id'] = row.server_id
                    elif section == 'schedules':
                        record['schedule_config'] = row.get_schedule_config()
                    records.append(record)
                config[section] = (records[0] if records else None) if section in SINGLETONS else records
        return {
            'format': BACKUP_FORMAT,
            'version': BACKUP_VERSION,
            'exported_at': datetime.now().astimezone().isoformat(),
            'includes_server_passwords': include_passwords,
            'config': config,
        }

    def _export_password(self, stored):
        if not stored:
            return ''
        try:
            return Fernet(self.server_service.cipher_key).decrypt(
                base64.b64decode(stored)
            ).decode('utf-8')
        except (InvalidToken, ValueError, UnicodeError):
            raise ConfigValidationError('服务器密码无法解密，请检查本机 ENCRYPTION_KEY 后再导出密码') from None

    def validate(self, payload):
        if not isinstance(payload, dict) or payload.get('format') != BACKUP_FORMAT:
            raise ConfigValidationError('请选择本系统导出的 JSON 配置文件')
        if type(payload.get('version')) is not int or payload['version'] != BACKUP_VERSION:
            raise ConfigValidationError('配置文件版本不受支持')
        includes_passwords = payload.get('includes_server_passwords')
        if type(includes_passwords) is not bool:
            raise ConfigValidationError('配置文件缺少有效的密码导出标记')
        config = payload.get('config')
        if not isinstance(config, dict) or set(config) != set(SECTIONS):
            raise ConfigValidationError('配置分组不完整或包含不支持的分组')

        normalized = {}
        source_ids = set()
        for section, (model, fields) in SECTIONS.items():
            entries = config[section]
            if section in SINGLETONS:
                entries = [] if entries is None else [entries]
            if not isinstance(entries, list):
                raise ConfigValidationError(f'{LABELS[section]}必须是列表')
            normalized[section] = []
            identities = set()
            names = set()
            for index, entry in enumerate(entries, 1):
                label = f'{LABELS[section]}第 {index} 项'
                if not isinstance(entry, dict):
                    raise ConfigValidationError(f'{label}格式错误')
                allowed = set(fields)
                if section == 'servers':
                    allowed.update(('id', 'password'))
                elif section == 'services':
                    allowed.add('server_id')
                elif section == 'schedules':
                    allowed.add('schedule_config')
                if set(entry) - allowed:
                    raise ConfigValidationError(f'{label}包含不支持的字段')
                if not set(fields).issubset(entry):
                    raise ConfigValidationError(f'{label}缺少配置字段')
                record = {}
                for field in fields:
                    value = entry[field]
                    column = model.__table__.columns[field]
                    if value is None:
                        if not column.nullable:
                            raise ConfigValidationError(f'{label}的 {field} 不能为空')
                    elif isinstance(column.type, Boolean):
                        if type(value) is not bool:
                            raise ConfigValidationError(f'{label}的 {field} 必须是布尔值')
                    elif isinstance(column.type, Integer):
                        if type(value) is not int:
                            raise ConfigValidationError(f'{label}的 {field} 必须是整数')
                    elif isinstance(column.type, Float):
                        if type(value) not in (int, float) or not math.isfinite(value):
                            raise ConfigValidationError(f'{label}的 {field} 必须是有限数值')
                    elif isinstance(column.type, String):
                        if not isinstance(value, str) or (column.type.length and len(value) > column.type.length):
                            raise ConfigValidationError(f'{label}的 {field} 类型或长度不正确')
                        if not column.nullable and not value.strip():
                            raise ConfigValidationError(f'{label}的 {field} 不能为空')
                    record[field] = value

                if section == 'servers':
                    source_id = entry.get('id')
                    if type(source_id) is not int or source_id < 1 or source_id in source_ids:
                        raise ConfigValidationError(f'{label}的来源 ID 缺失或重复')
                    source_ids.add(source_id)
                    record['id'] = source_id
                    self._range(record, 'port', 1, 65535, label)
                    if record['status'] not in ('active', 'inactive'):
                        raise ConfigValidationError(f'{label}的状态无效')
                    if includes_passwords:
                        if not isinstance(entry.get('password'), str):
                            raise ConfigValidationError(f'{label}缺少有效的密码字段')
                        record['password'] = entry['password']
                    elif 'password' in entry:
                        raise ConfigValidationError(f'{label}的密码字段与导出标记不一致')
                    identity = (record['host'], record['port'])
                    if record['name'] in names:
                        raise ConfigValidationError('配置文件中服务器名称重复')
                    names.add(record['name'])
                elif section == 'services':
                    source_id = entry.get('server_id')
                    if type(source_id) is not int or source_id not in source_ids:
                        raise ConfigValidationError(f'{label}引用的服务器不在配置文件中')
                    record['server_id'] = source_id
                    identity = (source_id, record['service_name'])
                elif section == 'schedules':
                    schedule = entry.get('schedule_config')
                    if not isinstance(schedule, dict) or not self.scheduler_service._validate_schedule_config(record['task_type'], schedule):
                        raise ConfigValidationError(f'{label}的调度配置无效')
                    if self.scheduler_service._create_trigger(record['task_type'], schedule) is None:
                        raise ConfigValidationError(f'{label}的调度表达式无效')
                    record['schedule_config'] = schedule
                    identity = record['name']
                elif section == 'thresholds':
                    for field in fields[:-1]:
                        self._range(record, field, 0, 100, label)
                    self._range(record, 'password_expiry_days', 1, 365, label)
                    identity = section
                elif section == 'notifications':
                    parsed_url = urlsplit(record['webhook_url'])
                    if parsed_url.scheme not in ('http', 'https') or not parsed_url.netloc:
                        raise ConfigValidationError(f'{label}的 Webhook URL 无效')
                    if record['method'] not in ('GET', 'POST'):
                        raise ConfigValidationError(f'{label}的请求方式无效')
                    self._range(record, 'timeout', 1, 3600, label)
                    identity = (record['name'], record['webhook_url'])
                elif section == 'oss':
                    self._range(record, 'expires_in_hours', 1, 168, label)
                    if record['is_enabled'] and not all(record[field] for field in ('endpoint', 'access_key_id', 'access_key_secret', 'bucket_name')):
                        raise ConfigValidationError(f'{label}缺少启用 OSS 所需的凭据')
                    identity = section
                else:
                    for key, low, high in (('service_monitor_interval', 1, 1440), ('restart_cooldown', 60, 86400)):
                        if record['setting_key'] == key:
                            try:
                                number = int(record['setting_value'])
                            except (TypeError, ValueError):
                                raise ConfigValidationError(f'{label}的设置值必须是整数') from None
                            if not low <= number <= high:
                                raise ConfigValidationError(f'{label}的设置值超出范围')
                    identity = record['setting_key']
                if identity in identities:
                    raise ConfigValidationError(f'{label}与前面的配置重复')
                identities.add(identity)
                normalized[section].append(record)
        return normalized

    @staticmethod
    def _range(record, field, low, high, label):
        value = record[field]
        if value is None or not low <= value <= high:
            raise ConfigValidationError(f'{label}的 {field} 必须在 {low} 到 {high} 之间')

    @staticmethod
    def _one(query, label):
        matches = query.limit(2).all()
        if len(matches) > 1:
            raise ConfigValidationError(f'本机{label}存在多个匹配项，请先处理重复配置')
        return matches[0] if matches else None

    def _build_plan(self, session, config):
        plan = {section: [] for section in SECTIONS}
        servers = {}
        for section, (model, fields) in SECTIONS.items():
            for record in config[section]:
                query = session.query(model)
                if section == 'servers':
                    by_name = self._one(query.filter_by(name=record['name']), LABELS[section])
                    row = self._one(query.filter_by(host=record['host'], port=record['port']), LABELS[section])
                    if by_name is not None and by_name is not row:
                        raise ConfigValidationError('服务器名称与本机其他主机冲突，请先修改名称或地址')
                    servers[record['id']] = row
                elif section == 'services':
                    server = servers[record['server_id']]
                    row = None if server is None else self._one(
                        query.filter_by(server_id=server.id, service_name=record['service_name']), LABELS[section]
                    )
                elif section == 'global_settings':
                    row = self._one(query.filter_by(setting_key=record['setting_key']), LABELS[section])
                elif section == 'notifications':
                    row = self._one(query.filter_by(name=record['name'], webhook_url=record['webhook_url']), LABELS[section])
                elif section == 'schedules':
                    row = self._one(query.filter_by(name=record['name']), LABELS[section])
                else:
                    row = query.order_by(model.id).first()
                plan[section].append((row, record))
        return plan

    @staticmethod
    def _summary(plan):
        return {
            'sections': {
                section: {
                    'label': LABELS[section],
                    'created': sum(row is None for row, _ in entries),
                    'updated': sum(row is not None for row, _ in entries),
                } for section, entries in plan.items()
            },
            'servers_without_password': sum(
                row is None and not record.get('password') and not record.get('private_key_path')
                for row, record in plan['servers']
            ),
        }

    def preview(self, payload):
        config = self.validate(payload)
        with Session(db.engine) as session:
            return self._summary(self._build_plan(session, config))

    def import_config(self, payload):
        config = self.validate(payload)

        def apply():
            session = db.session
            plan = self._build_plan(session, config)
            summary = self._summary(plan)
            servers = {}
            task_ids = []
            for section, (model, fields) in SECTIONS.items():
                for row, record in plan[section]:
                    if row is None:
                        row = model()
                        session.add(row)
                    for field in fields:
                        setattr(row, field, record[field])
                    if section == 'servers':
                        if 'password' in record:
                            password = record['password']
                            row.password = base64.b64encode(
                                Fernet(self.server_service.cipher_key).encrypt(password.encode('utf-8'))
                            ).decode('ascii') if password else ''
                        session.flush()
                        servers[record['id']] = row.id
                    elif section == 'services':
                        row.server_id = servers[record['server_id']]
                    elif section == 'schedules':
                        row.set_schedule_config(record['schedule_config'])
                        row.next_run = None
                        session.flush()
                        task_ids.append(row.id)
                session.flush()
            session.commit()
            return summary, task_ids

        summary, task_ids = run_sqlite_write(apply)
        settings_changed = any(
            record['setting_key'] in ('service_monitor_interval', 'restart_cooldown')
            for record in config['global_settings']
        )
        summary['warnings'] = self._sync_runtime(task_ids, settings_changed)
        return summary

    def _sync_runtime(self, task_ids, settings_changed):
        warnings = []
        scheduler = self.scheduler_service.scheduler
        if task_ids and (scheduler is None or not scheduler.running):
            warnings.append('配置已保存，计划任务将在应用重启后载入')
        elif task_ids:
            # The authenticated request may already hold an older read transaction.
            db.session.rollback()
            try:
                for task_id in task_ids:
                    task = db.session.get(ScheduleTask, task_id)
                    if task.is_active:
                        self.scheduler_service._add_job_to_scheduler(task)
                    elif scheduler.get_job(f'task_{task_id}'):
                        scheduler.remove_job(f'task_{task_id}')
            except Exception as error:
                db.session.rollback()
                logger.error('配置导入后的计划任务同步失败: %s', type(error).__name__)
                warnings.append('配置已保存，部分计划任务未能立即生效，请重启应用')
        if settings_changed and self.service_monitor_service._is_monitoring:
            success, _ = self.service_monitor_service.restart_monitor_loop()
            if not success:
                warnings.append('配置已保存，服务监控设置将在应用重启后生效')
        return warnings


def register_config_transfer_routes(app, login_required, server_service, scheduler_service, service_monitor_service):
    service = ConfigTransferService(server_service, scheduler_service, service_monitor_service)

    @app.route('/api/config/export', methods=['POST'])
    @login_required
    def export_configuration():
        options = request.get_json(silent=True)
        if not isinstance(options, dict) or type(options.get('include_server_passwords', False)) is not bool:
            return jsonify(success=False, message='密码导出选项必须是布尔值'), 400
        try:
            payload = service.export_config(options.get('include_server_passwords', False))
            content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')
            response = send_file(
                io.BytesIO(content), mimetype='application/json', as_attachment=True,
                download_name=f'host-monitor-config-{datetime.now():%Y%m%d-%H%M%S}.json',
            )
            response.headers['Cache-Control'] = 'no-store'
            response.headers['Pragma'] = 'no-cache'
            return response
        except ConfigValidationError as error:
            return jsonify(success=False, message=str(error)), 400
        except Exception as error:
            logger.error('导出配置失败: %s', type(error).__name__)
            return jsonify(success=False, message='导出配置失败，请查看系统日志'), 500

    @app.route('/api/config/import', methods=['POST'])
    @login_required
    def import_configuration():
        upload = request.files.get('file')
        if upload is None or not isinstance(upload.filename, str) or not upload.filename.lower().endswith('.json'):
            return jsonify(success=False, message='请选择 JSON 配置文件'), 400
        if request.form.get('preview') not in ('true', 'false'):
            return jsonify(success=False, message='请指定预览或导入操作'), 400
        raw = upload.stream.read(MAX_BACKUP_BYTES + 1)
        if len(raw) > MAX_BACKUP_BYTES:
            return jsonify(success=False, message='配置文件不能超过 10 MB'), 400
        try:
            def reject_constant(value):
                raise ValueError('Non-finite JSON number')

            payload = json.loads(raw.decode('utf-8-sig'), parse_constant=reject_constant)
        except (ValueError, UnicodeError, RecursionError):
            return jsonify(success=False, message='文件不是有效的 UTF-8 JSON'), 400
        try:
            preview = request.form['preview'] == 'true'
            result = service.preview(payload) if preview else service.import_config(payload)
            return jsonify(success=True, message='配置校验通过' if preview else '配置导入成功', data=result)
        except ConfigValidationError as error:
            return jsonify(success=False, message=str(error)), 400
        except Exception as error:
            logger.error('导入配置失败: %s', type(error).__name__)
            return jsonify(success=False, message='导入配置失败，本次配置未保存，请查看系统日志'), 500
