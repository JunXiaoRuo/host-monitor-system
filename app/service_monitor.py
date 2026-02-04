"""
服务监控模块
负责服务进程的监控和管理
"""

import logging
import re
import threading
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import func
from app.models import db, Server, ServiceConfig, ServiceMonitorLog, GlobalSettings
from app.ssh_manager import SSHConnectionManager
from app.services import ServerService
from app.notification_service import NotificationService
from app.ssh_pool_health_checker import SSHPoolHealthChecker

logger = logging.getLogger(__name__)

class ServiceMonitorService:
    """服务监控服务类"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls, app=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, app=None):
        # 防止重复初始化
        if self._initialized:
            if app and not self.app:
                self.app = app  # 更新app引用但不重复初始化
            return
            
        # 使用HostMonitor的全局共享SSH连接管理器
        from app.monitor import HostMonitor
        if HostMonitor._shared_ssh_manager is None:
            # 获取配置文件中的参数，而不是使用硬编码值
            from app.ssh_pool_config import ssh_pool_config_manager
            config = ssh_pool_config_manager.get_config()
            
            HostMonitor._shared_ssh_manager = SSHConnectionManager(
                timeout=config.command_timeout,
                connect_timeout=config.connect_timeout,
                use_pool=True,
                max_connections_per_server=config.max_connections_per_server,
                max_idle_time=config.max_idle_time
            )
            logger.info(f"创建全局SSH连接管理器，连接池已启用，max_idle_time={config.max_idle_time}秒")
        self.ssh_manager = HostMonitor._shared_ssh_manager
        
        # 初始化健康检查器
        self.health_checker = SSHPoolHealthChecker(self.ssh_manager)
        
        logger.info("服务监控服务已初始化，SSH连接池已启用")
        self.server_service = ServerService()
        self.notification_service = NotificationService()
        self._monitor_thread = None
        self._stop_monitor = False
        self._is_monitoring = False
        self._current_interval = 10  # 当前监控间隔
        self._restart_requested = False  # 重启请求标志
        self.app = app
        self._initialized = True
        
        logger.info("ServiceMonitorService 初始化完成（单例模式），SSH连接池已启用")
    
    def create_service_config(self, data: Dict[str, Any]) -> Tuple[bool, str, Optional[ServiceConfig]]:
        """
        创建服务配置
        
        Args:
            data: 服务配置数据
            
        Returns:
            (success, message, service_config)
        """
        try:
            # 验证必填字段
            if not data.get('server_id'):
                return False, "服务器ID不能为空", None
            
            if not data.get('service_name'):
                return False, "服务名称不能为空", None
            
            if not data.get('process_name'):
                return False, "进程名称不能为空", None
            
            # 验证服务器是否存在
            server = Server.query.get(data['server_id'])
            if not server:
                return False, "服务器不存在", None
            
            # 检查同一服务器下是否已存在相同的服务名称
            existing_service = ServiceConfig.query.filter_by(
                server_id=data['server_id'],
                service_name=data['service_name']
            ).first()
            if existing_service:
                return False, "该服务器下已存在相同名称的服务", None
            
            # 创建服务配置
            service_config = ServiceConfig(
                server_id=data['server_id'],
                service_name=data['service_name'],
                process_name=data['process_name'],
                is_monitoring=data.get('is_monitoring', True),
                start_command=data.get('start_command', ''),
                auto_restart=data.get('auto_restart', False),
                description=data.get('description', '')
            )
            
            db.session.add(service_config)
            db.session.commit()
            
            logger.info(f"创建服务配置成功: {service_config.service_name}")
            return True, "服务配置创建成功", service_config
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"创建服务配置失败: {str(e)}")
            return False, f"创建服务配置失败: {str(e)}", None
    
    def update_service_config(self, service_id: int, data: Dict[str, Any]) -> Tuple[bool, str, Optional[ServiceConfig]]:
        """
        更新服务配置
        
        Args:
            service_id: 服务ID
            data: 更新数据
            
        Returns:
            (success, message, service_config)
        """
        try:
            service_config = ServiceConfig.query.get(service_id)
            if not service_config:
                return False, "服务配置不存在", None
            
            # 检查服务名称冲突（如果修改了服务名称）
            if 'service_name' in data and data['service_name'] != service_config.service_name:
                existing_service = ServiceConfig.query.filter_by(
                    server_id=service_config.server_id,
                    service_name=data['service_name']
                ).first()
                if existing_service:
                    return False, "该服务器下已存在相同名称的服务", None
            
            # 更新字段
            if 'service_name' in data:
                service_config.service_name = data['service_name']
            if 'process_name' in data:
                service_config.process_name = data['process_name']
            if 'is_monitoring' in data:
                service_config.is_monitoring = data['is_monitoring']
            if 'start_command' in data:
                service_config.start_command = data['start_command']
            if 'auto_restart' in data:
                service_config.auto_restart = data['auto_restart']
            if 'description' in data:
                service_config.description = data['description']
            
            db.session.commit()
            
            logger.info(f"更新服务配置成功: {service_config.service_name}")
            return True, "服务配置更新成功", service_config
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"更新服务配置失败: {str(e)}")
            return False, f"更新服务配置失败: {str(e)}", None
    
    def delete_service_config(self, service_id: int) -> Tuple[bool, str]:
        """
        删除服务配置
        
        Args:
            service_id: 服务ID
            
        Returns:
            (success, message)
        """
        try:
            service_config = ServiceConfig.query.get(service_id)
            if not service_config:
                return False, "服务配置不存在"

            service_name = service_config.service_name

            # 先批量删除监控日志，避免 ORM 级联逐条处理
            ServiceMonitorLog.query.filter_by(service_config_id=service_id).delete(
                synchronize_session=False
            )

            # 再删除服务配置
            db.session.delete(service_config)
            db.session.commit()

            logger.info(f"删除服务配置成功: {service_name}")
            return True, "服务配置删除成功"

        except Exception as e:
            db.session.rollback()
            logger.error(f"删除服务配置失败: {str(e)}")
            return False, f"删除服务配置失败: {str(e)}"
    
    def get_services_by_server(self, server_id: int) -> List[Dict[str, Any]]:
        """
        获取指定服务器的服务配置列表
        
        Args:
            server_id: 服务器ID
            
        Returns:
            服务配置列表
        """
        try:
            services = ServiceConfig.query.filter_by(server_id=server_id).all()
            if not services:
                return []

            service_ids = [service.id for service in services]
            latest_times = (
                db.session.query(
                    ServiceMonitorLog.service_config_id,
                    func.max(ServiceMonitorLog.monitor_time).label('max_time')
                )
                .filter(ServiceMonitorLog.service_config_id.in_(service_ids))
                .group_by(ServiceMonitorLog.service_config_id)
                .subquery()
            )

            latest_logs = (
                db.session.query(ServiceMonitorLog)
                .join(
                    latest_times,
                    (ServiceMonitorLog.service_config_id == latest_times.c.service_config_id) &
                    (ServiceMonitorLog.monitor_time == latest_times.c.max_time)
                )
                .all()
            )
            latest_by_service_id = {log.service_config_id: log for log in latest_logs}

            result = []
            for service in services:
                service_dict = service.to_dict()
                latest_log = latest_by_service_id.get(service.id)

                if latest_log:
                    service_dict['latest_status'] = latest_log.status
                    service_dict['latest_process_count'] = latest_log.process_count
                    service_dict['latest_monitor_time'] = latest_log.monitor_time.isoformat()
                else:
                    service_dict['latest_status'] = 'unknown'
                    service_dict['latest_process_count'] = 0
                    service_dict['latest_monitor_time'] = None

                result.append(service_dict)

            return result

        except Exception as e:
            logger.error(f"获取服务配置列表失败: {str(e)}")
            return []
    
    def get_all_servers_with_services(self) -> List[Dict[str, Any]]:
        """
        获取所有服务器及其服务统计信息
        
        Returns:
            服务器列表（包含服务统计）
        """
        try:
            servers = Server.query.filter_by(status='active').all()
            result = []

            for server in servers:
                server_dict = server.to_dict()

                services_data = self.get_services_by_server(server.id)

                total_services = len(services_data)
                monitoring_services = len([s for s in services_data if s.get('is_monitoring')])

                normal_count = 0
                error_count = 0

                for service in services_data:
                    if not service.get('is_monitoring'):
                        continue

                    status = service.get('latest_status')
                    if status == 'running':
                        normal_count += 1
                    elif status in ['stopped', 'error', 'connection_failed']:
                        error_count += 1

                server_dict.update({
                    'total_services': total_services,
                    'monitoring_services': monitoring_services,
                    'normal_services': normal_count,
                    'error_services': error_count,
                    'services': services_data
                })

                result.append(server_dict)

            return result

        except Exception as e:
            logger.error(f"获取服务器服务统计失败: {str(e)}")
            return []
    
    def monitor_single_service(self, service_id: int) -> Dict[str, Any]:
        """
        监控单个服务
        
        Args:
            service_id: 服务ID
            
        Returns:
            监控结果
        """
        try:
            service_config = ServiceConfig.query.get(service_id)
            if not service_config:
                return {'success': False, 'message': '服务配置不存在'}
            
            if not service_config.is_monitoring:
                return {'success': False, 'message': '该服务未启用监控'}
            
            server = service_config.server
            if not server:
                return {'success': False, 'message': '服务器不存在'}
            
            # 建立SSH连接
            password = self.server_service._decrypt_password(server.password) if server.password else None
            
            with self.ssh_manager.get_connection(
                host=server.host,
                port=server.port,
                username=server.username,
                password=password,
                private_key_path=server.private_key_path if server.private_key_path else None
            ) as client:
                
                # 监控服务
                service_result = self._monitor_single_service(client, service_config)
                
                # 保存监控结果
                self._save_service_monitor_result(service_result)
            
            status_text = '正常' if service_result['status'] == 'running' else '异常'
            message = f"服务 {service_config.service_name} 监控完成，状态: {status_text}"
            
            logger.info(f"服务 {service_config.service_name} 单个监控完成，状态: {service_result['status']}")
            
            return {
                'success': True, 
                'message': message,
                'result': service_result
            }
            
        except Exception as e:
            logger.error(f"监控单个服务 {service_id} 失败: {str(e)}")
            return {'success': False, 'message': f'监控失败: {str(e)}'}

    def monitor_server_services(self, server_id: int) -> Dict[str, Any]:
        """
        监控指定服务器的所有服务
        
        Args:
            server_id: 服务器ID
            
        Returns:
            监控结果
        """
        try:
            server = Server.query.get(server_id)
            if not server:
                return {'success': False, 'message': '服务器不存在'}
            
            # 获取该服务器需要监控的服务
            services = ServiceConfig.query.filter_by(
                server_id=server_id,
                is_monitoring=True
            ).all()
            
            if not services:
                return {'success': True, 'message': '没有需要监控的服务', 'results': []}
            
            # 添加监控开始的日志
            logger.info(f"开始监控服务器 {server.name}，共 {len(services)} 个服务")
            
            results = []
            
            # 建立SSH连接
            password = self.server_service._decrypt_password(server.password) if server.password else None
            
            with self.ssh_manager.get_connection(
                host=server.host,
                port=server.port,
                username=server.username,
                password=password,
                private_key_path=server.private_key_path if server.private_key_path else None
            ) as client:
                
                for service in services:
                    service_result = self._monitor_single_service(client, service)
                    results.append(service_result)
                    
                    # 保存监控结果
                    self._save_service_monitor_result(service_result)
            
            logger.info(f"服务器 {server.name} 服务监控完成，监控了 {len(services)} 个服务")
            return {'success': True, 'message': '监控完成', 'results': results}
            
        except Exception as e:
            logger.error(f"监控服务器 {server_id} 的服务失败: {str(e)}")
            
            # SSH连接失败时，为每个服务创建连接失败的监控记录
            services = ServiceConfig.query.filter_by(
                server_id=server_id,
                is_monitoring=True
            ).all()
            
            results = []
            for service in services:
                # 创建连接失败的监控结果
                connection_failed_result = {
                    'service_id': service.id,
                    'service_name': service.service_name,
                    'server_name': server.name,
                    'status': 'connection_failed',
                    'process_count': 0,
                    'process_info': [],
                    'error_message': f'SSH连接失败: {str(e)}',
                    'monitor_time': datetime.now().isoformat()
                }
                results.append(connection_failed_result)
                
                # 保存监控结果到数据库
                self._save_service_monitor_result(connection_failed_result)
            
            return {'success': False, 'message': f'监控失败: {str(e)}', 'results': results}
    
    def _monitor_single_service(self, ssh_client, service_config: ServiceConfig) -> Dict[str, Any]:
        """
        监控单个服务
        
        Args:
            ssh_client: SSH客户端
            service_config: 服务配置
            
        Returns:
            监控结果
        """
        result = {
            'service_id': service_config.id,
            'service_name': service_config.service_name,
            'process_name': service_config.process_name,
            'server_name': service_config.server.name,
            'status': 'error',
            'process_count': 0,
            'process_info': [],
            'error_message': ''
        }
        
        try:
            # 使用ps命令查找进程，显式使用/bin/sh来避免shell兼容性问题
            cmd = f"/bin/sh -c \"ps aux | grep '{service_config.process_name}' | grep -v grep\""
            logger.info(f"执行命令: {cmd}")
            
            # 使用SSH管理器的execute_command方法，获得重试机制和更好的错误处理
            cmd_result = self.ssh_manager.execute_command(ssh_client, cmd)
            
            # 对于grep命令，退出码1表示没有找到匹配项，这是正常情况
            if not cmd_result['success'] and cmd_result['exit_code'] != 1:
                result['status'] = 'error'
                result['error_message'] = cmd_result['stderr'] or f"命令执行失败，退出码: {cmd_result['exit_code']}"
                logger.error(f"SSH命令执行失败: {result['error_message']}")
                return result
            elif cmd_result['exit_code'] == 1:
                logger.info(f"grep命令未找到匹配进程（退出码1），这是正常情况")
            
            # 获取命令输出
            output = cmd_result['stdout'].strip()
            error = cmd_result['stderr'].strip()
            
            logger.info(f"命令执行成功，耗时: {cmd_result['execution_time']:.2f}秒")
            logger.info(f"输出内容: {repr(output)}")
            if error:
                logger.warning(f"命令执行错误: {repr(error)}")
            
            if error:
                # 检查是否是shell配置文件的非关键错误
                non_critical_errors = [
                    'then: then/endif not found',
                    'if: Expression Syntax',
                    'Badly placed ()',
                    ': not found',
                    ': Undefined variable',  # 环境变量未定义
                    'LINX_PTS: Undefined variable',  # 特定的环境变量错误
                    'No such file or directory',  # 配置文件不存在（部分情况）
                    'Permission denied'  # 权限问题（部分情况）
                ]
                
                is_critical_error = True
                for non_critical in non_critical_errors:
                    if non_critical in error:
                        is_critical_error = False
                        logger.warning(f"检测到非关键shell错误（已忽略）: {error}")
                        break
                
                # 如果是关键错误，则报错
                if is_critical_error:
                    result['status'] = 'error'
                    result['error_message'] = error
                    logger.error(f"SSH命令执行出错: {error}")
                    return result
                else:
                    logger.info(f"忽略非关键错误，继续处理输出（可能为空）")
                    # 清除错误信息，避免后续处理中误判
                    error = None
            
            logger.info(f"命令输出为空: {not output}，输出长度: {len(output) if output else 0}")
            logger.info(f"输出内容: {repr(output)}")
            
            # 解析进程信息
            processes = []
            if output:
                lines = output.split('\n')
                logger.info(f"输出分割成 {len(lines)} 行")
                for i, line in enumerate(lines):
                    logger.info(f"第{i+1}行: {repr(line)}")
                    if line.strip():
                        # 解析ps输出
                        parts = line.split(None, 10)
                        logger.info(f"分割结果: {parts}, 长度: {len(parts)}")
                        if len(parts) >= 11:
                            process_info = {
                                'pid': parts[1],
                                'cpu': parts[2],
                                'memory': parts[3],
                                'command': parts[10]
                            }
                            processes.append(process_info)
                            logger.info(f"添加进程信息: {process_info}")
                        else:
                            logger.warning(f"行格式不正确，字段数量不足: {len(parts)}")
            
            result['process_count'] = len(processes)
            result['process_info'] = processes
            
            logger.info(f"最终统计: 找到 {len(processes)} 个进程")
            
            if len(processes) > 0:
                result['status'] = 'running'
                # 根据实际配置显示自启动状态
                if service_config.auto_restart:
                    result['auto_restart_status'] = '已开启'
                else:
                    result['auto_restart_status'] = '未开启'
                logger.info(f"服务 {service_config.service_name} 状态: 运行中")
            else:
                result['status'] = 'stopped'
                logger.warning(f"服务 {service_config.service_name} 状态: 已停止 - 未找到匹配的进程")
                
                # 检查是否需要自动重启
                if service_config.auto_restart and service_config.start_command:
                    logger.info(f"服务 {service_config.service_name} 开启了自动重启，尝试执行启动命令")
                    restart_result = self._execute_restart_command(ssh_client, service_config)
                    result['restart_attempted'] = True
                    result['restart_success'] = restart_result['success']
                    result['restart_message'] = restart_result['message']
                    
                    if restart_result['success']:
                        # 等待3秒后重新检测
                        logger.info(f"启动命令执行成功，等待3秒后重新检测服务状态")
                        time.sleep(3)
                        
                        # 重新检测服务状态
                        recheck_result = self._check_service_status(ssh_client, service_config)
                        if recheck_result['success'] and recheck_result['process_count'] > 0:
                            result['status'] = 'running'
                            result['process_count'] = recheck_result['process_count']
                            result['process_info'] = recheck_result['process_info']
                            result['auto_restart_status'] = '自启动成功'
                            logger.info(f"服务 {service_config.service_name} 重启成功，当前状态: 运行中")
                        else:
                            result['auto_restart_status'] = '自启动失败'
                            logger.warning(f"服务 {service_config.service_name} 重启后仍未运行")
                    else:
                        # 重启命令执行失败（包括超时）
                        result['auto_restart_status'] = '自启动失败'
                        logger.warning(f"服务 {service_config.service_name} 重启命令执行失败: {restart_result['message']}")
                else:
                    result['restart_attempted'] = False
                    if not service_config.auto_restart:
                        result['auto_restart_status'] = '未开启'
                        logger.info(f"服务 {service_config.service_name} 未开启自动重启")
                    elif not service_config.start_command:
                        result['auto_restart_status'] = '未开启'
                        logger.warning(f"服务 {service_config.service_name} 开启了自动重启但未配置启动命令")
            
            logger.debug(f"监控服务 {service_config.service_name}: {result['status']}, 进程数: {len(processes)}")
            
        except Exception as e:
            result['status'] = 'error'
            result['error_message'] = str(e)
            logger.error(f"监控服务 {service_config.service_name} 失败: {str(e)}")
        
        return result
    
    def _execute_restart_command(self, ssh_client, service_config: ServiceConfig) -> Dict[str, Any]:
        """
        执行服务重启命令
        
        Args:
            ssh_client: SSH客户端
            service_config: 服务配置
            
        Returns:
            执行结果
        """
        try:
            logger.info(f"执行重启命令: {service_config.start_command}")
            # 确保命令在后台运行且非交互式执行
            start_cmd = service_config.start_command.strip()
            # 如果命令已经包含&，则移除它，避免重复
            if start_cmd.endswith('&'):
                start_cmd = start_cmd[:-1].strip()
            # 使用sh -c来避免重定向解析问题
            background_command = f"sh -c 'nohup {start_cmd} >/dev/null 2>&1 &'"
            logger.info(f"实际执行的后台命令: {background_command}")
            cmd_result = self.ssh_manager.execute_command(ssh_client, background_command, timeout=30)
            
            if cmd_result['success']:
                logger.info(f"重启命令执行成功，耗时: {cmd_result['execution_time']:.2f}秒")
                return {
                    'success': True,
                    'message': '启动命令执行成功',
                    'output': cmd_result['stdout'],
                    'execution_time': cmd_result['execution_time']
                }
            else:
                error_msg = cmd_result['stderr'] or f"命令执行失败，退出码: {cmd_result['exit_code']}"
                logger.error(f"重启命令执行失败: {error_msg}")
                return {
                    'success': False,
                    'message': f'启动命令执行失败: {error_msg}',
                    'output': cmd_result['stdout'],
                    'error': cmd_result['stderr']
                }
        except Exception as e:
            logger.error(f"执行重启命令异常: {str(e)}")
            return {
                'success': False,
                'message': f'执行重启命令异常: {str(e)}',
                'error': str(e)
            }
    
    def _check_service_status(self, ssh_client, service_config: ServiceConfig) -> Dict[str, Any]:
        """
        检查服务状态（用于重启后的二次检测）
        
        Args:
            ssh_client: SSH客户端
            service_config: 服务配置
            
        Returns:
            检测结果
        """
        try:
            cmd = f"/bin/sh -c \"ps aux | grep '{service_config.process_name}' | grep -v grep\""
            cmd_result = self.ssh_manager.execute_command(ssh_client, cmd)
            
            # 对于grep命令，退出码1表示没有找到匹配项
            if not cmd_result['success'] and cmd_result['exit_code'] != 1:
                return {
                    'success': False,
                    'message': f"状态检测失败: {cmd_result['stderr']}",
                    'process_count': 0,
                    'process_info': []
                }
            
            output = cmd_result['stdout'].strip()
            processes = []
            
            if output:
                lines = output.split('\n')
                for line in lines:
                    if line.strip():
                        parts = line.split(None, 10)
                        if len(parts) >= 11:
                            process_info = {
                                'pid': parts[1],
                                'cpu': parts[2],
                                'memory': parts[3],
                                'command': parts[10]
                            }
                            processes.append(process_info)
            
            return {
                'success': True,
                'process_count': len(processes),
                'process_info': processes
            }
            
        except Exception as e:
            logger.error(f"检查服务状态异常: {str(e)}")
            return {
                'success': False,
                'message': f'检查服务状态异常: {str(e)}',
                'process_count': 0,
                'process_info': []
            }
    
    def _save_service_monitor_result(self, result: Dict[str, Any]) -> Optional[ServiceMonitorLog]:
        """
        保存服务监控结果
        
        Args:
            result: 监控结果
            
        Returns:
            监控日志对象
        """
        try:
            monitor_log = ServiceMonitorLog(
                service_config_id=result['service_id'],
                status=result['status'],
                process_count=result['process_count'],
                error_message=result['error_message']
            )
            
            monitor_log.set_process_info(result['process_info'])
            
            db.session.add(monitor_log)
            
            # 更新ServiceConfig的时间字段
            service_config = ServiceConfig.query.get(result['service_id'])
            if service_config:
                # 更新最新监控时间
                service_config.last_monitor_time = datetime.now()
                
                # 处理首次异常时间
                if result['status'] in ['stopped', 'error', 'connection_failed']:
                    # 异常状态，设置首次异常时间（如果还没有的话）
                    if not service_config.first_error_time:
                        service_config.first_error_time = datetime.now()
                else:
                    # 正常状态，清除首次异常时间
                    service_config.first_error_time = None
            
            db.session.commit()
            
            return monitor_log
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"保存服务监控结果失败: {str(e)}")
            return None
    
    def monitor_all_services(self) -> Dict[str, Any]:
        """
        监控所有活跃服务器的服务
        
        Returns:
            监控汇总结果
        """
        try:
            servers = Server.query.filter_by(status='active').all()
            
            total_services = 0
            normal_services = 0
            error_services = 0
            server_results = []
            service_alerts = []
            restart_success_alerts = []  # 收集重启成功的服务
            
            for server in servers:
                server_result = self.monitor_server_services(server.id)
                server_results.append(server_result)
                
                if server_result['success']:
                    # SSH连接成功，统计服务监控结果
                    for service_result in server_result['results']:
                        total_services += 1
                        
                        if service_result['status'] == 'running':
                            normal_services += 1
                            # 检查是否是重启成功的服务
                            if service_result.get('restart_attempted') and service_result.get('restart_success'):
                                restart_success_alerts.append({
                                    'server_name': service_result['server_name'],
                                    'server_ip': server.host,
                                    'service_name': service_result['service_name'],
                                    'status': 'restart_success',
                                    'auto_restart_status': service_result.get('auto_restart_status', '重启成功')
                                })
                        else:
                            error_services += 1
                            # 收集异常服务信息用于通知
                            service_alerts.append({
                                'server_name': service_result['server_name'],
                                'server_ip': server.host,  # 添加服务器IP
                                'service_name': service_result['service_name'],
                                'status': service_result['status'],
                                'error_message': service_result.get('error_message', ''),
                                'auto_restart_status': service_result.get('auto_restart_status', '未开启')
                            })
                else:
                    # SSH连接失败，统计该服务器上的所有服务为异常
                    services = ServiceConfig.query.filter_by(
                        server_id=server.id,
                        is_monitoring=True
                    ).all()
                    
                    for service in services:
                        total_services += 1
                        error_services += 1
                        # 收集SSH连接失败的服务信息用于通知
                        service_alerts.append({
                            'server_name': server.name,
                            'server_ip': server.host,
                            'service_name': service.service_name,
                            'status': 'connection_failed',
                            'error_message': server_result.get('message', 'SSH连接失败')
                        })
            
            # 发送服务监控通知（如果有异常或重启成功）
            if service_alerts or restart_success_alerts:
                self._send_service_alerts(service_alerts, total_services, normal_services, error_services, restart_success_alerts)
            
            summary = {
                'total_services': total_services,
                'normal_services': normal_services,
                'error_services': error_services,
                'server_results': server_results,
                'monitor_time': datetime.now().isoformat()
            }
            
            logger.info(f"服务监控完成: 总数={total_services}, 正常={normal_services}, 异常={error_services}")
            
            return summary
            
        except Exception as e:
            logger.error(f"监控所有服务失败: {str(e)}")
            return {'error': str(e)}
    
    def _send_service_alerts(self, alerts: List[Dict], total: int, normal: int, error: int, restart_success_alerts: List[Dict] = None):
        """
        发送服务监控告警通知
        
        Args:
            alerts: 异常服务列表
            total: 总服务数
            normal: 正常服务数
            error: 异常服务数
            restart_success_alerts: 重启成功服务列表
        """
        try:
            # 构建通知内容
            monitor_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 根据情况确定通知标题
            if alerts and restart_success_alerts:
                title = "服务监控告警"
            elif alerts:
                title = "服务监控告警"
            else:
                title = "服务重启通知"
            
            content = f"{title}\n时间: {monitor_time}\n"
            content += f"总服务数: {total}, 正常: {normal}, 异常: {error}\n"
            
            # 处理异常服务
            if alerts:
                content += "\n异常服务详情:\n"
                for alert in alerts:  # 显示所有异常服务
                    if alert['status'] == 'stopped':
                        status_text = "已停止"
                    elif alert['status'] == 'connection_failed':
                        status_text = "连接失败"
                    else:
                        status_text = "监控失败"
                    
                    # 获取自启动状态
                    auto_restart_status = "未开启"
                    if alert.get('auto_restart_status'):
                        auto_restart_status = alert['auto_restart_status']
                    
                    # 添加IP地址信息
                    server_info = f"{alert['server_name']}({alert.get('server_ip', 'N/A')})"
                    content += f"- {server_info} | {alert['service_name']} | {status_text} | {auto_restart_status}\n"
                    # 如果有错误信息，也显示出来
                    if alert.get('error_message'):
                        content += f"  错误: {alert['error_message']}\n"
            
            # 处理重启成功的服务
            if restart_success_alerts:
                if alerts:
                    content += "\n重启成功服务详情:\n"
                else:
                    content += "\n服务重启详情:\n"
                for alert in restart_success_alerts:
                    server_info = f"{alert['server_name']}({alert.get('server_ip', 'N/A')})"
                    content += f"- {server_info} | {alert['service_name']} | 已停止 | 重启成功\n"
            
            content += "\n更多内容可查看服务配置页面！"
            
            # 直接发送自定义通知
            success, message = self._send_custom_notification(content)
            
            if success:
                logger.info(f"服务监控告警通知发送成功: {message}")
            else:
                logger.error(f"服务监控告警通知发送失败: {message}")
                
        except Exception as e:
            logger.error(f"发送服务监控告警失败: {str(e)}")
    
    def _send_custom_notification(self, content: str):
        """
        发送自定义通知内容
        
        Args:
            content: 通知内容
            
        Returns:
            (success, message)
        """
        try:
            from app.models import NotificationChannel
            import requests
            import json
            
            # 获取所有启用的通知通道
            channels = NotificationChannel.query.filter_by(is_enabled=True).all()
            
            if not channels:
                return True, "没有启用的通知通道"
            
            success_count = 0
            for channel in channels:
                try:
                    # 使用原始内容，变量替换在请求体模板中处理
                    final_content = content
                    
                    if channel.method.upper() == 'GET':
                        # GET请求
                        params = {'message': final_content}
                        response = requests.get(
                            channel.webhook_url,
                            params=params,
                            timeout=channel.timeout
                        )
                    else:
                        # POST请求
                        if channel.request_body:
                            # 使用自定义请求体模板
                            try:
                                body_template = json.loads(channel.request_body)
                                # 递归替换所有字符串值中的变量
                                body = self._replace_variables_in_dict(body_template, final_content)
                                headers = {'Content-Type': 'application/json'}
                                response = requests.post(
                                    channel.webhook_url,
                                    json=body,
                                    headers=headers,
                                    timeout=channel.timeout
                                )
                            except json.JSONDecodeError:
                                # 如果不是有效JSON，直接作为文本发送
                                request_body = channel.request_body.replace('#context#', final_content)
                                request_body = request_body.replace('#url#', '')  # 服务监控通知中移除报告下载链接
                                # 移除固定的"报告下载链接："文本
                                request_body = request_body.replace('报告下载链接：', '')
                                request_body = request_body.replace('报告下载链接:', '')
                                # 清理多余的换行符
                                request_body = request_body.replace('\n\n', '\n').strip()
                                response = requests.post(
                                    channel.webhook_url,
                                    data=request_body,
                                    timeout=channel.timeout
                                )
                        else:
                            # 默认JSON格式
                            data = {'message': final_content}
                            headers = {'Content-Type': 'application/json'}
                            response = requests.post(
                                channel.webhook_url,
                                json=data,
                                headers=headers,
                                timeout=channel.timeout
                            )
                    
                    # 检查响应状态
                    if response.status_code in [200, 201, 204]:
                        logger.info(f"通知发送成功 - 通道: {channel.name}")
                        success_count += 1
                    else:
                        logger.warning(f"通知发送失败 - 通道: {channel.name}, 状态码: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"发送通知失败 - 通道: {channel.name}, 错误: {str(e)}")
            
            message = f"通知发送完成，成功 {success_count}/{len(channels)} 个通道"
            return True, message
            
        except Exception as e:
            logger.error(f"发送自定义通知失败: {str(e)}")
            return False, f"发送通知失败: {str(e)}"
    
    def _replace_variables_in_dict(self, data, content):
        """递归替换字典中的变量"""
        if isinstance(data, dict):
            return {k: self._replace_variables_in_dict(v, content) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._replace_variables_in_dict(item, content) for item in data]
        elif isinstance(data, str):
            # 替换内容变量，移除报告下载链接占位符（服务监控不需要报告链接）
            result = data.replace('#context#', content)
            result = result.replace('#url#', '')  # 服务监控通知中移除报告下载链接
            # 移除固定的"报告下载链接："文本
            result = result.replace('报告下载链接：', '')
            result = result.replace('报告下载链接:', '')
            # 清理多余的换行符
            result = result.replace('\n\n', '\n').strip()
            return result
        else:
            return data
    
    def get_global_setting(self, setting_key: str, default_value: str = '') -> str:
        """
        获取全局设置
        
        Args:
            setting_key: 设置键
            default_value: 默认值
            
        Returns:
            设置值
        """
        try:
            setting = GlobalSettings.query.filter_by(setting_key=setting_key).first()
            if setting:
                return setting.setting_value
            return default_value
            
        except Exception as e:
            logger.error(f"获取全局设置失败: {str(e)}")
            return default_value
    
    def set_global_setting(self, setting_key: str, setting_value: str, description: str = '') -> Tuple[bool, str]:
        """
        设置全局配置
        
        Args:
            setting_key: 设置键
            setting_value: 设置值
            description: 描述
            
        Returns:
            (success, message)
        """
        try:
            setting = GlobalSettings.query.filter_by(setting_key=setting_key).first()
            
            if setting:
                setting.setting_value = setting_value
                if description:
                    setting.description = description
            else:
                setting = GlobalSettings(
                    setting_key=setting_key,
                    setting_value=setting_value,
                    description=description
                )
                db.session.add(setting)
            
            db.session.commit()
            
            logger.info(f"设置全局配置成功: {setting_key} = {setting_value}")
            return True, "设置保存成功"
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"设置全局配置失败: {str(e)}")
            return False, f"设置保存失败: {str(e)}"
    
    def get_service_monitor_interval(self) -> int:
        """
        获取服务监控间隔（分钟）
        
        Returns:
            监控间隔（默认10分钟）
        """
        try:
            interval_str = self.get_global_setting('service_monitor_interval', '10')
            return int(interval_str)
        except:
            return 10
    
    def get_services_overview(self) -> Dict[str, Any]:
        """
        获取服务总览数据
        
        Returns:
            服务总览数据
        """
        try:
            total_services = ServiceConfig.query.count()
            monitoring_services = ServiceConfig.query.filter_by(is_monitoring=True).count()

            normal_count = 0
            error_count = 0

            monitoring_ids = [
                service_id for (service_id,) in
                db.session.query(ServiceConfig.id).filter_by(is_monitoring=True).all()
            ]
            if monitoring_ids:
                latest_times = (
                    db.session.query(
                        ServiceMonitorLog.service_config_id,
                        func.max(ServiceMonitorLog.monitor_time).label('max_time')
                    )
                    .filter(ServiceMonitorLog.service_config_id.in_(monitoring_ids))
                    .group_by(ServiceMonitorLog.service_config_id)
                    .subquery()
                )

                status_counts = (
                    db.session.query(ServiceMonitorLog.status, func.count())
                    .join(
                        latest_times,
                        (ServiceMonitorLog.service_config_id == latest_times.c.service_config_id) &
                        (ServiceMonitorLog.monitor_time == latest_times.c.max_time)
                    )
                    .group_by(ServiceMonitorLog.status)
                    .all()
                )

                for status, count in status_counts:
                    if status == 'running':
                        normal_count += count
                    elif status in ['stopped', 'error', 'connection_failed']:
                        error_count += count

            return {
                'total_services': total_services,
                'monitoring_services': monitoring_services,
                'normal_services': normal_count,
                'error_services': error_count,
                'is_monitoring': self._is_monitoring,
                'monitor_interval': self.get_service_monitor_interval()
            }

        except Exception as e:
            logger.error(f"获取服务总览数据失败: {str(e)}")
            return {
                'total_services': 0,
                'monitoring_services': 0,
                'normal_services': 0,
                'error_services': 0,
                'is_monitoring': False,
                'monitor_interval': 10
            }
    
    def start_monitor_loop(self):
        """
        启动循环监控
        
        Returns:
            (success, message)
        """
        try:
            # 检查是否已经在运行
            if self._is_monitoring and self._monitor_thread and self._monitor_thread.is_alive():
                logger.info("服务监控循环已经在运行")
                return True, "服务监控循环已经在运行"
            
            # 如果状态不一致，先停止旧线程
            if self._is_monitoring or (self._monitor_thread and self._monitor_thread.is_alive()):
                logger.info("检测到遗留的监控线程，先停止")
                self.stop_monitor_loop()
                time.sleep(1)  # 等待停止完成
            
            # 启动新的监控线程
            self._stop_monitor = False
            self._restart_requested = False
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()
            self._is_monitoring = True
            
            logger.info("服务循环监控已启动")
            return True, "服务循环监控已启动"
            
        except Exception as e:
            logger.error(f"启动服务循环监控失败: {str(e)}")
            return False, f"启动失败: {str(e)}"
    
    def restart_monitor_loop(self):
        """
        重启监控循环（在设置变更后调用）
        
        Returns:
            (success, message)
        """
        try:
            if self._is_monitoring:
                self._restart_requested = True
                logger.info("请求重启服务监控循环")
                return True, "服务监控循环将在下次循环开始时重启"
            else:
                return self.start_monitor_loop()
                
        except Exception as e:
            logger.error(f"重启服务监控循环失败: {str(e)}")
            return False, f"重启失败: {str(e)}"
    
    def stop_monitor_loop(self):
        """
        停止循环监控
        
        Returns:
            (success, message)
        """
        try:
            if not self._is_monitoring:
                return True, "监控已经停止"
            
            self._stop_monitor = True
            if self._monitor_thread and self._monitor_thread.is_alive():
                self._monitor_thread.join(timeout=5)
            
            self._is_monitoring = False
            logger.info("服务循环监控已停止")
            return True, "服务循环监控已停止"
            
        except Exception as e:
            logger.error(f"停止服务循环监控失败: {str(e)}")
            return False, f"停止失败: {str(e)}"
    
    def get_monitor_status(self) -> Dict[str, Any]:
        """
        获取监控状态
        
        Returns:
            监控状态信息
        """
        return {
            'is_running': self._is_monitoring,
            'interval_minutes': self.get_service_monitor_interval(),
            'thread_alive': self._monitor_thread.is_alive() if self._monitor_thread else False
        }
    
    def get_ssh_pool_stats(self) -> Dict[str, Any]:
        """
        获取SSH连接池统计信息
        
        Returns:
            连接池统计信息
        """
        try:
            return self.ssh_manager.get_pool_stats()
        except Exception as e:
            logger.error(f"获取SSH连接池统计信息失败: {str(e)}")
            return {'error': str(e)}
    
    def get_ssh_pool_health(self):
        """获取SSH连接池健康状态"""
        try:
            return self.health_checker.check_pool_health()
        except Exception as e:
            logger.error(f"获取SSH连接池健康状态失败: {str(e)}")
            return None
    
    def get_ssh_pool_health_trends(self, server=None, hours=24):
        """获取SSH连接池健康趋势"""
        try:
            return self.health_checker.get_health_trends(server, hours)
        except Exception as e:
            logger.error(f"获取SSH连接池健康趋势失败: {str(e)}")
            return None
    
    def diagnose_ssh_pool_issues(self):
        """诊断SSH连接池问题"""
        try:
            return self.health_checker.diagnose_issues()
        except Exception as e:
            logger.error(f"诊断SSH连接池问题失败: {str(e)}")
            return []
    
    def close_ssh_pool(self):
        """关闭SSH连接池"""
        try:
            self.ssh_manager.close_pool()
            logger.info("SSH连接池已关闭")
        except Exception as e:
            logger.error(f"关闭SSH连接池失败: {str(e)}")

    def _monitor_loop(self):
        """
        监控循环线程
        """
        logger.info("服务监控循环线程已启动")
        
        # 第一次直接执行，不等待
        first_run = True
        
        while not self._stop_monitor:
            try:
                # 检查是否需要重启
                if self._restart_requested:
                    self._restart_requested = False
                    logger.info("检测到重启请求，重新读取配置")
                    # 重新读取间隔设置
                    first_run = True
                
                if not first_run:
                    # 非第一次运行，需要等待间隔时间
                    if self.app:
                        with self.app.app_context():
                            interval_minutes = self.get_service_monitor_interval()
                    else:
                        interval_minutes = 10
                    
                    self._current_interval = interval_minutes
                    wait_seconds = interval_minutes * 60
                    logger.info(f"等待 {interval_minutes} 分钟后执行下次监控")
                    
                    # 等待指定时间，每秒10秒检查一次是否需要停止或重启
                    for i in range(0, wait_seconds, 10):
                        if self._stop_monitor or self._restart_requested:
                            break
                        time.sleep(10)
                    
                    # 如果收到停止或重启请求，退出此次循环
                    if self._stop_monitor:
                        break
                    if self._restart_requested:
                        continue
                
                # 使用Flask应用上下文执行监控
                if self.app:
                    with self.app.app_context():
                        # 获取监控间隔
                        interval_minutes = self.get_service_monitor_interval()
                        self._current_interval = interval_minutes
                        
                        # 执行监控
                        logger.info(f"开始定时服务监控，间隔: {interval_minutes}分钟")
                        monitor_result = self.monitor_all_services()
                        
                        if 'error' in monitor_result:
                            logger.error(f"定时服务监控失败: {monitor_result['error']}")
                        else:
                            logger.info(f"定时服务监控完成: 总数={monitor_result['total_services']}, 正常={monitor_result['normal_services']}, 异常={monitor_result['error_services']}")
                else:
                    logger.error("没有Flask应用上下文，跳过监控")
                
                first_run = False
                    
            except Exception as e:
                logger.error(f"服务监控循环异常: {str(e)}")
                # 发生异常时等待60秒后重试
                for _ in range(0, 60, 10):
                    if self._stop_monitor or self._restart_requested:
                        break
                    time.sleep(10)
        
        logger.info("服务监控循环线程已退出")
