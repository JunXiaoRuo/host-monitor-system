import time
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.models import db, Server, MonitorLog, MonitorReport
from app.ssh_manager import SSHConnectionManager
from app.services import ServerService, ThresholdService
from cryptography.fernet import Fernet
import base64
import threading
import concurrent.futures

logger = logging.getLogger(__name__)

class HostMonitor:
    """主机巡视核心类"""
    
    def __init__(self):
        self.ssh_manager = SSHConnectionManager()
        self._server_service = None
        self._threshold_service = None
    
    @property
    def server_service(self):
        """延迟初始化服务器服务"""
        if self._server_service is None:
            from flask import has_app_context
            if has_app_context():
                self._server_service = ServerService()
            else:
                from app import create_app
                app = create_app()
                with app.app_context():
                    self._server_service = ServerService()
        return self._server_service
    
    @property
    def threshold_service(self):
        """延迟初始化阈值服务"""
        if self._threshold_service is None:
            from flask import has_app_context
            if has_app_context():
                self._threshold_service = ThresholdService()
            else:
                from app import create_app
                app = create_app()
                with app.app_context():
                    self._threshold_service = ThresholdService()
        return self._threshold_service
    
    def _decrypt_password(self, encrypted_password: str) -> str:
        """解密密码 - 使用ServerService的解密方法确保一致性"""
        return self.server_service._decrypt_password(encrypted_password)
    
    def monitor_single_server(self, server: Server, thresholds: Dict[str, float]) -> Dict[str, Any]:
        """
        监控单个服务器
        
        Args:
            server: 服务器对象
            thresholds: 阈值配置
            
        Returns:
            监控结果字典
        """
        # 确保整个监控过程都在应用上下文中执行
        from flask import has_app_context
        
        def _monitor_with_context():
            return self._do_monitor_single_server(server, thresholds)
        
        if has_app_context():
            return _monitor_with_context()
        else:
            from app import create_app
            app = create_app()
            with app.app_context():
                return _monitor_with_context()
    
    def _do_monitor_single_server(self, server: Server, thresholds: Dict[str, float]) -> Dict[str, Any]:
        """
        实际执行单个服务器监控的内部方法
        
        Args:
            server: 服务器对象
            thresholds: 阈值配置
            
        Returns:
            监控结果字典
        """
        start_time = time.time()
        monitor_result = {
            'server_id': server.id,
            'server_name': server.name,
            'server_ip': server.host,  # 添加服务器IP信息
            'status': 'failed',
            'cpu_usage': None,
            'memory_usage': None,
            'disk_info': [],
            'system_info': {},
            'alerts': [],
            'error_message': '',
            'execution_time': 0
        }
        
        try:
            logger.info(f"开始监控服务器: {server.name} ({server.host}:{server.port})")
            
            # 解密密码
            password = self._decrypt_password(server.password) if server.password else None
            logger.debug(f"服务器 {server.name} 认证方式: {'password' if password else 'private_key' if server.private_key_path else 'none'}")
            
            # 建立SSH连接并执行监控
            with self.ssh_manager.get_connection(
                host=server.host,
                port=server.port,
                username=server.username,
                password=password,
                private_key_path=server.private_key_path if server.private_key_path else None
            ) as client:
                
                # 获取系统信息
                system_info = self.ssh_manager.get_system_info(client)
                monitor_result['system_info'] = system_info
                
                # 获取CPU使用率
                cpu_usage = self.ssh_manager.get_cpu_usage(client)
                if cpu_usage is not None:
                    monitor_result['cpu_usage'] = cpu_usage
                    if cpu_usage > thresholds['cpu_threshold']:
                        monitor_result['alerts'].append({
                            'type': 'cpu',
                            'level': 'warning',
                            'message': f'CPU使用率过高: {cpu_usage:.2f}% (阈值: {thresholds["cpu_threshold"]}%)',
                            'value': cpu_usage,
                            'threshold': thresholds['cpu_threshold']
                        })
                
                # 获取内存使用情况
                memory_info = self.ssh_manager.get_memory_usage(client)
                if memory_info is not None:
                    # 保存详细内存信息
                    monitor_result['memory_info'] = memory_info
                    
                    # 为了保持向后兼容，仍然保留memory_usage字段
                    memory_usage = memory_info['usage_percent']
                    monitor_result['memory_usage'] = memory_usage
                    
                    if memory_usage > thresholds['memory_threshold']:
                        monitor_result['alerts'].append({
                            'type': 'memory',
                            'level': 'warning',
                            'message': f'内存使用率过高: {memory_usage:.2f}% (阈值: {thresholds["memory_threshold"]}%)',
                            'value': memory_usage,
                            'threshold': thresholds['memory_threshold']
                        })
                
                # 获取磁盘使用情况
                disk_info = self.ssh_manager.get_disk_usage(client)
                monitor_result['disk_info'] = disk_info
                
                # 检查磁盘使用率告警
                for disk in disk_info:
                    if disk['use_percent'] > thresholds['disk_threshold']:
                        monitor_result['alerts'].append({
                            'type': 'disk',
                            'level': 'warning',
                            'message': f"磁盘 {disk['mounted_on']} 使用率过高: {disk['use_percent']:.2f}% (阈值: {thresholds['disk_threshold']}%)",
                            'value': disk['use_percent'],
                            'threshold': thresholds['disk_threshold'],
                            'filesystem': disk['filesystem'],
                            'mounted_on': disk['mounted_on'],
                            'size': disk['size'],
                            'used': disk['used'],
                            'available': disk['available']
                        })
                
                # 确定状态
                if monitor_result['alerts']:
                    monitor_result['status'] = 'warning'
                    logger.info(f"服务器 {server.name} 监控完成，状态: 告警，告警数: {len(monitor_result['alerts'])}")
                else:
                    monitor_result['status'] = 'success'
                    logger.info(f"服务器 {server.name} 监控完成，状态: 正常")
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"监控服务器 {server.name} ({server.host}:{server.port}) 失败: {error_msg}")
            monitor_result['error_message'] = error_msg
            monitor_result['status'] = 'failed'
        
        finally:
            monitor_result['execution_time'] = time.time() - start_time
        
        return monitor_result
    
    def save_monitor_result(self, monitor_result: Dict[str, Any]) -> Optional[MonitorLog]:
        """
        保存监控结果到数据库
        
        Args:
            monitor_result: 监控结果字典
            
        Returns:
            保存的MonitorLog对象或None
        """
        try:
            # 如果在多线程环境中，确保有应用上下文
            from flask import has_app_context
            from sqlalchemy.orm import sessionmaker
            from app.models import db
            
            def _save_to_db():
                # 在多线程环境中使用独立的数据库会话
                session = None
                try:
                    # 创建新的会话以避免多线程冲突
                    Session = sessionmaker(bind=db.engine)
                    session = Session()
                    
                    monitor_log = MonitorLog(
                        server_id=monitor_result['server_id'],
                        monitor_time=datetime.now(),
                        status=monitor_result['status'],
                        cpu_usage=monitor_result['cpu_usage'],
                        memory_usage=monitor_result['memory_usage'],
                        execution_time=monitor_result['execution_time'],
                        error_message=monitor_result['error_message']
                    )
                    
                    # 设置复杂数据
                    monitor_log.set_disk_info(monitor_result['disk_info'])
                    monitor_log.set_system_info(monitor_result['system_info'])
                    monitor_log.set_alert_info(monitor_result['alerts'])
                    
                    # 设置内存详细信息
                    if 'memory_info' in monitor_result and monitor_result['memory_info']:
                        monitor_log.set_memory_info(monitor_result['memory_info'])
                    
                    session.add(monitor_log)
                    session.commit()
                    
                    # 获取保存后的对象信息
                    result = session.merge(monitor_log)
                    session.close()
                    
                    return result
                    
                except Exception as e:
                    if session:
                        try:
                            session.rollback()
                            session.close()
                        except:
                            pass
                    raise e
            
            if has_app_context():
                # 已经在应用上下文中，直接保存
                return _save_to_db()
            else:
                # 没有应用上下文，创建一个
                from app import create_app
                app = create_app()
                with app.app_context():
                    return _save_to_db()
            
        except Exception as e:
            logger.error(f"保存监控结果失败: {str(e)}")
            return None
    
    def monitor_all_servers(self, max_workers: int = 5) -> Dict[str, Any]:
        """
        监控所有活跃服务器
        
        Args:
            max_workers: 最大并发数
            
        Returns:
            监控汇总结果
        """
        start_time = time.time()
        
        # 确保在应用上下文中获取数据
        from flask import has_app_context
        
        def _get_servers_and_thresholds():
            servers = self.server_service.get_active_servers()
            thresholds = self.threshold_service.get_threshold_config()
            return servers, thresholds
        
        if has_app_context():
            servers, thresholds = _get_servers_and_thresholds()
        else:
            from app import create_app
            app = create_app()
            with app.app_context():
                servers, thresholds = _get_servers_and_thresholds()
        
        if not servers:
            logger.warning("没有找到活跃的服务器")
            return {
                'total_servers': 0,
                'success_count': 0,
                'failed_count': 0,
                'warning_count': 0,
                'results': [],
                'execution_time': time.time() - start_time
            }
        
        results = []
        success_count = 0
        failed_count = 0
        warning_count = 0
        
        # 使用线程池并发监控服务器
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有监控任务
            future_to_server = {
                executor.submit(self.monitor_single_server, server, thresholds): server 
                for server in servers
            }
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_server):
                server = future_to_server[future]
                try:
                    result = future.result()
                    results.append(result)
                    
                    # 统计结果
                    if result['status'] == 'success':
                        success_count += 1
                    elif result['status'] == 'warning':
                        warning_count += 1
                    else:
                        failed_count += 1
                    
                    # 保存监控结果
                    self.save_monitor_result(result)
                    
                    logger.info(f"服务器 {server.name} 监控完成，状态: {result['status']}")
                    
                except Exception as e:
                    logger.error(f"监控服务器 {server.name} 时发生异常: {str(e)}")
                    
                    # 创建失败的监控结果记录
                    failed_result = {
                        'server_id': server.id,
                        'server_name': server.name,
                        'server_ip': server.host,
                        'status': 'failed',
                        'cpu_usage': None,
                        'memory_usage': None,
                        'memory_info': {},
                        'disk_info': [],
                        'system_info': {},
                        'alerts': [],
                        'error_message': str(e),
                        'execution_time': 0
                    }
                    
                    results.append(failed_result)
                    failed_count += 1
                    
                    # 保存失败结果
                    self.save_monitor_result(failed_result)
        
        execution_time = time.time() - start_time
        
        summary = {
            'total_servers': len(servers),
            'success_count': success_count,
            'failed_count': failed_count,
            'warning_count': warning_count,
            'results': results,
            'execution_time': execution_time,
            'thresholds': thresholds,
            'monitor_time': datetime.now().isoformat()
        }
        
        logger.info(f"主机巡视完成: 总数={len(servers)}, 成功={success_count}, 告警={warning_count}, 失败={failed_count}, 耗时={execution_time:.2f}s")
        
        return summary
    
    def get_monitor_history(self, server_id: Optional[int] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        获取监控历史记录
        
        Args:
            server_id: 服务器ID，为None时获取所有服务器
            limit: 记录数量限制
            
        Returns:
            监控历史列表
        """
        try:
            from flask import has_app_context
            
            def _get_history():
                query = MonitorLog.query
                
                if server_id:
                    query = query.filter_by(server_id=server_id)
                
                logs = query.order_by(MonitorLog.monitor_time.desc()).limit(limit).all()
                
                return [log.to_dict() for log in logs]
            
            if has_app_context():
                return _get_history()
            else:
                from app import create_app
                app = create_app()
                with app.app_context():
                    return _get_history()
            
        except Exception as e:
            logger.error(f"获取监控历史失败: {str(e)}")
            return []
    
    def get_latest_server_status(self) -> Dict[int, Dict[str, Any]]:
        """
        获取所有服务器的最新状态
        
        Returns:
            服务器ID为键的状态字典
        """
        try:
            from flask import has_app_context
            
            def _get_status():
                # 获取每个服务器的最新监控记录
                from sqlalchemy import func
                
                subquery = db.session.query(
                    MonitorLog.server_id,
                    func.max(MonitorLog.monitor_time).label('latest_time')
                ).group_by(MonitorLog.server_id).subquery()
                
                latest_logs = db.session.query(MonitorLog).join(
                    subquery,
                    (MonitorLog.server_id == subquery.c.server_id) &
                    (MonitorLog.monitor_time == subquery.c.latest_time)
                ).all()
                
                status_dict = {}
                for log in latest_logs:
                    status_dict[log.server_id] = {
                        'status': log.status,
                        'cpu_usage': log.cpu_usage,
                        'memory_usage': log.memory_usage,
                        'disk_info': log.get_disk_info(),
                        'alert_count': len(log.get_alert_info()),
                        'monitor_time': log.monitor_time.isoformat() if log.monitor_time else None,
                        'execution_time': log.execution_time
                    }
                
                return status_dict
            
            if has_app_context():
                return _get_status()
            else:
                from app import create_app
                app = create_app()
                with app.app_context():
                    return _get_status()
            
        except Exception as e:
            logger.error(f"获取最新服务器状态失败: {str(e)}")
            return {}
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """
        清理旧的监控日志
        
        Args:
            days_to_keep: 保留天数
            
        Returns:
            删除的记录数
        """
        try:
            from flask import has_app_context
            from datetime import timedelta
            
            def _cleanup():
                cutoff_date = datetime.now() - timedelta(days=days_to_keep)
                
                old_logs = MonitorLog.query.filter(MonitorLog.monitor_time < cutoff_date)
                count = old_logs.count()
                
                old_logs.delete()
                db.session.commit()
                
                logger.info(f"清理了 {count} 条旧监控日志")
                return count
            
            if has_app_context():
                return _cleanup()
            else:
                from app import create_app
                app = create_app()
                with app.app_context():
                    return _cleanup()
            
        except Exception as e:
            try:
                db.session.rollback()
            except:
                pass
            logger.error(f"清理旧监控日志失败: {str(e)}")
            return 0